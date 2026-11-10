import pytest

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import main
from main import app
from database.models import Base, Produto, get_db
from database.contas_models import Estabelecimento
from security.consulta_catalogo_ia import pergunta_catalogo


@pytest.fixture
def ambiente(tmp_path, monkeypatch):
    caminho = tmp_path / "catalogo_ia_teste.db"

    engine = create_engine(
        "sqlite:///" + caminho.as_posix(),
        connect_args={"check_same_thread": False},
    )

    Base.metadata.create_all(bind=engine)

    Sessao = sessionmaker(
        bind=engine,
        expire_on_commit=False,
    )

    with Sessao.begin() as db:
        loja_a = Estabelecimento(
            nome="Loja IA A",
            slug="loja-ia-a",
            ativo=True,
        )
        loja_b = Estabelecimento(
            nome="Loja IA B",
            slug="loja-ia-b",
            ativo=True,
        )

        db.add_all([loja_a, loja_b])
        db.flush()

        produtos = [
            Produto(
                nome="Caderno Alpha",
                preco=25.90,
                quantidade=13,
                categoria="Papelaria",
                estabelecimento_id=loja_a.id,
            ),
            Produto(
                nome="Caneta Sem Estoque",
                preco=5.00,
                quantidade=0,
                categoria="Papelaria",
                estabelecimento_id=loja_a.id,
            ),
            Produto(
                nome="Produto Secreto Beta",
                preco=88.00,
                quantidade=7,
                categoria="Testes",
                estabelecimento_id=loja_b.id,
            ),
        ]

        db.add_all(produtos)

    def fornecer_banco():
        with Sessao() as db:
            yield db

    anteriores = dict(app.dependency_overrides)
    app.dependency_overrides[get_db] = fornecer_banco

    # Consultas nao devem chegar ao fluxo de compra.
    def compra_proibida(*args, **kwargs):
        raise AssertionError(
            "Consulta informativa acionou compra!"
        )

    monkeypatch.setattr(
        main,
        "processar_pedido",
        compra_proibida,
    )

    cliente = TestClient(app)

    try:
        yield cliente, Sessao
    finally:
        cliente.close()
        app.dependency_overrides.clear()
        app.dependency_overrides.update(anteriores)
        engine.dispose()


def consultar(cliente, slug):
    return cliente.post(
        f"/lojas/{slug}/atender",
        json={
            "mensagem": (
                "Quais produtos estao disponiveis "
                "nesta loja e qual o preco de cada um?"
            )
        },
        headers={
            "Idempotency-Key": "consulta-teste-001"
        },
    )


def test_consulta_loja_a(ambiente):
    cliente, _ = ambiente

    resposta = consultar(cliente, "loja-ia-a")

    assert resposta.status_code == 200, resposta.text
    dados = resposta.json()

    assert dados["sucesso"] is True
    assert dados["acao_executada"] == "consulta_catalogo"

    assert "Caderno Alpha" in dados["resposta"]
    assert "R$ 25,90" in dados["resposta"]
    assert "13 em estoque" in dados["resposta"]


def test_isolamento_entre_lojas(ambiente):
    cliente, _ = ambiente

    resposta_a = consultar(cliente, "loja-ia-a")
    resposta_b = consultar(cliente, "loja-ia-b")

    assert resposta_a.status_code == 200
    assert resposta_b.status_code == 200

    texto_a = resposta_a.json()["resposta"]
    texto_b = resposta_b.json()["resposta"]

    assert "Caderno Alpha" in texto_a
    assert "Produto Secreto Beta" not in texto_a

    assert "Produto Secreto Beta" in texto_b
    assert "Caderno Alpha" not in texto_b


def test_produto_sem_estoque_nao_aparece(ambiente):
    cliente, _ = ambiente

    resposta = consultar(cliente, "loja-ia-a")

    assert resposta.status_code == 200
    assert (
        "Caneta Sem Estoque"
        not in resposta.json()["resposta"]
    )


def test_consulta_nao_modifica_estoque(ambiente):
    cliente, Sessao = ambiente

    with Sessao() as db:
        antes = {
            produto.nome: produto.quantidade
            for produto in db.query(Produto).all()
        }

    resposta = consultar(cliente, "loja-ia-a")

    assert resposta.status_code == 200

    with Sessao() as db:
        depois = {
            produto.nome: produto.quantidade
            for produto in db.query(Produto).all()
        }

    assert antes == depois


def test_mensagem_de_compra_nao_e_catalogo():
    assert not pergunta_catalogo(
        "Quero comprar 2 cadernos."
    )
