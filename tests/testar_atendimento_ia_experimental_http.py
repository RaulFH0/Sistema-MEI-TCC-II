from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from main import app
from database.models import get_db

import security.atendimento_ia_experimental_routes as rotas


@pytest.fixture
def cliente(monkeypatch):
    monkeypatch.delenv(
        "MEI_ATENDIMENTO_IA_EXPERIMENTAL",
        raising=False,
    )
    monkeypatch.setenv(
        "MEI_ATENDIMENTO_IA_EXPERIMENTAL_KEY",
        "chave-exclusiva-de-teste-" + "x" * 40,
    )

    def banco_simulado():
        yield object()

    anterior = dict(app.dependency_overrides)
    app.dependency_overrides[get_db] = banco_simulado

    with TestClient(
        app,
        raise_server_exceptions=False,
    ) as http:
        yield http

    app.dependency_overrides.clear()
    app.dependency_overrides.update(anterior)


def enviar(cliente, slug="loja-a"):
    return cliente.post(
        f"/lojas/{slug}/atendimento-experimental",
        json={"mensagem": "Quais produtos existem?"},
        headers={
            "X-MEI-Experimental-Key":
                "chave-exclusiva-de-teste-" + "x" * 40
        },
    )


def resposta_segura(acao="consulta_catalogo"):
    return {
        "resposta": "Resposta de teste.",
        "acao_executada": acao,
        "sucesso": True,
        "dados": {
            "compra_registrada": False,
            "tempo_ms": 1.0,
        },
    }


def test_rota_desativada_por_padrao(
    cliente, monkeypatch
):
    def proibido(*args, **kwargs):
        raise AssertionError(
            "Nao deveria resolver loja"
        )

    monkeypatch.setattr(
        rotas, "_resolver_loja", proibido
    )

    resposta = enviar(cliente)
    assert resposta.status_code == 404


def test_consulta_recebe_id_da_loja(
    cliente, monkeypatch
):
    monkeypatch.setenv(
        "MEI_ATENDIMENTO_IA_EXPERIMENTAL", "1"
    )

    chamadas = []

    monkeypatch.setattr(
        rotas,
        "_resolver_loja",
        lambda db, slug: SimpleNamespace(id=7),
    )

    def atendimento(db, loja, mensagem):
        chamadas.append((loja, mensagem))
        return resposta_segura()

    monkeypatch.setattr(
        rotas,
        "atender_multiintencao",
        atendimento,
    )

    resposta = enviar(cliente)

    assert resposta.status_code == 200
    assert chamadas == [
        (7, "Quais produtos existem?")
    ]
    assert resposta.json()["dados"][
        "compra_registrada"
    ] is False


def test_duas_lojas_isoladas(
    cliente, monkeypatch
):
    monkeypatch.setenv(
        "MEI_ATENDIMENTO_IA_EXPERIMENTAL", "1"
    )

    ids = {"loja-a": 7, "loja-b": 8}

    def resolver(db, slug):
        return SimpleNamespace(id=ids[slug])

    def atender(db, estabelecimento_id, mensagem):
        resultado = resposta_segura()
        resultado["resposta"] = (
            f"Loja {estabelecimento_id}"
        )
        return resultado

    monkeypatch.setattr(
        rotas, "_resolver_loja", resolver
    )
    monkeypatch.setattr(
        rotas, "atender_multiintencao", atender
    )

    a = enviar(cliente, "loja-a")
    b = enviar(cliente, "loja-b")

    assert a.status_code == 200
    assert b.status_code == 200
    assert a.json()["resposta"] == "Loja 7"
    assert b.json()["resposta"] == "Loja 8"


def test_loja_inexistente(
    cliente, monkeypatch
):
    monkeypatch.setenv(
        "MEI_ATENDIMENTO_IA_EXPERIMENTAL", "1"
    )

    def nao_encontrada(db, slug):
        raise HTTPException(
            status_code=404,
            detail="Loja nao encontrada.",
        )

    monkeypatch.setattr(
        rotas, "_resolver_loja", nao_encontrada
    )

    resposta = enviar(cliente, "inexistente")
    assert resposta.status_code == 404


def test_compra_pendente_nao_e_confirmacao(
    cliente, monkeypatch
):
    monkeypatch.setenv(
        "MEI_ATENDIMENTO_IA_EXPERIMENTAL", "1"
    )
    monkeypatch.setattr(
        rotas,
        "_resolver_loja",
        lambda db, slug: SimpleNamespace(id=3),
    )
    monkeypatch.setattr(
        rotas,
        "atender_multiintencao",
        lambda db, loja, mensagem: resposta_segura(
            "compra_pendente_confirmacao"
        ),
    )

    resposta = enviar(cliente)

    assert resposta.status_code == 200
    assert resposta.json()["acao_executada"] == (
        "compra_pendente_confirmacao"
    )
    assert resposta.json()["dados"][
        "compra_registrada"
    ] is False


