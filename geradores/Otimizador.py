# Otimizador.py

class OtimizadorCodigo:
    """
    Otimizador para o código intermediário.

    Etapas:
      1) Remover 'jmp Lx' quando o fluxo já cairia em Lx (mesmo com labels intermediários).
      2) Fazer alias de:
            lod tX, id, 0  ->  tX ≡ id
            ldc tX, N,  -  ->  tX ≡ N
         somente quando:
            - tX é definido exatamente uma vez,
            - tX não é usado como base/offset em lod/str.
      3) Eliminar instruções puras que definem temporários nunca usados.
      4) Renumerar temporários (t1, t2, ...).
      5) Remover labels não referenciados (jmp/jnz/call).
    """

    def __init__(self, codigo):
        # copia "limpa"
        self.codigo = [linha.strip() for linha in codigo if linha.strip()]
        self.referencias = set()

    # ------------------------------------------------------------
    # Utilidades básicas
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
        return isinstance(x, str) and x.startswith("t")

    # ------------------------------------------------------------
    # 1) Remover jmp direto para label de destino
    # ------------------------------------------------------------

    def remover_jmp_para_proxima_label(self):
        """
        Remove 'jmp Lx' quando a execução já cairia em Lx apenas seguindo o fluxo:

            jmp Lx, -, -
            label Lx, -, -

        ou ainda:

            jmp Lx, -, -
            label La, -, -
            label Lb, -, -
            ...
            label Lx, -, -

        (entre o jmp e o destino só podem existir labels).
        """
        novo = []
        i = 0
        while i < len(self.codigo):
            op1, a1, _, _ = self.parse(self.codigo[i])

            if op1 == "jmp":
                destino = a1
                j = i + 1
                encontrou_destino = False

                while j < len(self.codigo):
                    opj, aj, _, _ = self.parse(self.codigo[j])
                    if opj != "label":
                        break
                    if aj == destino:
                        encontrou_destino = True
                        break
                    j += 1

                if encontrou_destino:
                    # removemos o jmp, mantemos os labels
                    i += 1
                    continue

            novo.append(self.codigo[i])
            i += 1

        self.codigo = novo

    # ------------------------------------------------------------
    # 2) Alias de lod/ldc
    # ------------------------------------------------------------

    def alias_lods(self):
        """
        Constrói alias para temporários definidos por:

            lod tX, id, 0  -> tX ≡ id
            ldc tX, N, -   -> tX ≡ N

        se:
          - tX é definido uma única vez (len(defs[tX]) == 1)
          - tX nunca é usado como base/offset em lod/str.

        Depois substitui o uso de tX apenas em posições de USO
        (nunca em posição de destino).
        """

        instrs = self.codigo

        # 1) Coletar definições de temporários (apenas em instruções que realmente escrevem em a1)
        defs = {}       # temp -> [indices onde a1 é destino]
        base_uses = {}  # temp -> True, se usado como base/offset em lod/str

        op_def_a1 = {
            "ldc", "lod", "mov", "add", "sub", "mul", "div",
            "eql", "les", "grt", "neq"
        }

        for i, instr in enumerate(instrs):
            op, a1, a2, a3 = self.parse(instr)

            # destino em a1 apenas se o opcode realmente escreve em a1
            if op in op_def_a1 and self.is_temp(a1):
                defs.setdefault(a1, []).append(i)

            # usos como base/offset em lod/str
            if op in ("lod", "str"):
                if op == "lod":
                    base_v, off_v = a2, a3
                else:  # str base, off, src
                    base_v, off_v = a1, a2
                for v in (base_v, off_v):
                    if self.is_temp(v):
                        base_uses[v] = True

        # 2) Determinar alias possíveis
        alias_map = {}

        for t, def_idxs in defs.items():
            # exigimos uma única definição global (new_temp garante isso)
            if len(def_idxs) != 1:
                continue

            idx = def_idxs[0]
            op, a1, a2, a3 = self.parse(instrs[idx])

            # se é usado como base/offset em lod/str, não fazemos alias
            if base_uses.get(t, False):
                continue

            # caso a) lod tX, id, 0  -> alias para 'id'
            if op == "lod" and a3 == "0" and not self.is_temp(a2):
                alias_map[t] = a2
                continue

            # caso b) ldc tX, N, -   -> alias para literal numérico
            if op == "ldc" and a2.lstrip("-").isdigit():
                alias_map[t] = a2
                continue

        # 3) Aplicar alias nas posições de USO
        novo = []

        for instr in instrs:
            op, a1, a2, a3 = self.parse(instr)

            # posições de uso por opcode
            usos_pos = []
            if op in ("add", "sub", "mul", "div", "mov", "eql", "les", "grt", "neq"):
                usos_pos = [2, 3]            # a2, a3
            elif op == "lod":
                usos_pos = [2, 3]            # base e offset (em geral não-temp; mantemos por segurança)
            elif op == "str":
                usos_pos = [1, 2, 3]         # base, off, src
            elif op == "psh":
                usos_pos = [1]               # valor empilhado
            elif op == "jnz":
                usos_pos = [2]               # cond
            elif op == "ret":
                usos_pos = [1]               # valor a retornar
            else:
                # call, jmp, label etc. não têm uso de temporário em posição especial
                usos_pos = []

            vals = [None, a1, a2, a3]

            def sub(v):
                if self.is_temp(v) and v in alias_map:
                    return alias_map[v]
                return v

            for pos in usos_pos:
                vals[pos] = sub(vals[pos])

            a1n, a2n, a3n = vals[1], vals[2], vals[3]
            novo.append(f"{op} {a1n}, {a2n}, {a3n}")

        self.codigo = novo

    # ------------------------------------------------------------
    # 3) Dead Code Elimination simples de temporários
    # ------------------------------------------------------------

    def dce_temporarios(self):
        """
        Remove instruções "puras" que definem temporários nunca usados:

            ldc, lod, mov, add, sub, mul, div, eql, les, grt, neq

        Critério:
          - a1 é um temporário,
          - o temporário NUNCA aparece em nenhuma posição de USO.
        """
        puros = {"ldc", "lod", "mov", "add", "sub", "mul", "div",
                 "eql", "les", "grt", "neq"}

        # 1) coletar todos os temporários usados em posições de USO
        usados = set()
        for instr in self.codigo:
            op, a1, a2, a3 = self.parse(instr)

            usos = []
            if op in ("add", "sub", "mul", "div", "mov",
                      "eql", "les", "grt", "neq"):
                usos = [a2, a3]
            elif op == "lod":
                usos = [a2, a3]
            elif op == "str":
                usos = [a1, a2, a3]
            elif op == "psh":
                usos = [a1]
            elif op == "jnz":
                usos = [a2]
            elif op == "ret":
                usos = [a1]

            for v in usos:
                if self.is_temp(v):
                    usados.add(v)

        # 2) remover definições puras de temporários que nunca são usados
        novo = []
        for instr in self.codigo:
            op, a1, a2, a3 = self.parse(instr)
            if op in puros and self.is_temp(a1) and a1 not in usados:
                # definição morta (tX nunca lido)
                continue
            novo.append(instr)

        self.codigo = novo

    # ------------------------------------------------------------
    # 4) Renumerar temporários
    # ------------------------------------------------------------

    def renumerar_temporarios(self):
        """
        Renomeia temporários em ordem de primeira aparição global:
          t7, t12, t30, ... -> t1, t2, t3, ...
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
    # 5) Remover labels não referenciados
    # ------------------------------------------------------------

    def analisar_referencias_de_labels(self):
        """
        Coleta labels referenciados por jmp/jnz/call.
        """
        self.referencias = set()
        for instr in self.codigo:
            op, a1, a2, a3 = self.parse(instr)
            if op in ("jmp", "jnz", "call") and a1 != "-":
                self.referencias.add(a1.strip())

    def remover_labels_inuteis(self):
        """
        Remove 'label X, -, -' quando X não aparece em nenhuma referência.
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
        # 1) remover jmps redundantes
        self.remover_jmp_para_proxima_label()

        # 2) alias de lod/ldc
        self.alias_lods()

        # 3) eliminar definições mortas de temporários
        self.dce_temporarios()

        # 4) renumerar temporários
        self.renumerar_temporarios()

        # 5) remover labels não referenciados
        self.analisar_referencias_de_labels()
        self.remover_labels_inuteis()

        return self.codigo
