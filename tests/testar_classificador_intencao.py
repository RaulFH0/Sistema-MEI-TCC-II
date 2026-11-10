import json

import pytest

from agents.classificador_intencao import (
    classificar_intencao,
)


def simular(intencao, confianca):
    return lambda mensagem: json.dumps({
        "intencao": intencao,
        "confianca": confianca,
    })


def test_consulta_catalogo():
    resultado = classificar_intencao(
        "Quais produtos estao disponiveis?",
        executor=simular("consulta_catalogo", 0.98),
    )

    assert resultado["intencao"] == "consulta_catalogo"
    assert resultado["origem"] == "agente"


def test_compra():
    resultado = classificar_intencao(
        "Quero comprar dois cadernos.",
        executor=simular("compra", 0.97),
    )

    assert resultado["intencao"] == "compra"


def test_esclarecimento():
    resultado = classificar_intencao(
        "Preciso de ajuda.",
        executor=simular("esclarecimento", 0.95),
    )

    assert resultado["intencao"] == "esclarecimento"


def test_baixa_confianca():
    resultado = classificar_intencao(
        "Mensagem ambigua",
        executor=simular("compra", 0.54),
    )

    assert resultado["intencao"] == "esclarecimento"
    assert resultado["origem"] == "baixa_confianca"


def test_json_invalido():
    resultado = classificar_intencao(
        "Ola",
        executor=lambda mensagem: "resposta invalida",
    )

    assert resultado["intencao"] == "esclarecimento"
    assert resultado["origem"] == "falha_classificacao"


def test_categoria_desconhecida():
    resultado = classificar_intencao(
        "Ola",
        executor=simular("cancelamento", 0.99),
    )

    assert resultado["intencao"] == "esclarecimento"


def test_falha_do_provedor():
    def falhar(mensagem):
        raise RuntimeError("Servico indisponivel")

    resultado = classificar_intencao(
        "Quero comprar",
        executor=falhar,
    )

    assert resultado["intencao"] == "esclarecimento"
    assert resultado["confianca"] == 0.0


@pytest.mark.parametrize(
    "valor",
    [-1, 1.5, True, None, float("nan")],
)
def test_confianca_invalida(valor):
    resultado = classificar_intencao(
        "Teste",
        executor=simular("compra", valor),
    )

    assert resultado["intencao"] == "esclarecimento"
    assert resultado["origem"] == "falha_classificacao"


@pytest.mark.parametrize("mensagem", ["", "   ", None])
def test_mensagem_invalida(mensagem):
    with pytest.raises(ValueError):
        classificar_intencao(
            mensagem,
            executor=simular("compra", 0.99),
        )
