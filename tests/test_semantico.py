import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMPILADOR = ROOT / "compilador.py"


def executar_compilador(arquivo: str):
    caminho = Path(arquivo)
    if not caminho.is_absolute():
        caminho = ROOT / "tests" / caminho
    return subprocess.run(
        [sys.executable, str(COMPILADOR), str(caminho)],
        capture_output=True,
        text=True,
        cwd=ROOT,
    )


def test_programa_correto_nao_retorna_erros_semanticos():
    resultado = subprocess.run(
        [sys.executable, str(COMPILADOR), str(ROOT / "programaCerto.txt")],
        capture_output=True,
        text=True,
        cwd=ROOT,
    )
    assert resultado.returncode == 0
    assert "Erros semânticos" not in resultado.stdout


def test_variavel_duplicada_mesmo_escopo():
    resultado = executar_compilador("variavelDuplicada.txt")
    assert resultado.returncode != 0
    assert "Identificador 'a' já declarado" in resultado.stdout


def test_uso_de_variavel_sem_declaracao_previa():
    resultado = executar_compilador("usoAntesDeclaracao.txt")
    assert resultado.returncode != 0
    assert "Identificador 'a' não declarado antes do uso." in resultado.stdout


def test_atribuicao_com_tipos_diferentes():
    resultado = executar_compilador("atribuicaoTiposDiferentes.txt")
    assert resultado.returncode != 0
    assert "Tipos incompatíveis na atribuição: 'integer' e 'real'." in resultado.stdout


def test_chamada_de_parametros_em_identificador_nao_funcao():
    resultado = executar_compilador("chamadaNaoFuncao.txt")
    assert resultado.returncode != 0
    assert "'a' não é uma função para receber parâmetros." in resultado.stdout


def test_quantidade_de_parametros_incorreta_em_funcao():
    resultado = executar_compilador("quantidadeParametros.txt")
    assert resultado.returncode != 0
    assert "Quantidade de parâmetros incompatível em 'identidade': esperado 1, recebido 2." in resultado.stdout


def test_tipo_de_argumento_incorreto_em_funcao():
    resultado = executar_compilador("tipoArgumentos.txt")
    assert resultado.returncode != 0
    assert "Tipo do argumento 1 incompatível em 'identidade': esperado 'integer', recebido 'real'." in resultado.stdout


def test_tipo_de_retorno_incompativel():
    resultado = executar_compilador("retornoTipoIncorreto.txt")
    assert resultado.returncode != 0
    assert "Tipo de retorno 'real' difere do tipo da função 'integer'." in resultado.stdout


def test_uso_de_indice_em_variavel_nao_vetor():
    resultado = executar_compilador("indiceNaoVetor.txt")
    assert resultado.returncode != 0
    assert "Índice só pode ser usado em variáveis do tipo vetor." in resultado.stdout


def test_acesso_de_membro_em_tipo_nao_record():
    resultado = executar_compilador("membroEmNaoClasse.txt")
    assert resultado.returncode != 0
    assert "Acesso de membro apenas permitido para tipos classe/record." in resultado.stdout


def test_acesso_a_membro_nao_declarado():
    resultado = executar_compilador("membroNaoDeclarado.txt")
    assert resultado.returncode != 0
    assert "Membro 'idade' não declarado no tipo." in resultado.stdout
