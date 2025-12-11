# Otimizador.py

class OtimizadorCodigo:
    """
    Otimizador para o código intermediário.

    Objetivos principais:
    1. Remover 'jmp Lx' quando a próxima instrução é 'label Lx'.
    2. Substituir temporários definidos por 'lod tN, id, 0' diretamente pelo id,
       quando seguro, e depois remover os 'lod' mortos.
    3. Fazer uma eliminação simples de código morto para temporários.
    4. Renumerar temporários em ordem de primeira aparição (t1, t2, t3, ...).
    5. Remover labels que não possuam nenhuma referência (jmp/jnz/call).
    """

    def __init__(self, codigo):
        # copia "limpa"
        self.codigo = [linha.strip() for linha in codigo if linha.strip()]
        self.referencias = set()

    # ------------------------------------------------------------
    # utilitários
    # ------------------------------------------------------------

    def parse(self, instr):
        """
        "add t1, t2, t3" -> ("add", "t1", "t2", "t3")
        """
        sem_virgula = instr.replace(",", "")
        partes = sem_virgula.split()
        if not partes:
            return "", "-", "-", "-"
        op = partes[0]
        a1 = partes[1] if len(partes) > 1 else "-"
        a2 = partes[2] if len(partes) > 2 else "-"
        a3 = partes[3] if len(partes) > 3 else "-"
        return op, a1, a2, a3

    def is_temp(self, x: str) -> bool:
        return x.startswith("t")

    # ------------------------------------------------------------
    # 1) remover jmp cuja próxima linha seja o label de destino
    # ------------------------------------------------------------

    def remover_jmp_para_proxima_label(self):
        """
        Remove 'jmp Lx' quando o fluxo já cairia em Lx apenas seguindo o código.

        Casos tratados:

            jmp Lx, -, -
            label Lx, -, -

        e também:

            jmp Lx, -, -
            label La, -, -
            label Lb, -, -
            ...
            label Lx, -, -

        ou seja, entre o jmp e o label de destino só podem existir outros labels.
        """
        novo = []
        i = 0
        while i < len(self.codigo):
            op1, a1, _, _ = self.parse(self.codigo[i])

            if op1 == "jmp":
                destino = a1
                j = i + 1
                encontrou_destino = False

                # anda à frente enquanto só houver labels
                while j < len(self.codigo):
                    opj, aj, _, _ = self.parse(self.codigo[j])
                    if opj != "label":
                        break
                    if aj == destino:
                        encontrou_destino = True
                        break
                    j += 1

                if encontrou_destino:
                    # removemos apenas o jmp, mantemos todos os labels
                    i += 1
                    continue  # não adiciona o jmp em 'novo'

            # caso normal: só copia a instrução
            novo.append(self.codigo[i])
            i += 1

        self.codigo = novo

    # ------------------------------------------------------------
    # 2) alias de 'lod tN, id, 0' -> tN ≡ id
    # ------------------------------------------------------------

    def alias_lods(self):
        """
        Cria um mapa de alias para:

        - 'lod tX, id, 0'  ->  tX ≡ id
        - 'ldc tX, N, -'   ->  tX ≡ N   (N literal numérico)

        quando:
        - tX é definido apenas uma vez,
        - tX nunca é usado como destino em outra instrução,
        - tX nunca aparece como base/offset em lod/str.

        Depois substitui usos de tX por (id ou N) nas operações (a2/a3).
        """

        instrs = self.codigo

        # 1) coletar infos de uso/def de temporários
        defs = {}       # temp -> lista de índices onde é dest
        base_uses = {}  # temp -> True se usado como base/offset em lod/str

        for i, instr in enumerate(instrs):
            op, a1, a2, a3 = self.parse(instr)

            # destino
            if self.is_temp(a1):
                defs.setdefault(a1, []).append(i)

            # usos como base/offset em lod/str
            if op in ("lod", "str"):
                if op == "lod":
                    base_v = a2
                    off_v = a3
                else:  # str
                    base_v = a1
                    off_v = a2
                for v in (base_v, off_v):
                    if self.is_temp(v):
                        base_uses[v] = True

        # 2) decidir quais temps podem virar alias
        alias_map = {}  # temp -> substituto (id ou literal numérico)

        for t, def_idxs in defs.items():
            # tem que ter exatamente uma definição
            if len(def_idxs) != 1:
                continue

            idx = def_idxs[0]
            op, a1, a2, a3 = self.parse(instrs[idx])

            # não pode ser usado como base/offset em lod/str
            if base_uses.get(t, False):
                continue

            # caso 1: lod t, id, 0  -> alias para id (não-temp)
            if op == "lod":
                base = a2
                off = a3
                if off == "0" and not self.is_temp(base):
                    alias_map[t] = base
                    continue

            # caso 2: ldc t, N, -   -> alias para N (literal numérico)
            if op == "ldc":
                val = a2
                # só aliasamos se for literal numérico mesmo
                if (val.lstrip("-").isdigit()):
                    alias_map[t] = val
                    continue

        # 3) aplicar alias nas instruções (apenas em usos, não em destino)
        novo = []

        for instr in instrs:
            op, a1, a2, a3 = self.parse(instr)

            # não mexe em a1 (destino), apenas em a2/a3
            if self.is_temp(a2) and a2 in alias_map:
                a2 = alias_map[a2]
            if self.is_temp(a3) and a3 in alias_map:
                a3 = alias_map[a3]

            novo.append(f"{op} {a1}, {a2}, {a3}")

        self.codigo = novo

    # ------------------------------------------------------------
    # 3) Dead Code Elimination de temporários (simples)
    # ------------------------------------------------------------

    def dce_temporarios(self):
        """
        Remove instruções "puras" que definem temporários nunca usados:
        - ldc, lod, mov, add, sub, mul, div, eql, les, grt, neq
        """
        puros = {"ldc", "lod", "mov", "add", "sub", "mul", "div",
                 "eql", "les", "grt", "neq"}

        live = set()
        novo_rev = []

        for instr in reversed(self.codigo):
            op, a1, a2, a3 = self.parse(instr)

            # usos
            uses = []
            for v in (a2, a3):
                if self.is_temp(v):
                    uses.append(v)

            dest = a1 if self.is_temp(a1) else None

            # se pura, define temp, e esse temp não está vivo → mata
            if op in puros and dest is not None and dest not in live:
                continue

            # mantém
            novo_rev.append(instr)

            # atualiza conjunto de vivos
            for u in uses:
                live.add(u)
            if dest is not None and dest in live:
                live.remove(dest)

        self.codigo = list(reversed(novo_rev))

    # ------------------------------------------------------------
    # 4) Renumeração compacta de temporários
    # ------------------------------------------------------------

    def renumerar_temporarios(self):
        """
        Renomeia temporários em ordem de primeira aparição:
          t7, t8, t9, ... -> t1, t2, t3, ...
        """
        mapa = {}
        prox = 1
        novo = []

        for instr in self.codigo:
            op, a1, a2, a3 = self.parse(instr)

            def ren(v):
                nonlocal prox
                if not self.is_temp(v):
                    return v
                if v not in mapa:
                    mapa[v] = f"t{prox}"
                    prox += 1
                return mapa[v]

            a1n = ren(a1)
            a2n = ren(a2)
            a3n = ren(a3)
            novo.append(f"{op} {a1n}, {a2n}, {a3n}")

        self.codigo = novo

    # ------------------------------------------------------------
    # 5) Remover labels sem referência
    # ------------------------------------------------------------

    def analisar_referencias_de_labels(self):
        """
        Coleta todos os labels referenciados por jmp/jnz/call.
        """
        self.referencias = set()
        for instr in self.codigo:
            op, a1, a2, a3 = self.parse(instr)
            if op in ("jmp", "jnz", "call") and a1 != "-":
                self.referencias.add(a1.strip())

    def remover_labels_inuteis(self):
        """
        Remove 'label X' quando X não aparece em nenhuma referência.
        """
        novo = []
        for instr in self.codigo:
            op, a1, a2, a3 = self.parse(instr)
            if op == "label" and a1 not in self.referencias:
                continue
            novo.append(instr)
        self.codigo = novo

    # ------------------------------------------------------------
    # PIPELINE
    # ------------------------------------------------------------

    def otimizar(self):
        # 1) remover jmp direto para label seguinte
        self.remover_jmp_para_proxima_label()

        # 2) alias de lod tX, id, 0 -> tX ≡ id
        self.alias_lods()

        # 3) elimina código morto de temporários
        self.dce_temporarios()

        # 4) renumera temporários em ordem de aparição
        self.renumerar_temporarios()

        # 5) remover labels sem referência (inclui 'e1c' e 'Lmain1' se ninguém usa)
        self.analisar_referencias_de_labels()
        self.remover_labels_inuteis()

        return self.codigo
