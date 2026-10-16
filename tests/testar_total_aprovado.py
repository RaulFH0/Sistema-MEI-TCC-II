
import pytest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from database.crud import registrar_compra_segura
from database.models import Base, Compra, ItemCompra, Produto


@pytest.fixture
def ambiente():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    Base.metadata.create_all(bind=engine)

    SessaoTeste = sessionmaker(bind=engine)

    with SessaoTeste() as db:
        produto = Produto(
            nome="Arroz Teste",
            preco=25.00,
            quantidade=10,
            categoria="Testes",
        )

        db.add(produto)
        db.commit()
        db.refresh(produto)

        produto_id = produto.id

    try:
        yield SessaoTeste, produto_id
    finally:
        engine.dispose()


def confirmar(db, total, chave="teste-portal-001"):
    return registrar_compra_segura(
        db=db,
        cliente_nome="Cliente Teste",
        itens=[
            {
                "produto_nome": "Arroz Teste",
                "quantidade": 2,
            }
        ],
        chave_idempotencia=chave,
        mensagem_original="portal:cliente-teste:arroz:2",
        total_aprovado_centavos=total,
    )


def test_total_correto_confirma_compra(ambiente):
    SessaoTeste, produto_id = ambiente

    with SessaoTeste() as db:
        resultado = confirmar(db, 5000)

        assert resultado["pedido_confirmado"] is True
        assert resultado["valor_total"] == 50.00

        assert db.query(Compra).count() == 1
        assert db.query(ItemCompra).count() == 1
        assert db.get(Produto, produto_id).quantidade == 8


def test_total_diferente_desfaz_compra(ambiente):
    SessaoTeste, produto_id = ambiente

    with SessaoTeste() as db:
        with pytest.raises(ValueError, match="mudou"):
            confirmar(db, 4900)

        assert db.query(Compra).count() == 0
        assert db.query(ItemCompra).count() == 0
        assert db.get(Produto, produto_id).quantidade == 10


def test_reenvio_mesma_chave_nao_duplica(ambiente):
    SessaoTeste, produto_id = ambiente

    with SessaoTeste() as db:
        primeira = confirmar(db, 5000)
        segunda = confirmar(db, 5000)

        assert primeira["compra_id"] == segunda["compra_id"]
        assert segunda["requisicao_repetida"] is True

        assert db.query(Compra).count() == 1
        assert db.get(Produto, produto_id).quantidade == 8


def test_reenvio_com_outro_total_rejeitado(ambiente):
    SessaoTeste, produto_id = ambiente

    with SessaoTeste() as db:
        confirmar(db, 5000)

        with pytest.raises(ValueError, match="valor aprovado diferente"):
            confirmar(db, 4900)

        assert db.query(Compra).count() == 1
        assert db.get(Produto, produto_id).quantidade == 8


def test_preco_alterado_depois_do_orcamento(ambiente):
    SessaoTeste, produto_id = ambiente

    with SessaoTeste() as db:
        produto = db.get(Produto, produto_id)
        produto.preco = 30.00
        db.commit()

    with SessaoTeste() as db:
        with pytest.raises(ValueError, match="mudou"):
            confirmar(db, 5000)

        assert db.query(Compra).count() == 0
        assert db.get(Produto, produto_id).quantidade == 10


@pytest.mark.parametrize("total", [-1, 0, 50.5, True, "5000"])
def test_total_invalido_rejeitado(ambiente, total):
    SessaoTeste, produto_id = ambiente

    with SessaoTeste() as db:
        with pytest.raises(ValueError, match="Total aprovado invalido"):
            confirmar(db, total)

        assert db.query(Compra).count() == 0
        assert db.get(Produto, produto_id).quantidade == 10


def test_estoque_insuficiente_nao_registra(ambiente):
    SessaoTeste, produto_id = ambiente

    with SessaoTeste() as db:
        produto = db.get(Produto, produto_id)
        produto.quantidade = 1
        db.commit()

    with SessaoTeste() as db:
        with pytest.raises(ValueError, match="Estoque insuficiente"):
            confirmar(db, 5000)

        assert db.query(Compra).count() == 0
        assert db.get(Produto, produto_id).quantidade == 1