def test_confirmacao_indevida_rejeitada(
    cliente, monkeypatch
):
    monkeypatch.setenv(
        "MEI_ATENDIMENTO_IA_EXPERIMENTAL", "1"
    )
    monkeypatch.setattr(
        rotas,
        "_resolver_loja",
        lambda db, slug: SimpleNamespace(id=3),
    )
    monkeypatch.setattr(
        rotas,
        "atender_multiintencao",
        lambda db, loja, mensagem: resposta_segura(
            "pedido_confirmado"
        ),
    )

    resposta = enviar(cliente)
    assert resposta.status_code == 503


def test_falha_interna_sem_expor_detalhes(
    cliente, monkeypatch
):
    monkeypatch.setenv(
        "MEI_ATENDIMENTO_IA_EXPERIMENTAL", "1"
    )
    monkeypatch.setattr(
        rotas,
        "_resolver_loja",
        lambda db, slug: SimpleNamespace(id=3),
    )

    def falhar(*args):
        raise RuntimeError("Dado interno sigiloso")

    monkeypatch.setattr(
        rotas,
        "atender_multiintencao",
        falhar,
    )

    resposta = enviar(cliente)

    assert resposta.status_code == 503
    assert "Dado interno sigiloso" not in resposta.text


def test_chave_ausente_bloqueada(
    cliente, monkeypatch
):
    monkeypatch.setenv(
        "MEI_ATENDIMENTO_IA_EXPERIMENTAL", "1"
    )

    resposta = cliente.post(
        "/lojas/loja-a/atendimento-experimental",
        json={"mensagem": "Ola"},
    )

    assert resposta.status_code == 403


def test_chave_incorreta_bloqueada(
    cliente, monkeypatch
):
    monkeypatch.setenv(
        "MEI_ATENDIMENTO_IA_EXPERIMENTAL", "1"
    )

    resposta = cliente.post(
        "/lojas/loja-a/atendimento-experimental",
        json={"mensagem": "Ola"},
        headers={
            "X-MEI-Experimental-Key": "chave-incorreta"
        },
    )

    assert resposta.status_code == 403


def test_sem_chave_configurada_falha_fechado(
    cliente, monkeypatch
):
    monkeypatch.setenv(
        "MEI_ATENDIMENTO_IA_EXPERIMENTAL", "1"
    )
    monkeypatch.delenv(
        "MEI_ATENDIMENTO_IA_EXPERIMENTAL_KEY",
        raising=False,
    )

    resposta = enviar(cliente)

    assert resposta.status_code == 404


def test_chave_curta_rejeitada(
    cliente, monkeypatch
):
    monkeypatch.setenv(
        "MEI_ATENDIMENTO_IA_EXPERIMENTAL", "1"
    )
    monkeypatch.setenv(
        "MEI_ATENDIMENTO_IA_EXPERIMENTAL_KEY",
        "curta",
    )

    resposta = enviar(cliente)

    assert resposta.status_code == 404


@pytest.fixture(autouse=True)
def limpar_limite_ia():
    from security.limite_atendimento_ia import (
        limitador_atendimento_ia,
    )
    limitador_atendimento_ia.limpar_para_testes()


def configurar_resposta_valida(monkeypatch):
    from types import SimpleNamespace

    monkeypatch.setenv(
        "MEI_ATENDIMENTO_IA_EXPERIMENTAL", "1"
    )
    monkeypatch.setattr(
        rotas,
        "_resolver_loja",
        lambda db, slug: SimpleNamespace(id=7),
    )
    monkeypatch.setattr(
        rotas,
        "atender_multiintencao",
        lambda db, loja, mensagem: resposta_segura(),
    )


def test_sexta_requisicao_retorna_429(
    cliente, monkeypatch
):
    configurar_resposta_valida(monkeypatch)

    for _ in range(5):
        resposta = enviar(cliente)
        assert resposta.status_code == 200

    bloqueada = enviar(cliente)

    assert bloqueada.status_code == 429
    assert int(bloqueada.headers["Retry-After"]) >= 1


def test_limite_compartilhado_entre_lojas(
    cliente, monkeypatch
):
    configurar_resposta_valida(monkeypatch)

    for _ in range(3):
        assert enviar(cliente, "loja-a").status_code == 200

    for _ in range(2):
        assert enviar(cliente, "loja-b").status_code == 200

    assert enviar(cliente, "loja-b").status_code == 429


def test_chave_invalida_nao_consume_cota(
    cliente, monkeypatch
):
    configurar_resposta_valida(monkeypatch)

    sem_chave = cliente.post(
        "/lojas/loja-a/atendimento-experimental",
        json={"mensagem": "Ola"},
    )
    assert sem_chave.status_code == 403

    for _ in range(5):
        assert enviar(cliente).status_code == 200

    assert enviar(cliente).status_code == 429


def test_limite_expira_apos_janela(
    cliente, monkeypatch
):
    configurar_resposta_valida(monkeypatch)

    import security.limite_atendimento_ia as modulo

    relogio = [1000.0]
    monkeypatch.setattr(
        modulo,
        "_agora",
        lambda: relogio[0],
    )

    for _ in range(5):
        assert enviar(cliente).status_code == 200

    assert enviar(cliente).status_code == 429

    relogio[0] += 61.0

    assert enviar(cliente).status_code == 200
