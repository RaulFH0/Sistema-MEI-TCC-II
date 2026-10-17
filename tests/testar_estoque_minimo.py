
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from tests.auth_helpers import autenticar_cliente_admin

import main
from database.models import Base, get_db


@pytest.fixture
def cliente_api(monkeypatch):
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
        # Cria o cliente de teste sem executar
        # o lifespan da aplicacao.
        cliente = TestClient(main.app)

        # Autentica ANTES de disponibilizar
        # o cliente para os testes.
        autenticar_cliente_admin(cliente, monkeypatch)

        yield cliente
    finally:
        main.app.dependency_overrides.clear()
        engine.dispose()


def cadastrar_produto(cliente_api):
    resposta = cliente_api.post(
        "/produtos",
        json={
            "nome": "Produto Alerta Teste",
            "preco": 12.50,
            "quantidade": 8,
            "categoria": "Testes",
            "descricao": "Produto para teste de estoque minimo",
        },
    )

    assert resposta.status_code == 200, resposta.text
    return resposta.json()


def test_estoque_minimo_inicial(cliente_api):
    produto = cadastrar_produto(cliente_api)

    assert produto["estoque_minimo"] == 5


def test_configurar_estoque_minimo(cliente_api):
    produto = cadastrar_produto(cliente_api)

    resposta = cliente_api.patch(
        f"/produtos/{produto['id']}/estoque-minimo",
        json={"estoque_minimo": 10},
    )

    assert resposta.status_code == 200, resposta.text

    dados = resposta.json()

    assert dados["estoque_minimo"] == 10
    assert dados["quantidade"] == 8
    assert dados["preco"] == 12.50

    consulta = cliente_api.get("/produtos")
    assert consulta.status_code == 200

    produto_atualizado = next(
        item
        for item in consulta.json()
        if item["id"] == produto["id"]
    )

    assert produto_atualizado["estoque_minimo"] == 10
    assert produto_atualizado["quantidade"] == 8


def test_estoque_minimo_zero_permitido(cliente_api):
    produto = cadastrar_produto(cliente_api)

    resposta = cliente_api.patch(
        f"/produtos/{produto['id']}/estoque-minimo",
        json={"estoque_minimo": 0},
    )

    assert resposta.status_code == 200
    assert resposta.json()["estoque_minimo"] == 0


@pytest.mark.parametrize("valor", [-1, 2.5, "10", True])
def test_valores_invalidos_rejeitados(cliente_api, valor):
    produto = cadastrar_produto(cliente_api)

    resposta = cliente_api.patch(
        f"/produtos/{produto['id']}/estoque-minimo",
        json={"estoque_minimo": valor},
    )

    assert resposta.status_code == 422

    consulta = cliente_api.get("/produtos")
    produto_atual = next(
        item
        for item in consulta.json()
        if item["id"] == produto["id"]
    )

    assert produto_atual["estoque_minimo"] == 5


def test_produto_inexistente(cliente_api):
    resposta = cliente_api.patch(
        "/produtos/9999/estoque-minimo",
        json={"estoque_minimo": 10},
    )

    assert resposta.status_code == 404


def test_id_invalido(cliente_api):
    resposta = cliente_api.patch(
        "/produtos/0/estoque-minimo",
        json={"estoque_minimo": 10},
    )

    assert resposta.status_code == 422


def test_alteracao_nao_modifica_compras(cliente_api):
    produto = cadastrar_produto(cliente_api)

    antes = cliente_api.get("/compras")
    assert antes.status_code == 200

    resposta = cliente_api.patch(
        f"/produtos/{produto['id']}/estoque-minimo",
        json={"estoque_minimo": 20},
    )

    assert resposta.status_code == 200

    depois = cliente_api.get("/compras")
    assert depois.status_code == 200

    assert antes.json() == depois.json()
    assert resposta.json()["quantidade"] == 8
