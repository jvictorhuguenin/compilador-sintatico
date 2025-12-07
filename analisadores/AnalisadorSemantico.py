from dataclasses import dataclass
from typing import Optional

from utils.No import No
from utils.Token import Token
from utils.TabelaSimbolos import EntradaTabelaSimbolos, TabelaSimbolos


@dataclass
class ContextoSemantico:
    escopo: str = "global"
    em_declaracao: bool = False
    tipo_atual: Optional[str] = None
    classificacao_atual: Optional[str] = None
    quantidade_atual: Optional[int] = None

    def com_escopo(self, escopo: str) -> "ContextoSemantico":
        return ContextoSemantico(
            escopo=escopo,
            em_declaracao=self.em_declaracao,
            tipo_atual=self.tipo_atual,
            classificacao_atual=self.classificacao_atual,
            quantidade_atual=self.quantidade_atual,
        )

    def com_declaracao(self, em_declaracao: bool) -> "ContextoSemantico":
        return ContextoSemantico(
            escopo=self.escopo,
            em_declaracao=em_declaracao,
            tipo_atual=self.tipo_atual,
            classificacao_atual=self.classificacao_atual,
            quantidade_atual=self.quantidade_atual,
        )

    def com_tipo(self, tipo: Optional[str]) -> "ContextoSemantico":
        return ContextoSemantico(
            escopo=self.escopo,
            em_declaracao=self.em_declaracao,
            tipo_atual=tipo,
            classificacao_atual=self.classificacao_atual,
            quantidade_atual=self.quantidade_atual,
        )

    def com_classificacao(self, classificacao: Optional[str]) -> "ContextoSemantico":
        return ContextoSemantico(
            escopo=self.escopo,
            em_declaracao=self.em_declaracao,
            tipo_atual=self.tipo_atual,
            classificacao_atual=classificacao,
            quantidade_atual=self.quantidade_atual,
        )

    def com_quantidade(self, quantidade: Optional[int]) -> "ContextoSemantico":
        return ContextoSemantico(
            escopo=self.escopo,
            em_declaracao=self.em_declaracao,
            tipo_atual=self.tipo_atual,
            classificacao_atual=self.classificacao_atual,
            quantidade_atual=quantidade,
        )


