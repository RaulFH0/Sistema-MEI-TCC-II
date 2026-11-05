
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from database.models import Base, get_db
from database.contas_models import Estabelecimento
import main


@pytest.fixture
def ambiente_ia(monkeypatch):
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    Base.metadata.create_all(bind=engine)

    SessaoTeste = sessionmaker(
        bind=engine,
        expire_on_commit=False,
    )

    with SessaoTeste() as db:
        loja1 = Estabelecimento(
            nome="Loja IA Um",
            slug="loja-ia-um",
            ativo=True,
        )
        loja2 = Estabelecimento(
            nome="Loja IA Dois",
            slug="loja-ia-dois",
            ativo=True,
        )
        loja_inativa = Estabelecimento(
            nome="Loja IA Inativa",
            slug="loja-ia-inativa",
            ativo=False,
        )

        db.add_all([loja1, loja2, loja_inativa])
        db.commit()

        ids = {
            "loja1": loja1.id,
            "loja2": loja2.id,
            "inativa": loja_inativa.id,
        }

    def obter_db_teste():
        with SessaoTeste() as db:
            yield db

    chamadas = []

    def simular_orquestrador(
        mensagem_usuario,
        chave_idempotencia,
        *,
        estabelecimento_id=1,
    ):
        chamadas.append({
            "mensagem": mensagem_usuario,
            "chave": chave_idempotencia,
            "loja": estabelecimento_id,
        })

        return {
            "sucesso": True,
            "tempo_ms": 10,
            "resultado": {
                "compra_id": 100 + estabelecimento_id,
                "cliente_nome": "Cliente Teste",
                "valor_total": 25.0,
                "requisicao_repetida": False,
            },
        }

    monkeypatch.setattr(
        main,
        "processar_pedido",
        simular_orquestrador,
    )

    anterior = main.app.dependency_overrides.get(get_db)
    main.app.dependency_overrides[get_db] = obter_db_teste

    # Sem context manager para nao executar o lifespan.
    cliente = TestClient(main.app)

    try:
        yield SimpleNamespace(
            cliente=cliente,
            ids=ids,
            chamadas=chamadas,
        )
    finally:
        cliente.close()

        if anterior is None:
            main.app.dependency_overrides.pop(
                get_db, None
            )
        else:
            main.app.dependency_overrides[get_db] = anterior

        engine.dispose()


def enviar(ambiente, slug, chave="chave-ia-teste"):
    return ambiente.cliente.post(
        f"/lojas/{slug}/atender",
        headers={"Idempotency-Key": chave},
        json={
            "mensagem": "Cliente Teste quer um arroz"
        },
    )


def test_atendimento_da_primeira_loja(ambiente_ia):
    a = ambiente_ia

    resposta = enviar(a, "loja-ia-um")

    assert resposta.status_code == 200, resposta.text
    assert resposta.json()["sucesso"] is True
    assert resposta.json()["acao_executada"] == (
        "pedido_confirmado"
    )
    assert a.chamadas[-1]["loja"] == a.ids["loja1"]


def test_atendimento_da_segunda_loja(ambiente_ia):
    a = ambiente_ia

    resposta = enviar(a, "loja-ia-dois")

    assert resposta.status_code == 200, resposta.text
    assert a.chamadas[-1]["loja"] == a.ids["loja2"]


def test_mesma_chave_encaminhada_a_duas_lojas(ambiente_ia):
    a = ambiente_ia

    primeira = enviar(
        a, "loja-ia-um", chave="mesma-chave"
    )
    segunda = enviar(
        a, "loja-ia-dois", chave="mesma-chave"
    )

    assert primeira.status_code == 200
    assert segunda.status_code == 200

    assert a.chamadas[-2]["chave"] == "mesma-chave"
    assert a.chamadas[-1]["chave"] == "mesma-chave"

    assert a.chamadas[-2]["loja"] == a.ids["loja1"]
    assert a.chamadas[-1]["loja"] == a.ids["loja2"]


def test_loja_inexistente_nao_executa_ia(ambiente_ia):
    a = ambiente_ia

    resposta = enviar(a, "loja-inexistente")

    assert resposta.status_code == 404
    assert a.chamadas == []


def test_loja_inativa_nao_executa_ia(ambiente_ia):
    a = ambiente_ia

    resposta = enviar(a, "loja-ia-inativa")

    assert resposta.status_code == 404
    assert a.chamadas == []


def test_chave_obrigatoria(ambiente_ia):
    a = ambiente_ia

    resposta = a.cliente.post(
        "/lojas/loja-ia-um/atender",
        json={"mensagem": "Quero arroz"},
    )

    assert resposta.status_code == 422
    assert a.chamadas == []


def test_compra_repetida(ambiente_ia, monkeypatch):
    a = ambiente_ia

    def resposta_repetida(
        mensagem_usuario,
        chave_idempotencia,
        *,
        estabelecimento_id=1,
    ):
        return {
            "sucesso": True,
            "tempo_ms": 5,
            "resultado": {
                "compra_id": 45,
                "cliente_nome": "Cliente Teste",
                "valor_total": 25.0,
                "requisicao_repetida": True,
            },
        }

    monkeypatch.setattr(
        main, "processar_pedido", resposta_repetida
    )

    resposta = enviar(a, "loja-ia-um")

    assert resposta.status_code == 200
    assert resposta.json()["acao_executada"] == (
        "pedido_repetido"
    )


def test_erro_de_estoque(ambiente_ia, monkeypatch):
    a = ambiente_ia

    def resposta_erro(
        mensagem_usuario,
        chave_idempotencia,
        *,
        estabelecimento_id=1,
    ):
        return {
            "sucesso": False,
            "erro": "Estoque insuficiente para o produto.",
            "tempo_ms": 5,
        }

    monkeypatch.setattr(
        main, "processar_pedido", resposta_erro
    )

    resposta = enviar(a, "loja-ia-um")

    assert resposta.status_code == 409


def test_erro_inesperado(ambiente_ia, monkeypatch):
    a = ambiente_ia

    def falhar(
        mensagem_usuario,
        chave_idempotencia,
        *,
        estabelecimento_id=1,
    ):
        raise RuntimeError("Erro interno simulado")

    monkeypatch.setattr(
        main, "processar_pedido", falhar
    )

    resposta = enviar(a, "loja-ia-um")

    assert resposta.status_code == 500
    assert "Erro interno" in resposta.json()["detail"]


def test_rota_antiga_preservada(ambiente_ia):
    a = ambiente_ia

    resposta = a.cliente.post(
        "/atender",
        headers={"Idempotency-Key": "chave-legada"},
        json={"mensagem": "Quero arroz"},
    )

    assert resposta.status_code == 200, resposta.text
    assert a.chamadas[-1]["loja"] == 1
