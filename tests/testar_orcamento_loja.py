
import pytest

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from tests.auth_helpers import autenticar_cliente_admin

import main
from database.models import Base, Compra, Produto, get_db


@pytest.fixture
def ambiente(monkeypatch):
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

    def substituir_banco():
        db = SessaoTeste()
        try:
            yield db
        finally:
            db.close()

    main.app.dependency_overrides[get_db] = substituir_banco

    try:
        # Sem context manager para nao executar o lifespan real.
        cliente = TestClient(main.app)
        autenticar_cliente_admin(cliente, monkeypatch)

        cadastro = cliente.post(
            "/produtos",
            json={
                "nome": "Arroz Teste",
                "preco": 25.00,
                "quantidade": 10,
                "categoria": "Testes",
                "descricao": "Produto experimental",
            },
        )

        assert cadastro.status_code == 200, cadastro.text

        produto_id = cadastro.json()["id"]

        yield cliente, SessaoTeste, produto_id

    finally:
        main.app.dependency_overrides.clear()
        engine.dispose()


def dados_orcamento(produto_id, quantidade=2):
    return {
        "cliente_nome": "Cliente Teste",
        "itens": [
            {
                "produto_id": produto_id,
                "quantidade": quantidade,
            }
        ],
    }


def test_orcamento_calcula_total(ambiente):
    cliente, _, produto_id = ambiente

    resposta = cliente.post(
        "/loja/orcamento",
        json=dados_orcamento(produto_id),
    )

    assert resposta.status_code == 200, resposta.text

    dados = resposta.json()

    assert dados["cliente_nome"] == "Cliente Teste"
    assert dados["valor_total_centavos"] == 5000

    assert len(dados["itens"]) == 1
    assert dados["itens"][0]["quantidade"] == 2
    assert dados["itens"][0]["preco_unitario_centavos"] == 2500
    assert dados["itens"][0]["subtotal_centavos"] == 5000


def test_orcamento_nao_registra_compra(ambiente):
    cliente, SessaoTeste, produto_id = ambiente

    resposta = cliente.post(
        "/loja/orcamento",
        json=dados_orcamento(produto_id),
    )

    assert resposta.status_code == 200

    with SessaoTeste() as db:
        assert db.query(Compra).count() == 0

        produto = db.get(Produto, produto_id)

        assert produto is not None
        assert produto.quantidade == 10


def test_orcamento_repetido_nao_desconta_estoque(ambiente):
    cliente, SessaoTeste, produto_id = ambiente

    for _ in range(3):
        resposta = cliente.post(
            "/loja/orcamento",
            json=dados_orcamento(produto_id),
        )

        assert resposta.status_code == 200

    with SessaoTeste() as db:
        assert db.query(Compra).count() == 0
        assert db.get(Produto, produto_id).quantidade == 10


def test_estoque_insuficiente_rejeitado(ambiente):
    cliente, _, produto_id = ambiente

    resposta = cliente.post(
        "/loja/orcamento",
        json=dados_orcamento(produto_id, quantidade=11),
    )

    assert resposta.status_code == 409


def test_produto_inexistente(ambiente):
    cliente, _, _ = ambiente

    resposta = cliente.post(
        "/loja/orcamento",
        json=dados_orcamento(9999),
    )

    assert resposta.status_code == 404


def test_quantidade_invalida(ambiente):
    cliente, _, produto_id = ambiente

    resposta = cliente.post(
        "/loja/orcamento",
        json=dados_orcamento(produto_id, quantidade=-1),
    )

    assert resposta.status_code == 422


def test_itens_duplicados_consolidados(ambiente):
    cliente, _, produto_id = ambiente

    resposta = cliente.post(
        "/loja/orcamento",
        json={
            "cliente_nome": "Cliente Teste",
            "itens": [
                {"produto_id": produto_id, "quantidade": 2},
                {"produto_id": produto_id, "quantidade": 3},
            ],
        },
    )

    assert resposta.status_code == 200, resposta.text

    dados = resposta.json()

    assert len(dados["itens"]) == 1
    assert dados["itens"][0]["quantidade"] == 5
    assert dados["valor_total_centavos"] == 12500


def test_limite_consolidado_rejeitado(ambiente):
    cliente, _, produto_id = ambiente

    resposta = cliente.post(
        "/loja/orcamento",
        json={
            "cliente_nome": "Cliente Teste",
            "itens": [
                {"produto_id": produto_id, "quantidade": 30},
                {"produto_id": produto_id, "quantidade": 30},
            ],
        },
    )

    assert resposta.status_code == 422
