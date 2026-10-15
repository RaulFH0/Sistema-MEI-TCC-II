
import pytest

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import main

from database.models import Base, get_db, Produto


@pytest.fixture
def cliente_api():
    # Banco temporario em memoria
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool
    )

    Base.metadata.create_all(bind=engine)

    SessaoTeste = sessionmaker(
        bind=engine,
        expire_on_commit=False
    )

    def substituir_banco():
        db = SessaoTeste()
        try:
            yield db
        finally:
            db.close()

    main.app.dependency_overrides[get_db] = substituir_banco

    try:
        cliente = TestClient(main.app)
        yield cliente
    finally:
        main.app.dependency_overrides.clear()
        engine.dispose()


def test_cadastrar_produto(cliente_api):
    resposta = cliente_api.post(
        "/produtos",
        json={
            "nome": "Produto de Teste",
            "preco": 10.50,
            "quantidade": 20,
            "descricao": "Produto experimental",
            "categoria": "Testes"
        }
    )

    assert resposta.status_code == 200

    dados = resposta.json()

    assert dados["nome"] == "Produto de Teste"
    assert dados["quantidade"] == 20
    assert dados["preco"] == 10.50


def test_atualizar_estoque(cliente_api):
    cadastro = cliente_api.post(
        "/produtos",
        json={
            "nome": "Arroz Teste",
            "preco": 25,
            "quantidade": 10,
            "categoria": "Testes"
        }
    )

    assert cadastro.status_code == 200

    produto_id = cadastro.json()["id"]

    resposta = cliente_api.patch(
        f"/produtos/{produto_id}/estoque",
        json={"quantidade": 50}
    )

    assert resposta.status_code == 200
    assert resposta.json()["quantidade"] == 50

    # Confirmar que o GET retorna a nova quantidade
    produtos = cliente_api.get("/produtos")

    assert produtos.status_code == 200
    assert produtos.json()[0]["quantidade"] == 50


def test_estoque_negativo_rejeitado(cliente_api):
    resposta = cliente_api.patch(
        "/produtos/1/estoque",
        json={"quantidade": -1}
    )

    assert resposta.status_code == 422


def test_quantidade_decimal_rejeitada(cliente_api):
    resposta = cliente_api.patch(
        "/produtos/1/estoque",
        json={"quantidade": 2.5}
    )

    assert resposta.status_code == 422


def test_produto_inexistente(cliente_api):
    resposta = cliente_api.patch(
        "/produtos/9999/estoque",
        json={"quantidade": 20}
    )

    assert resposta.status_code == 404


def test_produto_duplicado(cliente_api):
    dados = {
        "nome": "Produto Repetido",
        "preco": 10,
        "quantidade": 5,
        "categoria": "Testes"
    }

    primeira = cliente_api.post("/produtos", json=dados)
    segunda = cliente_api.post("/produtos", json=dados)

    assert primeira.status_code == 200
    assert segunda.status_code == 400
