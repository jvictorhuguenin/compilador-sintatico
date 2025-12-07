import ply.lex as lex
from utils.Cor import Cor
from utils.Token import Token


class AnalisadorLexico:
    # Palavras reservadas
    palavras_reservadas = {
        'program': Token.PROGRAM.value,
        'const': Token.CONST.value,
        'type': Token.TYPE.value,
        'var': Token.VAR.value,
        'function': Token.FUNCTION.value,
        'integer': Token.INTEGER.value,
        'real': Token.REAL.value,
        'array': Token.ARRAY.value,
        'of': Token.OF.value,
        'record': Token.RECORD.value,
        'begin': Token.BEGIN.value,
        'end': Token.END.value,
        'while': Token.WHILE.value,
        'if': Token.IF.value,
        'then': Token.THEN.value,
        'else': Token.ELSE.value,
        'write': Token.WRITE.value,
        'read': Token.READ.value,
    }

    # Lista de tokens
    tokens = [
        Token.ID.value,
        Token.NUMERO.value,
        Token.STRING.value,
        Token.ATRIBUICAO.value,
        Token.DOIS_PONTOS.value,
        Token.PONTO_VIRGULA.value,
        Token.VIRGULA.value,
        Token.PONTO.value,
        Token.PARENTESES_ESQ.value,
        Token.PARENTESES_DIR.value,
        Token.COLCHETE_ESQ.value,
        Token.COLCHETE_DIR.value,
        Token.OP_LOGICO.value,
        Token.OP_MAT.value,
    ] + list(palavras_reservadas.values())

    # Regras para tokens simples
    t_ATRIBUICAO = r':='
    t_DOIS_PONTOS = r':'
    t_PONTO_VIRGULA = r';'
    t_PONTO = r'\.'
    t_VIRGULA = r','
    t_PARENTESES_ESQ = r'\('
    t_PARENTESES_DIR = r'\)'
    t_COLCHETE_ESQ = r'\['
    t_COLCHETE_DIR = r'\]'

    # Operadores
    t_OP_LOGICO = r'<|>|=|!'
    t_OP_MAT = r'[\+\-\*/]'

    # Tipos especiais
    t_STRING = r'\".*\"'  # string entre aspas
    t_NUMERO = r'\d+(\.\d+)?'

    # Identificadores e palavras reservadas
    def t_ID(self, token):
        r'[a-zA-Z_][a-zA-Z0-9_]*'
        token.type = self.palavras_reservadas.get(token.value, 'ID')
        return token

    # Comentários no formato $ ... $
    def t_COMENTARIO(self, t):
        r'\$([^$]*)\$'
        t.lexer.lineno += t.value.count("\n")
        pass

    # Contagem de linhas
    def t_newline(self, t):
        r'\n+'
        t.lexer.lineno += len(t.value)

    # Espaços em branco ignorados
    t_ignore = ' \t\r'

    # Tratamento de erro
    def t_error(self, t):
        self.erros.append((t.value[0], t.lineno))
        t.lexer.skip(1)

    # Construtor
    def __init__(self, codigo):
        self.lexo = lex.lex(module=self)
        self.erros = list()
        self.tokens = list()
        self.gerarTokens(codigo)

    # Função principal
    def gerarTokens(self, codigo):
        self.lexo.input(codigo)
        while True:
            tok = self.lexo.token()
            if not tok:
                break
            self.tokens.append((tok.type, tok.value, tok.lineno))

    # Funções auxiliares
    def printTokens(self):
        for token in self.tokens:
            print(Cor.pintar(f"{token[0]} {(20-len(token[0]))*' '} Lexema: {token[1]} {(10-len(str(token[1])))*' '} linha: {token[2]}" , Cor.VERDE))

    def printErros(self):
        for token in self.erros:
            print(Cor.pintar(f"Caracter ilegal '{token[0]}' na linha {token[1]}" , Cor.VERMELHO))
