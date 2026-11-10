import pytest

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from main import app
from database.models import (
    Base,
    Compra,
    ItemCompra,
    Produto,
    get_db,
)
from database.contas_models import Estabelecimento
from security.mei_routes import exigir_mei


@pytest.fixture
def ambiente(tmp_path):
    banco = tmp_path / "compras_mei_teste.db"

    engine = create_engine(
        "sqlite:///" + banco.as_posix(),
        connect_args={"check_same_thread": False},
    )

    @event.listens_for(engine, "connect")
    def configurar_sqlite(conexao, registro):
        cursor = conexao.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(bind=engine)

    Sessao = sessionmaker(
        bind=engine,
        autoflush=False,
        expire_on_commit=False,
    )

    with Sessao.begin() as db:
        lojas = [
            Estabelecimento(
                nome="Loja A",
                slug="teste-vendas-loja-a",
                ativo=True,
            ),
            Estabelecimento(
                nome="Loja B",
                slug="teste-vendas-loja-b",
                ativo=True,
            ),
        ]
        db.add_all(lojas)
        db.flush()

        loja_a, loja_b = lojas

        produtos = [
            Produto(
                nome="Produto A",
                descricao="Teste",
                preco=25.90,
                quantidade=10,
                categoria="Teste",
                estoque_minimo=0,
                estabelecimento_id=loja_a.id,
            ),
            Produto(
                nome="Produto B",
                descricao="Teste",
                preco=10.00,
                quantidade=10,
                categoria="Teste",
                estoque_minimo=0,
                estabelecimento_id=loja_b.id,
            ),
        ]

        db.add_all(produtos)
        db.flush()

        produto_a, produto_b = produtos

        compras = [
            Compra(
                cliente_nome="Cliente Loja A",
                chave_idempotencia="teste-venda-a-1",
                valor_total=5180,
                status="confirmado",
                estabelecimento_id=loja_a.id,
            ),
            Compra(
                cliente_nome="Segundo Cliente A",
                chave_idempotencia="teste-venda-a-2",
                valor_total=2590,
                status="confirmado",
                estabelecimento_id=loja_a.id,
            ),
            Compra(
                cliente_nome="Cliente Loja B",
                chave_idempotencia="teste-venda-b-1",
                valor_total=1000,
                status="confirmado",
                estabelecimento_id=loja_b.id,
            ),
        ]

        db.add_all(compras)
        db.flush()

        db.add_all([
            ItemCompra(
                compra_id=compras[0].id,
                produto_id=produto_a.id,
                produto_nome="Produto A",
                quantidade=2,
                preco_unitario=2590,
                subtotal=5180,
            ),
            ItemCompra(
                compra_id=compras[1].id,
                produto_id=produto_a.id,
                produto_nome="Produto A",
                quantidade=1,
                preco_unitario=2590,
                subtotal=2590,
            ),
            ItemCompra(
                compra_id=compras[2].id,
                produto_id=produto_b.id,
                produto_nome="Produto B",
                quantidade=1,
                preco_unitario=1000,
                subtotal=1000,
            ),
        ])

        ids = (loja_a.id, loja_b.id)

    anteriores = dict(app.dependency_overrides)

    def banco_teste():
        with Sessao() as db:
            yield db

    app.dependency_overrides[get_db] = banco_teste

    cliente = TestClient(app)

    try:
        yield cliente, ids
    finally:
        cliente.close()
        app.dependency_overrides.clear()
        app.dependency_overrides.update(anteriores)
        engine.dispose()


def autenticar_loja(loja_id):
    app.dependency_overrides[exigir_mei] = (
        lambda: {"estabelecimento_id": loja_id}
    )


def test_sem_autenticacao_retorna_401(ambiente):
    cliente, _ = ambiente

    resposta = cliente.get("/mei/compras")

    assert resposta.status_code == 401


@pytest.mark.parametrize("indice,cliente_esperado,quantidade", [
    (0, "Cliente Loja A", 2),
    (1, "Cliente Loja B", 1),
])
def test_isolamento_por_estabelecimento(
    ambiente,
    indice,
    cliente_esperado,
    quantidade,
):
    cliente, lojas = ambiente
    autenticar_loja(lojas[indice])

    resposta = cliente.get("/mei/compras")

    assert resposta.status_code == 200, resposta.text

    dados = resposta.json()

    assert len(dados) == quantidade

    nomes = {compra["cliente_nome"] for compra in dados}
    assert cliente_esperado in nomes

    if indice == 0:
        assert "Cliente Loja B" not in nomes
    else:
        assert "Cliente Loja A" not in nomes
        assert "Segundo Cliente A" not in nomes


def test_valores_em_centavos_e_itens(ambiente):
    cliente, lojas = ambiente
    autenticar_loja(lojas[0])

    resposta = cliente.get("/mei/compras")
    assert resposta.status_code == 200, resposta.text

    compras = resposta.json()

    compra = next(
        c for c in compras
        if c["cliente_nome"] == "Cliente Loja A"
    )

    assert compra["valor_total"] == 5180
    assert compra["status"] == "confirmado"
    assert compra["criado_em"]
    assert len(compra["itens"]) == 1

    item = compra["itens"][0]

    assert item["produto_nome"] == "Produto A"
    assert item["quantidade"] == 2
    assert item["preco_unitario"] == 2590
    assert item["subtotal"] == 5180

    assert "chave_idempotencia" not in compra
    assert "hash_solicitacao" not in compra


def test_limite_de_resultados(ambiente):
    cliente, lojas = ambiente
    autenticar_loja(lojas[0])

    resposta = cliente.get("/mei/compras?limite=1")

    assert resposta.status_code == 200, resposta.text
    assert len(resposta.json()) == 1


def test_limite_invalido_retorna_422(ambiente):
    cliente, lojas = ambiente
    autenticar_loja(lojas[0])

    for limite in (0, 101):
        resposta = cliente.get(
            f"/mei/compras?limite={limite}"
        )
        assert resposta.status_code == 422
