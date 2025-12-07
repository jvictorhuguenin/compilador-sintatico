from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class EntradaTabelaSimbolos:
    nome: str
    classificacao: str
    tipo: Optional[str] = None
    escopo: str = "global"
    quantidade: Optional[int] = None
    ordem: Optional[int] = None
    linha: Optional[int] = None
    metadados: Dict[str, str] = field(default_factory=dict)

    def atualizar(self, **campos):
        for chave, valor in campos.items():
            if valor is not None:
                setattr(self, chave, valor)

    def __repr__(self):
        return (
            f"EntradaTabelaSimbolos(nome={self.nome!r}, classificacao={self.classificacao!r}, "
            f"tipo={self.tipo!r}, escopo={self.escopo!r}, quantidade={self.quantidade!r}, "
            f"ordem={self.ordem!r}, linha={self.linha!r})"
        )


class TabelaSimbolos:
    """Tabela de símbolos com acesso rápido por escopo e nome."""

    def __init__(self):
        self._escopos: List[str] = ["global"]
        self._tabelas: Dict[str, Dict[str, EntradaTabelaSimbolos]] = {"global": {}}

    @property
    def escopo_atual(self) -> str:
        return self._escopos[-1]

    def entrar_escopo(self, nome: str) -> str:
        novo_escopo = self._nomear_escopo(nome)
        self._escopos.append(novo_escopo)
        self._tabelas.setdefault(novo_escopo, {})
        return novo_escopo

    def sair_escopo(self):
        if len(self._escopos) > 1:
            self._escopos.pop()

    def adicionar(self, entrada: EntradaTabelaSimbolos, escopo: Optional[str] = None) -> EntradaTabelaSimbolos:
        alvo_escopo = escopo or self.escopo_atual
        tabela = self._tabelas.setdefault(alvo_escopo, {})
        if entrada.nome not in tabela:
            entrada.escopo = alvo_escopo
            entrada.ordem = entrada.ordem or (len(tabela) + 1)
            tabela[entrada.nome] = entrada
        else:
            self.atualizar(entrada.nome, escopo=alvo_escopo, **entrada.__dict__)
        return tabela[entrada.nome]

    def atualizar(self, nome: str, escopo: Optional[str] = None, **campos):
        escopo_busca = escopo or self.escopo_atual
        entrada = self.buscar(nome, escopo_busca)
        if entrada:
            entrada.atualizar(**campos)
        return entrada

    def buscar(self, nome: str, escopo: Optional[str] = None) -> Optional[EntradaTabelaSimbolos]:
        escopo_inicial = escopo or self.escopo_atual
        for escopo_atual in self._iterar_escopos(escopo_inicial):
            tabela = self._tabelas.get(escopo_atual, {})
            if nome in tabela:
                return tabela[nome]
        return None

    def listar_escopo(self, escopo: Optional[str] = None) -> List[EntradaTabelaSimbolos]:
        return list(self._tabelas.get(escopo or self.escopo_atual, {}).values())

    def existe_no_escopo(self, nome: str, escopo: Optional[str] = None) -> bool:
        tabela = self._tabelas.get(escopo or self.escopo_atual, {})
        return nome in tabela

    def __contains__(self, nome: str) -> bool:
        return self.buscar(nome) is not None

    def _iterar_escopos(self, escopo: str):
        if escopo in self._tabelas:
            yield escopo
        partes = escopo.split(".")
        for i in range(len(partes) - 1, 0, -1):
            yield ".".join(partes[:i])
        if "global" not in self._tabelas:
            return
        if escopo != "global":
            yield "global"

    def _nomear_escopo(self, nome: str) -> str:
        if self.escopo_atual == "global":
            return nome
        return f"{self.escopo_atual}.{nome}"