class AnalisadorSemantico:
    """Percorre a árvore sintática preenchendo a tabela de símbolos."""

    NOS_DECLARACAO = {"CONSTANTE", "TIPO", "VARIAVEL", "NOME_FUNCAO"}
    NOS_TIPO_PRIMITIVO = {Token.INTEGER.value, Token.REAL.value}

    def __init__(self, arvore_sintatica: No):
        self.arvore = arvore_sintatica
        self.tabela = TabelaSimbolos()
        self.erros = []
        self._funcao_atual: Optional[str] = None
        self._escopo_pendente: Optional[str] = None
        self._definindo_parametros: bool = False
        self._ultimo_simbolo: Optional[EntradaTabelaSimbolos] = None

    def analisar(self) -> TabelaSimbolos:
        self._percorrer(self.arvore, ContextoSemantico())
        return self.tabela

    def _percorrer(self, no: No, contexto: ContextoSemantico):
        if not no:
            return

        if no.tipo == "FUNCAO":
            cabecalho = no.filhos[0] if no.filhos else None
            self._registrar_funcao_cabecalho(cabecalho)

        entrou_escopo = False
        escopo_anterior = self.tabela.escopo_atual
        funcao_anterior = self._funcao_atual
        definindo_parametros_anterior = self._definindo_parametros

        if self._abre_escopo(no):
            nome_escopo = self._nome_escopo(no)
            self.tabela.entrar_escopo(nome_escopo)
            contexto = contexto.com_escopo(self.tabela.escopo_atual)
            entrou_escopo = True
            if no.tipo == "FUNCAO":
                self._funcao_atual = self._escopo_pendente or nome_escopo
                self._definindo_parametros = True
            else:
                self._definindo_parametros = False

        contexto_declaracao = self._ajustar_contexto(no, contexto)

        for filho in no.filhos:
            self._percorrer(filho, contexto_declaracao)

        self._processar_no(no, contexto_declaracao)

        if entrou_escopo:
            self.tabela.sair_escopo()
            self._funcao_atual = funcao_anterior
            self._definindo_parametros = definindo_parametros_anterior

        self._escopo_pendente = None

    def _nome_escopo(self, no: No) -> str:
        if no.tipo in {"FUNCAO", "NOME_FUNCAO"}:
            return self._escopo_pendente or "funcao"
        if no.tipo == "PROGRAMA":
            nome = self._buscar_primeiro_id(no)
            return nome or "programa"
        return no.valor or no.tipo.lower()

    def _registrar_funcao_cabecalho(self, no: No):
        nome = self._buscar_primeiro_id(no)
        if not nome:
            return
        self._escopo_pendente = nome
        if self.tabela.existe_no_escopo(nome):
            self._registrar_erro(f"Identificador '{nome}' já declarado no escopo '{self.tabela.escopo_atual}'.", no)
            return
        entrada = EntradaTabelaSimbolos(
            nome=nome,
            classificacao="funcao",
            metadados={"parametros": []},
        )
        self.tabela.adicionar(entrada, escopo=self.tabela.escopo_atual)

    def _ajustar_contexto(self, no: No, contexto: ContextoSemantico) -> ContextoSemantico:
        em_declaracao = contexto.em_declaracao or no.tipo in self.NOS_DECLARACAO
        novo_contexto = contexto.com_declaracao(em_declaracao)

        if no.tipo in self.NOS_TIPO_PRIMITIVO:
            novo_contexto = novo_contexto.com_tipo(no.tipo.lower())

        if no.tipo == "FUNCTION":
            novo_contexto = novo_contexto.com_classificacao("funcao")
        elif no.tipo == "PARAMETRO":
            novo_contexto = novo_contexto.com_classificacao("parametro")
        elif no.tipo == "LISTA_VAR" or no.tipo == "DEF_VAR":
            novo_contexto = novo_contexto.com_classificacao("variavel")

        return novo_contexto

    def _processar_no(self, no: No, contexto: ContextoSemantico):
        if no.tipo == "CONSTANTE":
            self._processar_constante(no)
        elif no.tipo == "TIPO_DADO":
            no.tipo_inferido = self._tipo_do_dado(no)
        elif no.tipo == "TIPO":
            self._processar_tipo(no)
        elif no.tipo == "VARIAVEL":
            self._processar_variavel(no)
        elif no.tipo == "NOME_FUNCAO":
            self._processar_nome_funcao(no)
            self._definindo_parametros = False
        elif no.tipo == "COMANDO":
            self._processar_comando(no)
        elif no.tipo == "VALOR":
            no.tipo_inferido = self._avaliar_valor(no)
        elif no.tipo == "LISTA_NOME":
            no.argumentos = self._coletar_argumentos(no)
        elif no.tipo == "EXP_LOGICA":
            no.tipo_inferido = self._avaliar_exp_logica(no)
        elif no.tipo == "EXP_MAT":
            no.tipo_inferido = self._avaliar_exp_mat(no)
        elif no.tipo == "NOME":
            no.tipo_inferido = self._avaliar_nome(no)

    def _processar_constante(self, no: No):
        identificador = self._buscar_primeiro_id(no)
        if not identificador:
            return
        if self.tabela.existe_no_escopo(identificador):
            self._registrar_erro(f"Identificador '{identificador}' já declarado no escopo '{self.tabela.escopo_atual}'.", no)
            return
        tipo_valor = None
        if no.filhos:
            const_valor = no.filhos[2] if len(no.filhos) > 2 else None
            if const_valor:
                tipo_valor = getattr(const_valor, "tipo_inferido", None) or (
                    "string" if const_valor.tipo == Token.STRING.value else "integer"
                )

        entrada = EntradaTabelaSimbolos(
            nome=identificador,
            classificacao="constante",
            tipo=tipo_valor,
            escopo=self.tabela.escopo_atual,
        )
        self.tabela.adicionar(entrada)

    def _processar_tipo(self, no: No):
        identificador = self._buscar_primeiro_id(no)
        if not identificador:
            return
        if self.tabela.existe_no_escopo(identificador):
            self._registrar_erro(f"Identificador '{identificador}' já declarado no escopo '{self.tabela.escopo_atual}'.", no)
            return
        tipo_dado = no.filhos[-1]
        tipo = getattr(tipo_dado, "tipo_inferido", None)
        entrada = EntradaTabelaSimbolos(
            nome=identificador,
            classificacao="tipo",
            tipo=tipo,
            escopo=self.tabela.escopo_atual,
        )
        self.tabela.adicionar(entrada)

    def _processar_variavel(self, no: No):
        if len(no.filhos) < 3:
            return
        lista_id_no = no.filhos[0]
        tipo_no = no.filhos[2]
        tipo = getattr(tipo_no, "tipo_inferido", None)
        ids = self._coletar_ids(lista_id_no)
        for identificador in ids:
            if self.tabela.existe_no_escopo(identificador):
                self._registrar_erro(
                    f"Identificador '{identificador}' já declarado no escopo '{self.tabela.escopo_atual}'.",
                    no,
                )
                continue
            classificacao = "parametro" if self._definindo_parametros else "variavel"
            entrada = EntradaTabelaSimbolos(
                nome=identificador,
                classificacao=classificacao,
                tipo=tipo,
                escopo=self.tabela.escopo_atual,
            )
            self.tabela.adicionar(entrada)
            if self._funcao_atual and classificacao == "parametro":
                funcao = self.tabela.buscar(self._funcao_atual, escopo=self._escopo_pai())
                if funcao:
                    funcao.metadados.setdefault("parametros", []).append({"nome": identificador, "tipo": tipo})

    def _processar_nome_funcao(self, no: No):
        nome = self._buscar_primeiro_id(no)
        retorno_no = no.filhos[-1] if no.filhos else None
        tipo_retorno = getattr(retorno_no, "tipo_inferido", None)
        entrada = self.tabela.buscar(nome, escopo=self._escopo_pai())
        if entrada:
            entrada.tipo = tipo_retorno
            entrada.metadados.setdefault("parametros", [])
            if not self.tabela.existe_no_escopo("result"):
                self.tabela.adicionar(
                    EntradaTabelaSimbolos(
                        nome="result",
                        classificacao="variavel",
                        tipo=tipo_retorno,
                        escopo=self.tabela.escopo_atual,
                    )
                )

    def _processar_comando(self, no: No):
        if not no.filhos:
            return
        primeiro = no.filhos[0]
        if primeiro.tipo == "NOME":
            alvo_tipo = self._avaliar_nome(primeiro)
            valor_no = no.filhos[2] if len(no.filhos) > 2 else None
            valor_tipo = self._avaliar_valor(valor_no) if valor_no else None
            if not self._verificar_declaracao_nome(primeiro):
                return
            if valor_tipo and alvo_tipo and valor_tipo != alvo_tipo:
                self._registrar_erro(
                    f"Tipos incompatíveis na atribuição: '{alvo_tipo}' e '{valor_tipo}'.",
                    no,
                )
            primeiro_id = self._buscar_primeiro_id(primeiro)
            if self._funcao_atual and (self._nome_igual_funcao(primeiro) or primeiro_id == "result"):
                funcao = self.tabela.buscar(self._funcao_atual, escopo=self._escopo_pai())
                if funcao and funcao.tipo and funcao.tipo != valor_tipo:
                    self._registrar_erro(
                        f"Tipo de retorno '{valor_tipo}' difere do tipo da função '{funcao.tipo}'.",
                        no,
                    )
        elif primeiro.tipo in {Token.WHILE.value, Token.IF.value} and len(no.filhos) >= 2:
            condicao = no.filhos[1]
            self._avaliar_exp_logica(condicao)

    def _avaliar_valor(self, no: Optional[No]):
        if not no or not no.filhos:
            return None
        primeiro = no.filhos[0]
        if primeiro.tipo == Token.NUMERO.value:
            return "integer"
        if primeiro.tipo == Token.ID.value:
            identificador = primeiro.valor
            valor_no = no.filhos[1] if len(no.filhos) > 1 else None
            if valor_no and valor_no.filhos and valor_no.filhos[0].tipo == "LISTA_PARAM":
                return self._avaliar_chamada_funcao(identificador, valor_no.filhos[0])
            nome_no = No("NOME", [primeiro] + ([valor_no] if valor_no else []))
            return self._avaliar_nome(nome_no)
        return None

    def _avaliar_chamada_funcao(self, identificador: str, lista_param_no: No):
        entrada = self.tabela.buscar(identificador)
        if not entrada:
            self._registrar_erro(f"Identificador '{identificador}' não declarado antes do uso.", lista_param_no)
            return None
        if entrada.classificacao != "funcao":
            self._registrar_erro(f"'{identificador}' não é uma função para receber parâmetros.", lista_param_no)
            return entrada.tipo

        parametros_declarados = entrada.metadados.get("parametros", [])
        argumentos = self._coletar_argumentos(lista_param_no.filhos[1] if len(lista_param_no.filhos) > 1 else None)
        if argumentos is None:
            argumentos = []
        if len(argumentos) != len(parametros_declarados):
            self._registrar_erro(
                f"Quantidade de parâmetros incompatível em '{identificador}': esperado {len(parametros_declarados)}, recebido {len(argumentos)}.",
                lista_param_no,
            )
        else:
            for idx, (arg, decl) in enumerate(zip(argumentos, parametros_declarados)):
                if arg != decl.get("tipo"):
                    self._registrar_erro(
                        f"Tipo do argumento {idx + 1} incompatível em '{identificador}': esperado '{decl.get('tipo')}', recebido '{arg}'.",
                        lista_param_no,
                    )
        return entrada.tipo

    def _avaliar_exp_logica(self, no: Optional[No]):
        if not no or not no.filhos:
            return None
        esquerda = no.filhos[0]
        tipo_esquerda = self._avaliar_exp_mat(esquerda)
        if len(no.filhos) > 1 and no.filhos[1].filhos:
            direita = no.filhos[1].filhos[1]
            tipo_direita = self._avaliar_exp_logica(direita)
            if tipo_esquerda and tipo_direita and tipo_esquerda != tipo_direita:
                self._registrar_erro("Expressão lógica com tipos incompatíveis.", no)
        no.tipo_inferido = tipo_esquerda
        return tipo_esquerda

    def _avaliar_exp_mat(self, no: Optional[No]):
        if not no or not no.filhos:
            return None
        parametro = no.filhos[0]
        tipo_parametro = None
        if parametro.tipo == "PARAMETRO":
            tipo_parametro = self._avaliar_parametro(parametro)
        if len(no.filhos) > 1 and no.filhos[1].filhos:
            prox = no.filhos[1].filhos[1]
            tipo_prox = self._avaliar_exp_mat(prox)
            if tipo_parametro and tipo_prox and tipo_parametro != tipo_prox:
                self._registrar_erro("Operação matemática com tipos incompatíveis.", no)
        no.tipo_inferido = tipo_parametro
        return tipo_parametro

    def _avaliar_parametro(self, no: No):
        if not no.filhos:
            return None
        filho = no.filhos[0]
        if filho.tipo == "NOME":
            return self._avaliar_nome(filho)
        if filho.tipo == Token.NUMERO.value:
            return "integer"
        return None

    def _avaliar_nome(self, no: No):
        if not no.filhos:
            return None
        identificador = no.filhos[0].valor
        entrada = self.tabela.buscar(identificador)
        if not entrada:
            self._registrar_erro(f"Identificador '{identificador}' não declarado antes do uso.", no)
            return None
        tipo_atual = entrada.tipo
        restante = no.filhos[1] if len(no.filhos) > 1 else None
        if restante and restante.filhos:
            filho = restante.filhos[0]
            conteudo = filho.filhos[0] if filho.tipo == "NOME'" and filho.filhos else filho
            parametro_no = (
                filho.filhos[1]
                if filho.tipo == "NOME'" and len(filho.filhos) > 1
                else (restante.filhos[1] if len(restante.filhos) > 1 else None)
            )
            if conteudo.tipo == Token.PONTO.value:
                membro_no = parametro_no
                if not self._eh_record(tipo_atual):
                    self._registrar_erro("Acesso de membro apenas permitido para tipos classe/record.", no)
                    return tipo_atual
                membro_nome = self._buscar_primeiro_id(membro_no)
                campos = tipo_atual.get("campos", {}) if isinstance(tipo_atual, dict) else {}
                if membro_nome not in campos:
                    self._registrar_erro(f"Membro '{membro_nome}' não declarado no tipo.", no)
                    return None
                tipo_atual = campos[membro_nome]
            elif conteudo.tipo == Token.COLCHETE_ESQ.value:
                if not self._eh_array(tipo_atual):
                    self._registrar_erro("Índice só pode ser usado em variáveis do tipo vetor.", no)
                    return tipo_atual
                parametro = parametro_no
                self._avaliar_parametro(parametro)
                tipo_atual = tipo_atual.get("tipo") if isinstance(tipo_atual, dict) else None
        return tipo_atual

    def _coletar_argumentos(self, no: Optional[No]):
        if not no:
            return []
        argumentos = []
        if no.tipo == "LISTA_NOME" and no.filhos:
            parametro_no = no.filhos[0]
            if parametro_no.tipo == "PARAMETRO":
                argumentos.append(self._avaliar_parametro(parametro_no))
            if len(no.filhos) > 1:
                proximo = no.filhos[1].filhos[1] if no.filhos[1].filhos else None
                argumentos.extend(self._coletar_argumentos(proximo))
        return argumentos

    def _tipo_do_dado(self, no: No):
        if not no.filhos:
            return None
        primeiro = no.filhos[0]
        if primeiro.tipo == Token.INTEGER.value:
            return "integer"
        if primeiro.tipo == Token.REAL.value:
            return "real"
        if primeiro.tipo == Token.ARRAY.value:
            tamanho_no = no.filhos[2]
            base_no = no.filhos[-1]
            base_tipo = getattr(base_no, "tipo_inferido", None) or self._tipo_do_dado(base_no)
            tamanho = tamanho_no.valor if tamanho_no else None
            return {"categoria": "array", "tipo": base_tipo, "tamanho": tamanho}
        if primeiro.tipo == Token.RECORD.value:
            campos = {}
            lista_var_no = no.filhos[1]
            for variavel_no in lista_var_no.filhos:
                if variavel_no.tipo == "VARIAVEL":
                    tipo_campo = getattr(variavel_no.filhos[2], "tipo_inferido", None)
                    for nome_campo in self._coletar_ids(variavel_no.filhos[0]):
                        campos[nome_campo] = tipo_campo
            return {"categoria": "record", "campos": campos}
        if primeiro.tipo == Token.ID.value:
            entrada = self.tabela.buscar(primeiro.valor)
            if not entrada:
                self._registrar_erro(f"Identificador '{primeiro.valor}' não declarado antes do uso.", no)
                return None
            return entrada.tipo
        return None

    def _coletar_ids(self, no: Optional[No]):
        if not no:
            return []
        ids = []
        if no.tipo == Token.ID.value:
            ids.append(no.valor)
        for filho in no.filhos:
            ids.extend(self._coletar_ids(filho))
        return ids

    def _buscar_primeiro_id(self, no: Optional[No]):
        if not no:
            return None
        if no.tipo == Token.ID.value:
            return no.valor
        for filho in no.filhos:
            encontrado = self._buscar_primeiro_id(filho)
            if encontrado:
                return encontrado
        return None

    def _registrar_erro(self, mensagem: str, no: Optional[No]):
        self.erros.append(mensagem)

    def _eh_array(self, tipo):
        return isinstance(tipo, dict) and tipo.get("categoria") == "array"

    def _eh_record(self, tipo):
        return isinstance(tipo, dict) and tipo.get("categoria") == "record"

    def _escopo_pai(self):
        atual = self.tabela.escopo_atual
        if "." in atual:
            return atual.rsplit(".", 1)[0]
        return "global"

    def _verificar_declaracao_nome(self, nome_no: No) -> bool:
        identificador = self._buscar_primeiro_id(nome_no)
        if not identificador:
            return False
        if not self.tabela.buscar(identificador):
            self._registrar_erro(f"Identificador '{identificador}' não declarado antes do uso.", nome_no)
            return False
        return True

    def _nome_igual_funcao(self, nome_no: No) -> bool:
        identificador = self._buscar_primeiro_id(nome_no)
        return identificador == self._funcao_atual

    def _abre_escopo(self, no: No) -> bool:
        return no.tipo in {"PROGRAMA", "FUNCAO"}
