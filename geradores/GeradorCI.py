class GeradorCodigoIntermediario:
    """
    Percorre a árvore sintática (No) e gera lista de instruções de código intermediário.
    Cada instrução é uma string, ex.: 'add t3, t1, t2'.
    """

    def __init__(self, raiz):
        self.raiz = raiz
        self.codigo = []          # lista de strings
        self.temp_count = 0
        self.label_count = 0

        # mapa simples de variáveis -> par (base, off)
        # por enquanto off = 0 para tudo
        self.variaveis = {}

        self.label_main = None

        # Mapeamento de parâmetros da função atual: nome_param -> registrador temp
        self.param_temps = {}

        self.gerar_programa(self.raiz)

    # utilidades básicas -----------------------------------------------------

    def tipo(self, no):
        # adaptação caso o atributo não se chame "nome"
        return getattr(no, "nome", getattr(no, "tipo", None))

    def emit(self, op, a1="-", a2="-", a3="-"):
        self.codigo.append(f"{op} {a1}, {a2}, {a3}")

    def novo_temp(self):
        self.temp_count += 1
        return f"t{self.temp_count}"

    def novo_label(self, prefixo="L"):
        self.label_count += 1
        return f"{prefixo}{self.label_count}"

    # memória: represento cada variável como (nome, 0)
    def mem_var(self, nome_var):
        if nome_var not in self.variaveis:
            self.variaveis[nome_var] = (nome_var, 0)
        base, off = self.variaveis[nome_var]
        return base, off

    # ------------------------------------------------------------------------
    # PROGRAMA / CORPO / LISTA_COM / COMANDO
    # ------------------------------------------------------------------------

    def gerar_programa(self, no):
        # [PROGRAMA] → program ID ; CORPO
        # filhos: PROGRAM, ID, ';', CORPO
        nome_prog = None
        for f in no.filhos:
            if self.tipo(f) == "ID":
                nome_prog = f.valor
        if nome_prog is None:
            nome_prog = "main"

        # cria rótulo do main
        self.label_main = self.novo_label("Lmain")

        # entrada do programa
        self.emit("label", nome_prog, "-", "-")
        # pula as funções e vai direto para o corpo principal
        self.emit("jmp", self.label_main, "-", "-")

        # gera corpo (declarações + comandos)
        for f in no.filhos:
            if self.tipo(f) == "CORPO":
                self.gerar_corpo(f)

    def gerar_corpo(self, no):
        # CORPO → DECLARACOES begin LISTA_COM end | begin LISTA_COM end
        # 1) declarações (inclui funções)
        for f in no.filhos:
            if self.tipo(f) == "DECLARACOES":
                self.gerar_declaracoes(f)

        # 2) marca início do main
        if self.label_main:
            self.emit("label", self.label_main, "-", "-")
            self.label_main = None   # para não reutilizar

        # 3) comandos do begin ... end
        for f in no.filhos:
            if self.tipo(f) == "LISTA_COM":
                self.gerar_lista_com(f)

    def gerar_declaracoes(self, no):
        """
        Para o gerador, as declarações só interessam para conhecer os IDs.
        Não há código gerado aqui, apenas registro de variáveis.
        """
        for f in no.filhos:
            if self.tipo(f) == "DEF_VAR":
                self.coletar_variaveis(f)
            elif self.tipo(f) == "LISTA_FUNC":
                self.gerar_lista_func(f)

    def gerar_lista_func(self, no):
        # LISTA_FUNC → FUNCAO LISTA_FUNC | ε
        for f in no.filhos:
            if self.tipo(f) == "FUNCAO":
                self.gerar_funcao(f)
            elif self.tipo(f) == "LISTA_FUNC":
                self.gerar_lista_func(f)

    # ----------------------- PARÂMETROS DE FUNÇÃO ---------------------------

    def coletar_ids_param(self, no):
        """
        Coleta todos os IDs que representam parâmetros dentro de LISTA_VAR
        (ou subárvore equivalente usada na declaração de parâmetros).
        """
        ids = []

        def visita(n):
            if self.tipo(n) == "ID":
                ids.append(n.valor)
            for f in getattr(n, "filhos", []):
                visita(f)

        visita(no)
        return ids

    def gerar_funcao(self, no):
        # FUNCAO → NOME_FUNCAO BLOCO_FUNCAO
        nome_no = None
        bloco_fun_no = None

        for f in no.filhos:
            if self.tipo(f) == "NOME_FUNCAO":
                nome_no = f
            elif self.tipo(f) == "BLOCO_FUNCAO":
                bloco_fun_no = f

        nome_func = None
        parametros = []  # nomes dos parâmetros, na ordem declarada

        # --- extrai nome da função e parâmetros ---
        if nome_no:
            for f in nome_no.filhos:
                if self.tipo(f) == "ID":
                    nome_func = f.valor           # ex.: "funcao"
                elif self.tipo(f) == "LISTA_VAR":
                    # parâmetros são tratados como variáveis locais
                    self.coletar_variaveis(f)
                    parametros.extend(self.coletar_ids_param(f))

        if nome_func is None:
            nome_func = "anon"

        # rótulo da função
        self.emit("label", nome_func, "-", "-")

        # salva mapeamento de parâmetros anterior (caso haja aninhamento)
        old_param_temps = self.param_temps
        self.param_temps = {}

        # prólogo da função: POP dos parâmetros em ordem inversa
        # Chamador:
        #   psh param1
        #   psh param2
        #   call funcao, 2, -
        # Pilha (topo): param2, param1
        # Função:
        #   pop tX  ; param2
        #   pop tY  ; param1
        for nome_param in reversed(parametros):
            reg = self.novo_temp()
            self.emit("pop", reg, "-", "-")
            self.param_temps[nome_param] = reg

        # --- corpo da função (variáveis locais + bloco begin...end) ---
        if bloco_fun_no:
            self.gerar_bloco_funcao(bloco_fun_no)

        # --- retorno: carrega 'result' e devolve em r0 ---
        base, off = self.mem_var("result")   # 'result' tratado como var normal
        t = self.novo_temp()
        self.emit("lod", t, base, off)
        self.emit("mov", "r0", t, "-")
        self.emit("ret", "r0", "-", "-")

        # restaura mapeamento de parâmetros anterior
        self.param_temps = old_param_temps

    def gerar_bloco_funcao(self, no):
        # BLOCO_FUNCAO → DEF_VAR BLOCO | BLOCO
        for f in no.filhos:
            if self.tipo(f) == "DEF_VAR":
                self.coletar_variaveis(f)       # variáveis locais da função
            elif self.tipo(f) == "BLOCO":
                self.gerar_bloco(f)

    def coletar_variaveis(self, no):
        # percorre LISTA_VAR / VARIAVEL / LISTA_ID e registra nomes
        if self.tipo(no) == "DEF_VAR":
            for f in no.filhos:
                if self.tipo(f) == "LISTA_VAR":
                    self.coletar_variaveis(f)
        elif self.tipo(no) == "LISTA_VAR":
            for f in no.filhos:
                if self.tipo(f) == "VARIAVEL":
                    self.coletar_variaveis(f)
                elif self.tipo(f) == "LISTA_VAR":
                    self.coletar_variaveis(f)
        elif self.tipo(no) == "VARIAVEL":
            for f in no.filhos:
                if self.tipo(f) == "LISTA_ID":
                    self.coletar_variaveis(f)
        elif self.tipo(no) == "LISTA_ID":
            for f in no.filhos:
                if self.tipo(f) == "ID":
                    self.mem_var(f.valor)  # registra
                elif self.tipo(f) == "LISTA_ID":
                    self.coletar_variaveis(f)

    def gerar_lista_com(self, no):
        # [LISTA_COM] → COMANDO ; LISTA_COM | ε
        for f in no.filhos:
            if self.tipo(f) == "COMANDO":
                self.gerar_comando(f)
            elif self.tipo(f) == "LISTA_COM":
                self.gerar_lista_com(f)

    def gerar_comando(self, no):
        """
        [COMANDO] → NOME := VALOR
                   | while EXP_LOGICA BLOCO
                   | if EXP_LOGICA then BLOCO ELSE
                   | write CONST_VALOR
                   | read NOME
        """
        filhos = no.filhos
        if not filhos:
            return

        # distinção pelo primeiro filho / token
        t0 = self.tipo(filhos[0])

        # atribuição
        if t0 == "NOME":
            nome_lhs = filhos[0]
            # espera-se: NOME, ATRIBUICAO, VALOR
            valor_no = None
            for f in filhos:
                if self.tipo(f) == "VALOR":
                    valor_no = f
                    break
            reg_valor = self.gerar_valor(valor_no)
            var = self.obter_id_de_nome(nome_lhs)
            base, off = self.mem_var(var)
            self.emit("str", base, off, reg_valor)

            # se for parâmetro da função atual, atualiza o registrador associado
            if var in self.param_temps:
                self.param_temps[var] = reg_valor

        # while
        elif self.tipo(filhos[0]) == "WHILE" or getattr(filhos[0], "valor", None) == "while":
            # estrutura: WHILE, EXP_LOGICA, BLOCO
            label_inicio = self.novo_label("Lwhile")
            label_fim = self.novo_label("Lendwhile")

            self.emit("label", label_inicio, "-", "-")

            exp_logica_no = filhos[1]
            reg_cond = self.gerar_exp_logica(exp_logica_no)

            # se cond ≠ 0, vai para corpo; senão salta para fim
            label_corpo = self.novo_label("Lbody")
            self.emit("jnz", label_corpo, reg_cond, "-")
            self.emit("jmp", label_fim, "-", "-")

            self.emit("label", label_corpo, "-", "-")
            self.gerar_bloco(filhos[2])
            self.emit("jmp", label_inicio, "-", "-")
            self.emit("label", label_fim, "-", "-")

        # if
        elif self.tipo(filhos[0]) == "IF" or getattr(filhos[0], "valor", None) == "if":
            # estrutura: IF, EXP_LOGICA, THEN, BLOCO, [ELSE]
            exp_logica_no = None
            bloco_then = None
            no_else = None
            i = 0
            while i < len(filhos):
                if self.tipo(filhos[i]) == "EXP_LOGICA":
                    exp_logica_no = filhos[i]
                if self.tipo(filhos[i]) == "BLOCO":
                    if bloco_then is None:
                        bloco_then = filhos[i]
                    else:
                        # segundo bloco é o else
                        no_else = filhos[i]
                if self.tipo(filhos[i]) == "ELSE":
                    no_else = filhos[i]
                i += 1

            reg_cond = self.gerar_exp_logica(exp_logica_no)
            label_then = self.novo_label("Lthen")
            label_fim = self.novo_label("Lendif")
            label_else = self.novo_label("Lelse") if no_else else label_fim

            self.emit("jnz", label_then, reg_cond, "-")
            self.emit("jmp", label_else, "-", "-")

            # then
            self.emit("label", label_then, "-", "-")
            self.gerar_bloco(bloco_then)
            self.emit("jmp", label_fim, "-", "-")

            # else (se existir)
            if no_else:
                self.emit("label", label_else, "-", "-")
                # ELSE → else BLOCO | ε
                for f in no_else.filhos:
                    if self.tipo(f) == "BLOCO":
                        self.gerar_bloco(f)

            self.emit("label", label_fim, "-", "-")

        # write CONST_VALOR
        elif (self.tipo(filhos[0]) == "WRITE" or
              getattr(filhos[0], "valor", None) == "write"):
            const_no = None
            for f in filhos:
                if self.tipo(f) == "CONST_VALOR":
                    const_no = f
                    break
            reg = self.gerar_const_valor(const_no)
            # convenção: empilha argumento e chama função WRITE
            self.emit("psh", reg, "-", "-")
            self.emit("call", "WRITE", 1, "-")
            self.emit("pop", self.novo_temp(), "-", "-")  # descarta retorno/pilha

        # read NOME
        elif (self.tipo(filhos[0]) == "READ" or
              getattr(filhos[0], "valor", None) == "read"):
            nome_no = None
            for f in filhos:
                if self.tipo(f) == "NOME":
                    nome_no = f
                    break
            var = self.obter_id_de_nome(nome_no)
            base, off = self.mem_var(var)
            # convenção: chama função READ, que devolve valor em um temp fictício rRet
            self.emit("call", "READ", 0, "-")
            reg_ret = self.novo_temp()
            # supomos que o runtime deixa valor lido em 'r0'; copiamos pra temp
            self.emit("mov", reg_ret, "r0", "-")
            self.emit("str", base, off, reg_ret)

    # ------------------------------------------------------------------------
    # BLOCOS
    # ------------------------------------------------------------------------

    def gerar_bloco(self, no):
        # [BLOCO] → begin LISTA_COM end | COMANDO
        if any(self.tipo(f) == "COMANDO" for f in no.filhos):
            for f in no.filhos:
                if self.tipo(f) == "COMANDO":
                    self.gerar_comando(f)
        else:
            for f in no.filhos:
                if self.tipo(f) == "LISTA_COM":
                    self.gerar_lista_com(f)

    # ------------------------------------------------------------------------
    # EXPRESSÕES / VALORES
    # ------------------------------------------------------------------------

    def gerar_const_valor(self, no):
        # CONST_VALOR → "string" | EXP_MAT
        # retorna registrador com resultado
        for f in no.filhos:
            if self.tipo(f) == "STRING":
                reg = self.novo_temp()
                self.emit("ldc", reg, repr(f.valor), "-")  # repr para manter aspas
                return reg
            if self.tipo(f) == "EXP_MAT":
                return self.gerar_exp_mat(f)
        # caso improvável
        reg = self.novo_temp()
        self.emit("ldc", reg, 0, "-")
        return reg

    def gerar_valor(self, no):
        """
        [VALOR] → NUMERO EXP_MAT'
                 | ID VALOR'
        Aqui tratamos basicamente como expressão aritmética.
        """
        if not no.filhos:
            reg = self.novo_temp()
            self.emit("ldc", reg, 0, "-")
            return reg

        f0 = no.filhos[0]

        # caso comece com número
        if self.tipo(f0) == "NUMERO":
            reg = self.gerar_parametro_numero(f0)
            # pode haver EXP_MAT'
            for f in no.filhos[1:]:
                if self.tipo(f) == "EXP_MAT'":
                    reg = self.gerar_exp_mat_linha(f, reg)
            return reg

        # caso comece com ID → pode ser variável, expressão ou chamada de função
        if self.tipo(f0) == "ID":
            # construo um nó NOME artificial: [ID] + possível NOME'
            nome_no = self.construir_nome_a_partir_de_valor(no)
            # verifica se VALOR' é LISTA_PARAM (chamada de função)
            valor_linha = None
            for f in no.filhos[1:]:
                if self.tipo(f) == "VALOR'":
                    valor_linha = f
                    break

            if valor_linha and any(self.tipo(ff) == "LISTA_PARAM" for ff in valor_linha.filhos):
                # chamada de função ID(...)
                return self.gerar_chamada_funcao(f0.valor, valor_linha)
            else:
                # caso simples: expressão começando em variável
                reg = self.gerar_nome_rvalue(nome_no)
                if valor_linha:
                    # trata [NOME'] [EXP_MAT']
                    for ff in valor_linha.filhos:
                        if self.tipo(ff) == "EXP_MAT'":
                            reg = self.gerar_exp_mat_linha(ff, reg)
                return reg

        # fallback
        return self.gerar_exp_mat(no)

    def construir_nome_a_partir_de_valor(self, valor_no):
        """
        Recebe o nó VALOR (ID VALOR') e retorna um nó NOME equivalente,
        reaproveitando o ID e possível NOME'.
        """
        id_no = valor_no.filhos[0]
        nome_filhos = [id_no]
        for f in valor_no.filhos[1:]:
            if self.tipo(f) == "VALOR'":
                for ff in f.filhos:
                    if self.tipo(ff) == "NOME'":
                        nome_filhos.append(ff)
        # cria nó NOME “artificial”
        class _NoTmp:
            def __init__(self, nome, filhos):
                self.nome = nome
                self.filhos = filhos
                self.valor = None
        return _NoTmp("NOME", nome_filhos)

    def gerar_chamada_funcao(self, nome_func, valor_linha):
        """
        Gera psh para cada parâmetro e call nome_func, n, -
        Retorna um temporário com o valor de retorno (mov a partir de r0).
        """
        # VALOR' → LISTA_PARAM
        # LISTA_PARAM → ( LISTA_NOME )
        # LISTA_NOME → PARAMETRO LISTA_NOME' | ε
        parametros = []
        for f in valor_linha.filhos:
            if self.tipo(f) == "LISTA_PARAM":
                parametros = self.coletar_parametros(f)

        # gera código para cada parâmetro (avalia e empilha)
        for p_no in parametros:
            reg = self.gerar_parametro(p_no)
            self.emit("psh", reg, "-", "-")

        # chamada da função com número de parâmetros
        self.emit("call", nome_func, len(parametros), "-")

        # NÃO desempilha aqui: quem consome a pilha é a função (via pop)

        # assume que retorno está em r0
        reg_ret = self.novo_temp()
        self.emit("mov", reg_ret, "r0", "-")
        return reg_ret

    def coletar_parametros(self, lista_param_no):
        """
        Retorna lista de nós PARAMETRO dentro de LISTA_PARAM.
        """
        parametros = []

        def visita(no):
            if self.tipo(no) == "PARAMETRO":
                parametros.append(no)
            for f in getattr(no, "filhos", []):
                visita(f)

        visita(lista_param_no)
        return parametros

    # ------------------ EXPRESSÃO ARITMÉTICA -----------------------------

    def gerar_parametro(self, no_param):
        # PARAMETRO → NOME | NUMERO
        f0 = no_param.filhos[0]
        if self.tipo(f0) == "NUMERO":
            return self.gerar_parametro_numero(f0)
        elif self.tipo(f0) == "NOME":
            return self.gerar_nome_rvalue(f0)

    def gerar_parametro_numero(self, num_no):
        reg = self.novo_temp()
        self.emit("ldc", reg, num_no.valor, "-")
        return reg

    def gerar_nome_rvalue(self, nome_no):
        """
        Carrega o valor de um NOME (variável simples).
        Se for parâmetro da função atual, usa o registrador associado (sem lod).
        """
        var = self.obter_id_de_nome(nome_no)

        # Se for parâmetro da função atual, retorna o temp correspondente
        if var in self.param_temps:
            return self.param_temps[var]

        # Caso contrário, variável "normal" em memória
        base, off = self.mem_var(var)
        reg = self.novo_temp()
        self.emit("lod", reg, base, off)
        return reg

    def obter_id_de_nome(self, nome_no):
        """
        NOME → ID NOME'
        Para simplificação, usa apenas o ID base.
        """
        for f in nome_no.filhos:
            if self.tipo(f) == "ID":
                return f.valor
        # fallback
        return "tmpVar"

    def gerar_exp_mat(self, no):
        # [EXP_MAT] → PARAMETRO EXP_MAT'
        param_no = None
        exp_linha = None
        for f in no.filhos:
            if self.tipo(f) == "PARAMETRO":
                param_no = f
            elif self.tipo(f) == "EXP_MAT'":
                exp_linha = f
        reg = self.gerar_parametro(param_no)
        if exp_linha:
            reg = self.gerar_exp_mat_linha(exp_linha, reg)
        return reg

    def gerar_exp_mat_linha(self, no, reg_esq):
        # [EXP_MAT’] → OP_MAT EXP_MAT | ε
        if not no.filhos:
            return reg_esq

        op_no = None
        exp_dir = None
        for f in no.filhos:
            if self.tipo(f) == "OP_MAT":
                op_no = f
            elif self.tipo(f) == "EXP_MAT":
                exp_dir = f
        reg_dir = self.gerar_exp_mat(exp_dir)

        res = self.novo_temp()
        op = op_no.valor  # '+', '-', '*', '/'

        if op == '+':
            self.emit("add", res, reg_esq, reg_dir)
        elif op == '-':
            self.emit("sub", res, reg_esq, reg_dir)
        elif op == '*':
            self.emit("mul", res, reg_esq, reg_dir)
        elif op == '/':
            self.emit("div", res, reg_esq, reg_dir)
        else:
            # se aparecer algo inesperado, copia o operando esquerdo
            self.emit("mov", res, reg_esq, "-")

        return res

    # ------------------ EXPRESSÃO LÓGICA / RELACIONAL --------------------

    def gerar_exp_logica(self, no):
        # [EXP_LOGICA] → EXP_MAT EXP_LOGICA'
        exp_mat_no = None
        exp_log_linha = None
        for f in no.filhos:
            if self.tipo(f) == "EXP_MAT":
                exp_mat_no = f
            elif self.tipo(f) == "EXP_LOGICA'":
                exp_log_linha = f

        reg_esq = self.gerar_exp_mat(exp_mat_no)

        if exp_log_linha:
            return self.gerar_exp_logica_linha(exp_log_linha, reg_esq)
        return reg_esq  # permite while (expr) sem operador relacional

    def gerar_exp_logica_linha(self, no, reg_esq):
        # [EXP_LOGICA’] → OP_LOGICO EXP_LOGICA | ε
        if not no.filhos:
            return reg_esq

        op_no = None
        exp_dir = None
        for f in no.filhos:
            if self.tipo(f) == "OP_LOGICO":
                op_no = f
            elif self.tipo(f) == "EXP_LOGICA":
                exp_dir = f

        reg_dir = self.gerar_exp_logica(exp_dir)
        res = self.novo_temp()

        op = op_no.valor  # '<', '>', '=', '!' ...

        if op == '=':
            self.emit("eql", res, reg_esq, reg_dir)
        elif op == '<':
            self.emit("les", res, reg_esq, reg_dir)
        elif op == '>':
            self.emit("grt", res, reg_esq, reg_dir)
        elif op == '!':
            self.emit("neq", res, reg_esq, reg_dir)
        else:
            # se operador desconhecido, apenas copia
            self.emit("mov", res, reg_esq, "-")

        return res
