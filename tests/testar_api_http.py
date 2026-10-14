
import pytest

from fastapi.testclient import TestClient

import main


client = TestClient(main.app)

CHAVE = "teste-http-automatizado-001"

MENSAGEM = {
    "mensagem": (
        "Sou Pedro e quero comprar 1 pacote de Arroz."
    )
}


def resposta_compra(repetida=False):
    return {
        "sucesso": True,
        "tempo_ms": 10,
        "resultado": {
            "pedido_confirmado": True,
            "compra_id": 123,
            "cliente_nome": "Pedro",
            "itens": [
                {
                    "produto_nome": "Arroz",
                    "quantidade": 1,
                    "preco_unitario": 25.0,
                    "subtotal": 25.0
                }
            ],
            "valor_total": 25.0,
            "requisicao_repetida": repetida
        }
    }


def enviar(chave=CHAVE, mensagem=None):
    return client.post(
        "/atender",
        json=mensagem if mensagem is not None else MENSAGEM,
        headers={"Idempotency-Key": chave}
    )


def test_compra_nova_http_200(monkeypatch):
    def simular_orquestrador(
        mensagem_usuario,
        chave_idempotencia
    ):
        assert mensagem_usuario == MENSAGEM["mensagem"]
        assert chave_idempotencia == CHAVE
        return resposta_compra(repetida=False)

    monkeypatch.setattr(
        main,
        "processar_pedido",
        simular_orquestrador
    )

    resposta = enviar()

    assert resposta.status_code == 200

    dados = resposta.json()

    assert dados["sucesso"] is True
    assert dados["acao_executada"] == "pedido_confirmado"
    assert dados["dados"]["pedido"]["compra_id"] == 123
    assert dados["dados"]["pedido"]["valor_total"] == 25.0

    print("\nTESTE HTTP 200 - COMPRA NOVA: APROVADO!")


def test_compra_repetida_http_200(monkeypatch):
    monkeypatch.setattr(
        main,
        "processar_pedido",
        lambda **kwargs: resposta_compra(repetida=True)
    )

    resposta = enviar()

    assert resposta.status_code == 200

    dados = resposta.json()

    assert dados["sucesso"] is True
    assert dados["acao_executada"] == "pedido_repetido"
    assert dados["dados"]["pedido"]["requisicao_repetida"]

    print("\nTESTE HTTP 200 - REENVIO: APROVADO!")


def test_conflito_http_409(monkeypatch):
    monkeypatch.setattr(
        main,
        "processar_pedido",
        lambda **kwargs: {
            "sucesso": False,
            "tempo_ms": 5,
            "erro": (
                "Chave de idempotencia utilizada "
                "com mensagem diferente."
            )
        }
    )

    resposta = enviar()

    assert resposta.status_code == 409

    dados = resposta.json()["detail"]

    assert dados["sucesso"] is False
    assert dados["acao_executada"] == "pedido_nao_confirmado"
    assert "mensagem diferente" in dados["mensagem"]

    print("\nTESTE HTTP 409 - CONFLITO: APROVADO!")


def test_validacao_http_422(monkeypatch):
    def nao_deveria_executar(**kwargs):
        raise AssertionError(
            "Orquestrador nao deveria ser chamado."
        )

    monkeypatch.setattr(
        main,
        "processar_pedido",
        nao_deveria_executar
    )

    resposta = client.post(
        "/atender",
        json=MENSAGEM
        # Cabecalho obrigatorio ausente
    )

    assert resposta.status_code == 422

    print("\nTESTE HTTP 422 - VALIDACAO: APROVADO!")


def test_erro_interno_http_500(monkeypatch):
    monkeypatch.setattr(
        main,
        "processar_pedido",
        lambda **kwargs: {
            "sucesso": False,
            "tempo_ms": 7,
            "erro": "Falha interna simulada."
        }
    )

    resposta = enviar()

    assert resposta.status_code == 500

    dados = resposta.json()["detail"]

    assert dados["sucesso"] is False
    assert dados["mensagem"] == (
        "Erro interno ao processar o atendimento."
    )

    print("\nTESTE HTTP 500 - ERRO INTERNO: APROVADO!")


def test_excecao_inesperada_http_500(monkeypatch):
    def simular_falha(**kwargs):
        raise RuntimeError("Erro interno de teste.")

    monkeypatch.setattr(
        main,
        "processar_pedido",
        simular_falha
    )

    resposta = enviar()

    assert resposta.status_code == 500
    assert "Erro interno" in resposta.json()["detail"]

    print("\nTESTE HTTP 500 - EXCECAO: APROVADO!")


def test_rota_saude():
    resposta = client.get("/")

    assert resposta.status_code == 200
    assert resposta.json()["status"] == "online"

    print("\nTESTE ROTA DE SAUDE: APROVADO!")
