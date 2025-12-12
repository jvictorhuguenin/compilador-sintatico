from utils.Cor import Cor
from utils.No import No
from utils.Token import Token
from utils.First import First
from utils.Follow import Follow

class AnalisadorSintatico:
    def __init__(self, listaTokens):
        self.tokens = listaTokens  # tuplas (tipo, valor, linha)
        self.pos = 0
        self.erro = False
        self.arvoreSintatica = self.programa()

    def token_atual(self):
        return self.tokens[self.pos] if self.pos < len(self.tokens) else None

    def tratarTerminal(self, recebido: Token):
        esperado = recebido.value
        token = self.token_atual()
        if token and token[0] == esperado:
            self.pos += 1
            return No(esperado, valor=token[1])
        else:
            return self.tratarErro(valido=esperado)
            
        
    def tratarErro(self, valido="", follow={} ):
        token = self.token_atual()
        self.erro = True

        if(not token):
            if(follow):
                print(Cor.pintar(f"Erro: Token esperado, mas o arquivo terminou inesperadamente", Cor.VERMELHO))
            else:
                print(Cor.pintar(f"Erro: esperado {valido}, mas o arquivo terminou inesperadamente", Cor.VERMELHO))
            return No("ERRO", valor="EOF")

        self.pos += 1
        if(follow):
            print(Cor.pintar(f"Erro no {token[1]}, na linha {token[2]}", Cor.VERMELHO))
            while (self.token_atual() and self.token_atual()[0] not in follow):
                self.pos += 1
        else:
            print(Cor.pintar(f"Esperado {valido}, mas encontrado {token} na linha {token[2]}", Cor.VERMELHO))
            while (self.token_atual() and self.token_atual()[0] != valido):
                self.pos += 1
        
        self.pos += 1
        return No("ERRO", valor=str(token))

    # --- NÃO TERMINAIS ---

    def programa(self):
        # [PROGRAMA] ::= (program) [ID] (;) [CORPO]
        filhos = []
        token = self.token_atual()
        if token and token[0] == Token.PROGRAM.value:
            filhos.append(self.tratarTerminal(Token.PROGRAM))
            filhos.append(self.tratarTerminal(Token.ID))
            filhos.append(self.tratarTerminal(Token.PONTO_VIRGULA))
            filhos.append(self.corpo())
            return No("PROGRAMA", filhos)
        else:
            return self.tratarErro(follow=Follow.PROGRAMA)

    def corpo(self):
        # [CORPO] ::= [DECLARACOES] (begin) [LISTA_COM] (end)
        #          | (begin) [LISTA_COM] (end)
        filhos = []
        token = self.token_atual()
        if token and token[0] in First.DECLARACOES:
            filhos.append(self.declaracoes())
            filhos.append(self.tratarTerminal(Token.BEGIN))
            filhos.append(self.lista_com())
            filhos.append(self.tratarTerminal(Token.END))
            return No("CORPO", filhos)
        elif token and token[0] == Token.BEGIN.value:
            filhos.append(self.tratarTerminal(Token.BEGIN))
            filhos.append(self.lista_com())
            filhos.append(self.tratarTerminal(Token.END))
            return No("CORPO", filhos)
        else:
            return self.tratarErro(follow=Follow.CORPO)

    def declaracoes(self):
        # [DECLARACOES] ::= [DEF_CONST] [DEF_TIPOS] [DEF_VAR] [LISTA_FUNC] | ε
        filhos = []
        filhos.append(self.def_const())
        filhos.append(self.def_tipos())
        filhos.append(self.def_var())
        filhos.append(self.lista_func())
        return No("DECLARACOES", filhos)

    def def_const(self):
        # [DEF_CONST] ::= (const) [LISTA_CONST] | ε
        filhos = []
        token = self.token_atual()
        if token and token[0] == Token.CONST.value:
            filhos.append(self.tratarTerminal(Token.CONST))
            filhos.append(self.lista_const())
        return No("DEF_CONST", filhos)
        
    def lista_const(self):
        # [LISTA_CONST] ::= [CONSTANTE] [LISTA_CONST’]
        filhos = []
        token = self.token_atual()
        if token and token[0] in First.CONSTANTE:
            filhos.append(self.constante())
            filhos.append(self.lista_const_())
            return No("LISTA_CONST", filhos)
        else:
            return self.tratarErro(follow=Follow.LISTA_CONST)        

    def lista_const_(self):
        # [LISTA_CONST’] ::= [LISTA_CONST] | ε
        filhos = []
        token = self.token_atual()
        if token and token[0] in First.LISTA_CONST:
            filhos.append(self.lista_const())
        return No("LISTA_CONST'", filhos)

    def constante(self):
        # [CONSTANTE] ::= [ID] (:=) [CONST_VALOR] (;)
        filhos = []
        token = self.token_atual()
        if token and token[0] == Token.ID.value:
            filhos.append(self.tratarTerminal(Token.ID))
            filhos.append(self.tratarTerminal(Token.ATRIBUICAO))
            filhos.append(self.const_valor())
            filhos.append(self.tratarTerminal(Token.PONTO_VIRGULA))
            return No("CONSTANTE", filhos)
        else:
            return self.tratarErro(follow=Follow.CONSTANTE) 
        
    def const_valor(self):
        # [CONST_VALOR] ::= (“) sequência alfanumérica (“) | [EXP_MAT]
        filhos = []
        token = self.token_atual()
        if token and token[0] == Token.STRING.value:
            filhos.append(self.tratarTerminal(Token.STRING))
            return No("CONST_VALOR", filhos)
        elif token and token[0] in First.EXP_MAT:
            filhos.append(self.exp_mat())
            return No("CONST_VALOR", filhos)
        else:
            return self.tratarErro(follow=Follow.CONST_VALOR)

    def def_tipos(self):
        # [DEF_TIPOS] ::= (type) [LISTA_TIPOS] | ε
        filhos = []
        token = self.token_atual()
        if token and token[0] == Token.TYPE.value:
            filhos.append(self.tratarTerminal(Token.TYPE))
            filhos.append(self.lista_tipos())
        return No("DEF_TIPOS", filhos) 

    def lista_tipos(self):
        # [LISTA_TIPOS] ::= [TIPO] (;) [LISTA_TIPOS’] 
        filhos = []
        token = self.token_atual()
        if token and token[0] in First.TIPO:
            filhos.append(self.tipo())
            filhos.append(self.tratarTerminal(Token.PONTO_VIRGULA))
            filhos.append(self.lista_tipos_())
            return No("LISTA_TIPOS", filhos) 
        else:
            return self.tratarErro(follow=Follow.LISTA_TIPOS) 

    def lista_tipos_(self):
        # [LISTA_TIPOS’] ::= [LISTA_TIPOS] | ε
        filhos = []
        token = self.token_atual()
        if token and token[0] in First.LISTA_TIPOS:
            filhos.append(self.lista_tipos())
        return No("LISTA_TIPOS'", filhos)

    def tipo(self):
        # [TIPO] ::= [ID] (:=) [TIPO_DADO]
        filhos = []
        token = self.token_atual()
        if token and token[0] == Token.ID.value:
            filhos.append(self.tratarTerminal(Token.ID))
            filhos.append(self.tratarTerminal(Token.ATRIBUICAO))
            filhos.append(self.tipo_dado())
            return No("TIPO", filhos)
        else:
            return self.tratarErro(follow=Follow.TIPO) 

    def tipo_dado(self):
        # [TIPO_DADO] ::= (integer) | (real) | (array) ([) [NUMERO] (]) (of) [TIPO_DADO] | (record) [LISTA_VAR] (end) | [ID]
        token = self.token_atual()
        filhos = []
        if token and token[0] == Token.INTEGER.value:
            filhos.append(self.tratarTerminal(Token.INTEGER))
            return No("TIPO_DADO", filhos)
        elif token and token[0] == Token.REAL.value:
            filhos.append(self.tratarTerminal(Token.REAL))
            return No("TIPO_DADO", filhos)
        elif token and token[0] == Token.ARRAY.value:
            filhos.append(self.tratarTerminal(Token.ARRAY))
            filhos.append(self.tratarTerminal(Token.COLCHETE_ESQ))
            filhos.append(self.tratarTerminal(Token.NUMERO))
            filhos.append(self.tratarTerminal(Token.COLCHETE_DIR))
            filhos.append(self.tratarTerminal(Token.OF))
            filhos.append(self.tipo_dado())
            return No("TIPO_DADO", filhos)
        elif token and token[0] == Token.RECORD.value:
            filhos.append(self.tratarTerminal(Token.RECORD))
            filhos.append(self.lista_var())
            filhos.append(self.tratarTerminal(Token.END))
            return No("TIPO_DADO", filhos)
        elif token and token[0] == Token.ID.value:
            filhos.append(self.tratarTerminal(Token.ID))
            return No("TIPO_DADO", filhos)
        else:
            return self.tratarErro(follow=Follow.TIPO_DADO)

    def def_var(self):
        # [DEF_VAR] ::= (var) [LISTA_VAR] | ε
        filhos = []
        token = self.token_atual()
        if token and token[0] == Token.VAR.value:
            filhos.append(self.tratarTerminal(Token.VAR))
            filhos.append(self.lista_var())
        return No("DEF_VAR", filhos)

    def lista_var(self):
        # [LISTA_VAR] ::= [VARIAVEL] [LISTA_VAR’] | ε                                   loop no ;                                       
        filhos = []
        token = self.token_atual()
        if token and token[0] in First.VARIAVEL:
            filhos.append(self.variavel())
            filhos.append(self.lista_var_())
        return No("LISTA_VAR", filhos)

    def lista_var_(self):
        # [LISTA_VAR’] ::= (;) [LISTA_VAR] | ε
        filhos = []
        token = self.token_atual()
        if token and token[0] == Token.PONTO_VIRGULA.value:
            filhos.append(self.tratarTerminal(Token.PONTO_VIRGULA))
            filhos.append(self.lista_var())
        return No("LISTA_VAR'", filhos)

    def variavel(self):
        # [VARIAVEL] ::= [LISTA_ID] (:) [TIPO_DADO]
        filhos = []
        token = self.token_atual()
        if token and token[0] in First.LISTA_ID:
            filhos.append(self.lista_id())
            filhos.append(self.tratarTerminal(Token.DOIS_PONTOS))
            filhos.append(self.tipo_dado())
            return No("VARIAVEL", filhos)
        else:
            return self.tratarErro(follow=Follow.VARIAVEL)

    def lista_id(self):
        # [LISTA_ID] ::= [ID] [LISTA_ID’]
        filhos = []
        token = self.token_atual()
        if token and token[0] == Token.ID.value:
            filhos.append(self.tratarTerminal(Token.ID))
            filhos.append(self.lista_id_())
            return No("LISTA_ID", filhos)
        else:
            return self.tratarErro(follow=Follow.LISTA_ID)

    def lista_id_(self):
        # [LISTA_ID’] ::= (,) [LISTA_ID] | ε
        filhos = []
        token = self.token_atual()
        if token and token[0] == Token.VIRGULA.value:
            filhos.append(self.tratarTerminal(Token.VIRGULA))
            filhos.append(self.lista_id())
        return No("LISTA_ID'", filhos)

    def lista_func(self):
        # [LISTA_FUNC] ::= [FUNCAO] [LISTA_FUNC] | ε
        filhos = []
        token = self.token_atual()
        if token and token[0] in First.FUNCAO:
            filhos.append(self.funcao())
            filhos.append(self.lista_func())
        return No("LISTA_FUNC", filhos)

    def funcao(self):
        # [FUNCAO] ::= [NOME_FUNCAO] [BLOCO_FUNCAO]
        filhos = []
        token = self.token_atual()
        if token and token[0] in First.NOME_FUNCAO:
            filhos.append(self.nome_funcao())
            filhos.append(self.bloco_funcao())
            return No("FUNCAO", filhos)
        else:
            return self.tratarErro(follow=Follow.FUNCAO)

    def nome_funcao(self):
        # [NOME_FUNCAO] ::= (function) [ID] (() [LIST_VAR] ()) (:) [TIPO_DADO]
        filhos = []
        token = self.token_atual()
        if token and token[0] == Token.FUNCTION.value:
            filhos.append(self.tratarTerminal(Token.FUNCTION))
            filhos.append(self.tratarTerminal(Token.ID))
            filhos.append(self.tratarTerminal(Token.PARENTESES_ESQ))
            filhos.append(self.lista_var())
            filhos.append(self.tratarTerminal(Token.PARENTESES_DIR))
            filhos.append(self.tratarTerminal(Token.DOIS_PONTOS))
            filhos.append(self.tipo_dado())
            return No("NOME_FUNCAO", filhos)
        else:
            return self.tratarErro(follow=Follow.NOME_FUNCAO)

    def bloco_funcao(self):
        # [BLOCO_FUNCAO] ::= [DEF_VAR] [BLOCO] | [BLOCO]
        filhos = []
        token = self.token_atual()
        if token and token[0] in First.DEF_VAR:
            filhos.append(self.def_var())
            filhos.append(self.bloco())
            return No("BLOCO_FUNCAO", filhos)
        if token and token[0] in First.BLOCO:
            filhos.append(self.bloco())
            return No("BLOCO_FUNCAO", filhos)
        else:
            return self.tratarErro(follow=Follow.BLOCO_FUNCAO)

    def bloco(self):
        # [BLOCO] ::= (begin) [LISTA_COM] (end) | [COMANDO]
        filhos = []
        token = self.token_atual()
        if token and token[0] == Token.BEGIN.value:
            filhos.append(self.tratarTerminal(Token.BEGIN))
            filhos.append(self.lista_com())
            filhos.append(self.tratarTerminal(Token.END))
            return No("BLOCO", filhos)
        elif token and token[0] in First.COMANDO:
            filhos.append(self.comando())
            return No("BLOCO", filhos)
        else:
            return self.tratarErro(follow=Follow.BLOCO)

    def lista_com(self):
        # [LISTA_COM] ::= [COMANDO] (;) [LISTA_COM] | ε
        filhos = []
        token = self.token_atual()
        if token and token[0] in First.COMANDO:
            filhos.append(self.comando())
            filhos.append(self.tratarTerminal(Token.PONTO_VIRGULA))
            filhos.append(self.lista_com())
        return No("LISTA_COM", filhos)

    def comando(self):
        # [COMANDO] ::= [NOME] (:=) [VALOR]
        #            | (while) [EXP_LOGICA] [BLOCO]
        #            | (if) [EXP_LOGICA] (then) [BLOCO] [ELSE]
        #            | (write) [CONST_VALOR]
        #            | (read) [NOME]
        filhos = []
        token = self.token_atual()
        if token and token[0] in First.NOME:
            filhos.append(self.nome())
            filhos.append(self.tratarTerminal(Token.ATRIBUICAO))
            filhos.append(self.valor())
            return No("COMANDO", filhos)
        elif token and token[0] == Token.WHILE.value:
            filhos.append(self.tratarTerminal(Token.WHILE))
            filhos.append(self.exp_logica())
            filhos.append(self.bloco())
            return No("COMANDO", filhos)
        elif token and token[0] == Token.IF.value:
            filhos.append(self.tratarTerminal(Token.IF))
            filhos.append(self.exp_logica())
            filhos.append(self.tratarTerminal(Token.THEN))
            filhos.append(self.bloco())
            filhos.append(self.else_())
            return No("COMANDO", filhos)
        elif token and token[0] == Token.WRITE.value:
            filhos.append(self.tratarTerminal(Token.WRITE))
            filhos.append(self.const_valor())
            return No("COMANDO", filhos)
        elif token and token[0] == Token.READ.value:
            filhos.append(self.tratarTerminal(Token.READ))
            filhos.append(self.nome())
            return No("COMANDO", filhos)
        else:
             return self.tratarErro(follow=Follow.COMANDO)

    def else_(self):
        # [ELSE] ::= (else) [BLOCO] | ε
        filhos = []
        token = self.token_atual()
        if token and token[0] == Token.ELSE.value:
            filhos.append(self.tratarTerminal(Token.ELSE))
            filhos.append(self.bloco())
        return No("ELSE", filhos)

    def valor(self):
        # [VALOR] ::= [NUMERO] [EXP_MAT']
        #          | [ID] [VALOR']
        filhos = []
        token = self.token_atual()
        if token and token[0] == Token.NUMERO.value:  
            filhos.append(self.tratarTerminal(Token.NUMERO))
            filhos.append(self.exp_mat_())
            return No("VALOR", filhos)
        elif token and token[0] == Token.ID.value: 
            filhos.append(self.tratarTerminal(Token.ID)) 
            filhos.append(self.valor_())
            return No("VALOR", filhos)
        else:
            return self.tratarErro(follow=Follow.VALOR)

    def valor_(self):  
        #[VALOR'] ::= [NOME'] [EXP_MAT']
	    #          | [LISTA_PARAM] 
        #          | ε
        filhos = []
        token = self.token_atual()
        if token and (token[0] in First.NOME_ or token[0] in First.EXP_MAT_):
            filhos.append(self.nome_())
            filhos.append(self.exp_mat_())
        elif token and token[0] in First.LISTA_PARAM:
            filhos.append(self.lista_param())
        return No("VALOR'", filhos)        

    def lista_param(self):
        # [LISTA_PARAM] ::= (() [LISTA_NOME] ())
        filhos = []
        token = self.token_atual()
        if token and token[0] == Token.PARENTESES_ESQ.value:
            filhos.append(self.tratarTerminal(Token.PARENTESES_ESQ))
            filhos.append(self.lista_nome())
            filhos.append(self.tratarTerminal(Token.PARENTESES_DIR))
            return No("LISTA_PARAM", filhos)
        else:
            return self.tratarErro(follow=Follow.LISTA_PARAM)

    def lista_nome(self):
        # [LISTA_NOME] ::= [PARAMETRO] [LISTA_NOME’] | ε                             
        filhos = []
        token = self.token_atual()
        if token and token[0] in First.PARAMETRO:
            filhos.append(self.parametro())
            filhos.append(self.lista_nome_())
        return No("LISTA_NOME", filhos)

    def lista_nome_(self):
        # [LISTA_NOME’] ::= (,) [LISTA_NOME] | ε
        filhos = []
        token = self.token_atual()
        if token and token[0] == Token.VIRGULA.value:
            filhos.append(self.tratarTerminal(Token.VIRGULA))
            filhos.append(self.lista_nome())
        return No("LISTA_NOME'", filhos)

    def parametro(self):
        # [PARAMETRO] ::= [NOME] | [NUMERO]
        filhos = []
        token = self.token_atual()
        if token and token[0] in First.NOME:
            filhos.append(self.nome())
            return No("PARAMETRO", filhos)
        elif token and token[0] == Token.NUMERO.value:
            filhos.append(self.tratarTerminal(Token.NUMERO))
            return No("PARAMETRO", filhos)
        else:
            return self.tratarErro(follow=Follow.PARAMETRO)

    def exp_logica(self):
        # [EXP_LOGICA] ::= [EXP_MAT] [EXP_LOGICA’]
        filhos = []
        token = self.token_atual()
        if token and token[0] in First.EXP_MAT:
            filhos.append(self.exp_mat())
            filhos.append(self.exp_logica_())
            return No("EXP_LOGICA", filhos)
        else:
            return self.tratarErro(follow=Follow.EXP_LOGICA)

    def exp_logica_(self):
        # [EXP_LOGICA’] ::= [OP_LOGICO] [EXP_LOGICA] | ε
        filhos = []
        token = self.token_atual()
        if token and token[0] == Token.OP_LOGICO.value:
            filhos.append(self.tratarTerminal(Token.OP_LOGICO))
            filhos.append(self.exp_logica())
        return No("EXP_LOGICA'", filhos)

    def exp_mat(self):
        # [EXP_MAT] ::= [PARAMETRO] [EXP_MAT’]
        filhos = []
        token = self.token_atual()
        if token and token[0] in First.PARAMETRO:
            filhos.append(self.parametro())
            filhos.append(self.exp_mat_())
            return No("EXP_MAT", filhos)
        else:
            return self.tratarErro(follow=Follow.EXP_MAT)

    def exp_mat_(self):
        # [EXP_MAT’] ::= [OP_MAT] [EXP_MAT] | ε
        filhos = []
        token = self.token_atual()
        if token and token[0] == Token.OP_MAT.value:
            filhos.append(self.tratarTerminal(Token.OP_MAT))
            filhos.append(self.exp_mat())
        return No("EXP_MAT'", filhos)

    def nome(self):
        # [NOME] ::= [ID] [NOME’]
        filhos = []
        token = self.token_atual()
        if token and token[0] == Token.ID.value:
            filhos.append(self.tratarTerminal(Token.ID))
            filhos.append(self.nome_())
            return No("NOME", filhos)
        else:
            return self.tratarErro(follow=Follow.NOME)

    def nome_(self):
        # [NOME’] ::= (.) [NOME] | ([) [PARAMETRO] (]) | ε
        filhos = []
        token = self.token_atual()
        if token and token[0] == Token.PONTO.value:
            filhos.append(self.tratarTerminal(Token.PONTO))
            filhos.append(self.nome())
        elif token and token[0] == Token.COLCHETE_ESQ.value:
            filhos.append(self.tratarTerminal(Token.COLCHETE_ESQ))
            filhos.append(self.parametro())
            filhos.append(self.tratarTerminal(Token.COLCHETE_DIR))
        return No("NOME'", filhos)

