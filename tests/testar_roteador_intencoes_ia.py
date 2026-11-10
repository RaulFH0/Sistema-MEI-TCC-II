import pytest

from security.roteador_intencoes_ia import (
    decidir_encaminhamento,
)


@pytest.mark.parametrize(
    "intencao,destino",
    [
        ("consulta_catalogo", "consulta_catalogo"),
        ("compra", "compra_pendente_confirmacao"),
        ("esclarecimento", "solicitar_esclarecimento"),
    ],
)
def test_encaminhamento_valido(intencao, destino):
    resultado = decidir_encaminhamento({
        "intencao": intencao,
        "confianca": 0.95,
        "origem": "agente",
    })

    assert resultado["destino"] == destino
    assert resultado["autoriza_compra"] is False


@pytest.mark.parametrize(
    "origem",
    [
        "falha_classificacao",
        "baixa_confianca",
        "bloqueio_seguranca",
    ],
)
def test_origem_nao_aprovada(origem):
    resultado = decidir_encaminhamento({
        "intencao": "compra",
        "confianca": 0.99,
        "origem": origem,
    })

    assert resultado["destino"] == (
        "solicitar_esclarecimento"
    )
    assert resultado["autoriza_compra"] is False


def test_confianca_insuficiente():
    resultado = decidir_encaminhamento({
        "intencao": "compra",
        "confianca": 0.50,
        "origem": "agente",
    })

    assert resultado["destino"] == (
        "solicitar_esclarecimento"
    )


def test_intencao_desconhecida():
    resultado = decidir_encaminhamento({
        "intencao": "executar_compra",
        "confianca": 0.99,
        "origem": "agente",
    })

    assert resultado["destino"] == (
        "solicitar_esclarecimento"
    )


@pytest.mark.parametrize(
    "confianca",
    [
        None,
        True,
        float("nan"),
        float("inf"),
        -1,
        1.5,
    ],
)
def test_confianca_invalida(confianca):
    resultado = decidir_encaminhamento({
        "intencao": "compra",
        "confianca": confianca,
        "origem": "agente",
    })

    assert resultado["destino"] == (
        "solicitar_esclarecimento"
    )
    assert resultado["autoriza_compra"] is False


def test_classificacao_ausente():
    resultado = decidir_encaminhamento(None)

    assert resultado["destino"] == (
        "solicitar_esclarecimento"
    )


def test_roteador_nunca_autoriza_compra():
    exemplos = [
        {
            "intencao": "compra",
            "confianca": 1.0,
            "origem": "agente",
        },
        {
            "intencao": "consulta_catalogo",
            "confianca": 1.0,
            "origem": "agente",
        },
        {
            "intencao": "esclarecimento",
            "confianca": 1.0,
            "origem": "agente",
        },
        {},
        None,
    ]

    for classificacao in exemplos:
        resultado = decidir_encaminhamento(
            classificacao
        )

        assert resultado["autoriza_compra"] is False
