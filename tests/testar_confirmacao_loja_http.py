
import pytest

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import main

from database.models import (
    Base,
    Compra,
    ItemCompra,
    Produto,
    get_db,
)


@pytest.fixture
def ambiente():
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
        produto = Produto(
            nome="Arroz Portal Teste",
            preco=25.00,
            quantidade=10,
            categoria="Testes",
            estoque_minimo=5,
        )

        db.add(produto)
        db.commit()
        db.refresh(produto)

        produto_id = produto.id

    def substituir_banco():
        db = SessaoTeste()

        try:
            yield db
        finally:
            db.close()

    main.app.dependency_overrides[get_db] = substituir_banco

    try:
        # Nao executa o lifespan da aplicacao.
        cliente = TestClient(main.app)
        yield cliente, SessaoTeste, produto_id

    finally:
        main.app.dependency_overrides.clear()
        engine.dispose()


def pedido(produto_id, quantidade=2, total=5000):
    return {
        "cliente_nome": "Cliente Portal",
        "itens": [
            {
                "produto_id": produto_id,
                "quantidade": quantidade,
            }
        ],
        "valor_total_centavos": total,
    }


def confirmar(cliente, dados, chave="portal-http-teste-001"):
    return cliente.post(
        "/loja/confirmar",
        json=dados,
        headers={"Idempotency-Key": chave},
    )


def test_confirmacao_registra_compra(ambiente):
    cliente, SessaoTeste, produto_id = ambiente

    resposta = confirmar(
        cliente,
        pedido(produto_id),
    )

    assert resposta.status_code == 200, resposta.text

    dados = resposta.json()

    assert dados["sucesso"] is True
    assert dados["acao_executada"] == "pedido_confirmado"
    assert dados["pedido"]["valor_total"] == 50.00
    assert dados["pedido"]["requisicao_repetida"] is False

    with SessaoTeste() as db:
        assert db.query(Compra).count() == 1
        assert db.query(ItemCompra).count() == 1

        item = db.query(ItemCompra).one()

        assert item.produto_id == produto_id
        assert item.quantidade == 2
        assert db.get(Produto, produto_id).quantidade == 8


def test_reenvio_nao_duplica_compra(ambiente):
    cliente, SessaoTeste, produto_id = ambiente

    dados = pedido(produto_id)

    primeira = confirmar(cliente, dados)
    segunda = confirmar(cliente, dados)

    assert primeira.status_code == 200
    assert segunda.status_code == 200

    assert segunda.json()["acao_executada"] == "pedido_repetido"

    assert (
        primeira.json()["pedido"]["compra_id"]
        == segunda.json()["pedido"]["compra_id"]
    )

    with SessaoTeste() as db:
        assert db.query(Compra).count() == 1
        assert db.get(Produto, produto_id).quantidade == 8


def test_mesma_chave_com_quantidade_diferente(ambiente):
    cliente, SessaoTeste, produto_id = ambiente

    primeira = confirmar(
        cliente,
        pedido(produto_id, quantidade=2, total=5000),
    )

    segunda = confirmar(
        cliente,
        pedido(produto_id, quantidade=1, total=2500),
    )

    assert primeira.status_code == 200
    assert segunda.status_code == 409

    with SessaoTeste() as db:
        assert db.query(Compra).count() == 1
        assert db.get(Produto, produto_id).quantidade == 8


def test_preco_alterado_rejeita_confirmacao(ambiente):
    cliente, SessaoTeste, produto_id = ambiente

    orcamento = cliente.post(
        "/loja/orcamento",
        json={
            "cliente_nome": "Cliente Portal",
            "itens": [
                {
                    "produto_id": produto_id,
                    "quantidade": 2,
                }
            ],
        },
    )

    assert orcamento.status_code == 200
    assert orcamento.json()["valor_total_centavos"] == 5000

    # Simula alteracao de preco apos o orcamento.
    with SessaoTeste() as db:
        produto = db.get(Produto, produto_id)
        produto.preco = 30.00
        db.commit()

    resposta = confirmar(
        cliente,
        pedido(produto_id, total=5000),
    )

    assert resposta.status_code == 409

    with SessaoTeste() as db:
        assert db.query(Compra).count() == 0
        assert db.query(ItemCompra).count() == 0
        assert db.get(Produto, produto_id).quantidade == 10


def test_estoque_insuficiente_rejeita(ambiente):
    cliente, SessaoTeste, produto_id = ambiente

    resposta = confirmar(
        cliente,
        pedido(
            produto_id,
            quantidade=11,
            total=27500,
        ),
    )

    assert resposta.status_code == 409

    with SessaoTeste() as db:
        assert db.query(Compra).count() == 0
        assert db.query(ItemCompra).count() == 0
        assert db.get(Produto, produto_id).quantidade == 10


def test_produto_inexistente(ambiente):
    cliente, SessaoTeste, _ = ambiente

    resposta = confirmar(
        cliente,
        pedido(9999, quantidade=1, total=2500),
    )

    assert resposta.status_code == 404

    with SessaoTeste() as db:
        assert db.query(Compra).count() == 0


def test_total_invalido(ambiente):
    cliente, SessaoTeste, produto_id = ambiente

    resposta = confirmar(
        cliente,
        pedido(produto_id, total=-1),
    )

    assert resposta.status_code == 422

    with SessaoTeste() as db:
        assert db.query(Compra).count() == 0


def test_confirmacao_sem_chave(ambiente):
    cliente, SessaoTeste, produto_id = ambiente

    resposta = cliente.post(
        "/loja/confirmar",
        json=pedido(produto_id),
    )

    assert resposta.status_code == 422

    with SessaoTeste() as db:
        assert db.query(Compra).count() == 0
