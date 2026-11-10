
import pytest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from database.crud import registrar_compra_segura
from database.models import Base, Compra, ItemCompra, Produto
from database.contas_models import Estabelecimento


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
        db.add(
            Estabelecimento(
                id=1,
                nome="Loja Inicial",
                slug="loja-inicial",
                ativo=True,
            )
        )
        db.flush()
        arroz = Produto(
            nome="Arroz Teste",
            preco=25.00,
            quantidade=10,
            categoria="Testes",
            estabelecimento_id=1,
        )

        feijao = Produto(
            nome="Feijao Teste",
            preco=8.50,
            quantidade=5,
            categoria="Testes",
            estabelecimento_id=1,
        )

        db.add_all([arroz, feijao])
        db.commit()

        arroz_id = arroz.id
        feijao_id = feijao.id

    try:
        yield SessaoTeste, arroz_id, feijao_id
    finally:
        engine.dispose()


def confirmar(
    db,
    itens,
    total,
    chave="portal-teste-001",
):
    return registrar_compra_segura(
        db=db,
        cliente_nome="Cliente Portal",
        itens=itens,
        chave_idempotencia=chave,
        total_aprovado_centavos=total,
        identificar_por_id=True,
    )


def test_compra_por_id_confirmada(ambiente):
    SessaoTeste, arroz_id, feijao_id = ambiente

    with SessaoTeste() as db:
        resultado = confirmar(
            db,
            [
                {"produto_id": arroz_id, "quantidade": 2},
                {"produto_id": feijao_id, "quantidade": 1},
            ],
            total=5850,
        )

        assert resultado["pedido_confirmado"] is True
        assert resultado["valor_total"] == 58.50

        compra = db.query(Compra).one()
        itens = db.query(ItemCompra).all()

        assert compra.valor_total == 5850
        assert len(itens) == 2
        assert {item.produto_id for item in itens} == {
            arroz_id,
            feijao_id,
        }

        assert db.get(Produto, arroz_id).quantidade == 8
        assert db.get(Produto, feijao_id).quantidade == 4


def test_produto_inexistente_nao_registra(ambiente):
    SessaoTeste, arroz_id, _ = ambiente

    with SessaoTeste() as db:
        with pytest.raises(ValueError, match="nao cadastrado"):
            confirmar(
                db,
                [{"produto_id": 9999, "quantidade": 1}],
                total=2500,
            )

        assert db.query(Compra).count() == 0
        assert db.get(Produto, arroz_id).quantidade == 10


def test_preco_diferente_desfaz_tudo(ambiente):
    SessaoTeste, arroz_id, _ = ambiente

    with SessaoTeste() as db:
        with pytest.raises(ValueError, match="mudou"):
            confirmar(
                db,
                [{"produto_id": arroz_id, "quantidade": 2}],
                total=4900,
            )

        assert db.query(Compra).count() == 0
        assert db.query(ItemCompra).count() == 0
        assert db.get(Produto, arroz_id).quantidade == 10


def test_reenvio_mesma_chave(ambiente):
    SessaoTeste, arroz_id, _ = ambiente

    with SessaoTeste() as db:
        itens = [{"produto_id": arroz_id, "quantidade": 2}]

        primeira = confirmar(db, itens, 5000)
        segunda = confirmar(db, itens, 5000)

        assert primeira["compra_id"] == segunda["compra_id"]
        assert segunda["requisicao_repetida"] is True

        assert db.query(Compra).count() == 1
        assert db.get(Produto, arroz_id).quantidade == 8


def test_mesma_chave_outro_produto_rejeitada(ambiente):
    SessaoTeste, arroz_id, feijao_id = ambiente

    with SessaoTeste() as db:
        confirmar(
            db,
            [{"produto_id": arroz_id, "quantidade": 1}],
            total=2500,
        )

        with pytest.raises(ValueError, match="dados diferentes"):
            confirmar(
                db,
                [{"produto_id": feijao_id, "quantidade": 1}],
                total=850,
            )

        assert db.query(Compra).count() == 1
        assert db.get(Produto, arroz_id).quantidade == 9
        assert db.get(Produto, feijao_id).quantidade == 5


def test_itens_duplicados_consolidados(ambiente):
    SessaoTeste, arroz_id, _ = ambiente

    with SessaoTeste() as db:
        resultado = confirmar(
            db,
            [
                {"produto_id": arroz_id, "quantidade": 1},
                {"produto_id": arroz_id, "quantidade": 2},
            ],
            total=7500,
        )

        assert resultado["valor_total"] == 75.00
        assert db.query(ItemCompra).count() == 1
        assert db.get(Produto, arroz_id).quantidade == 7


def test_id_invalido_rejeitado(ambiente):
    SessaoTeste, arroz_id, _ = ambiente

    with SessaoTeste() as db:
        with pytest.raises(ValueError, match="ID do produto invalido"):
            confirmar(
                db,
                [{"produto_id": True, "quantidade": 1}],
                total=2500,
            )

        assert db.query(Compra).count() == 0
        assert db.get(Produto, arroz_id).quantidade == 10


def test_estoque_insuficiente_rejeitado(ambiente):
    SessaoTeste, arroz_id, _ = ambiente

    with SessaoTeste() as db:
        with pytest.raises(ValueError, match="Estoque insuficiente"):
            confirmar(
                db,
                [{"produto_id": arroz_id, "quantidade": 11}],
                total=27500,
            )

        assert db.query(Compra).count() == 0
        assert db.get(Produto, arroz_id).quantidade == 10
