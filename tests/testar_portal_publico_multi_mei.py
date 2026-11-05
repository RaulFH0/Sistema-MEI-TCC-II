
import pytest

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import database.contas_models

from main import app
from database.models import (
    Base,
    Produto,
    Compra,
    get_db,
)
from database.contas_models import Estabelecimento


@pytest.fixture
def ambiente_portal():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    Base.metadata.create_all(bind=engine)

    SessaoTeste = sessionmaker(
        bind=engine,
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
    )

    with SessaoTeste() as db:
        loja1 = Estabelecimento(
            nome="Loja Publica Um",
            slug="loja-publica-um",
            ativo=True,
        )
        loja2 = Estabelecimento(
            nome="Loja Publica Dois",
            slug="loja-publica-dois",
            ativo=True,
        )

        db.add_all([loja1, loja2])
        db.flush()

        produto1 = Produto(
            nome="Arroz Teste",
            preco=10.50,
            quantidade=20,
            descricao="Produto da loja um",
            categoria="Alimentos",
            estabelecimento_id=loja1.id,
        )
        produto2 = Produto(
            nome="Arroz Teste",
            preco=12.00,
            quantidade=15,
            descricao="Produto da loja dois",
            categoria="Alimentos",
            estabelecimento_id=loja2.id,
        )

        db.add_all([produto1, produto2])
        db.commit()

        dados = {
            "loja1": loja1.id,
            "loja2": loja2.id,
            "produto1": produto1.id,
            "produto2": produto2.id,
        }

    def obter_db_teste():
        with SessaoTeste() as db:
            yield db

    anterior = app.dependency_overrides.get(get_db)
    app.dependency_overrides[get_db] = obter_db_teste

    try:
        with TestClient(app) as cliente:
            yield {
                "cliente": cliente,
                "SessaoTeste": SessaoTeste,
                **dados,
            }
    finally:
        if anterior is None:
            app.dependency_overrides.pop(get_db, None)
        else:
            app.dependency_overrides[get_db] = anterior

        engine.dispose()


def orcamento(ambiente, slug, produto_id, quantidade=2):
    return ambiente["cliente"].post(
        f"/lojas/{slug}/orcamento",
        json={
            "cliente_nome": "Cliente Teste",
            "itens": [
                {
                    "produto_id": produto_id,
                    "quantidade": quantidade,
                }
            ],
        },
    )


def confirmar(
    ambiente,
    slug,
    produto_id,
    chave,
    quantidade=2,
    total=2100,
):
    return ambiente["cliente"].post(
        f"/lojas/{slug}/confirmar",
        headers={"Idempotency-Key": chave},
        json={
            "cliente_nome": "Cliente Teste",
            "itens": [
                {
                    "produto_id": produto_id,
                    "quantidade": quantidade,
                }
            ],
            "valor_total_centavos": total,
        },
    )


def estoque(ambiente, produto_id):
    with ambiente["SessaoTeste"]() as db:
        return db.get(Produto, produto_id).quantidade


def compras(ambiente):
    with ambiente["SessaoTeste"]() as db:
        return db.scalars(
            select(Compra).order_by(Compra.id)
        ).all()


def test_orcamento_loja_um(ambiente_portal):
    a = ambiente_portal

    resposta = orcamento(
        a, "loja-publica-um", a["produto1"]
    )

    assert resposta.status_code == 200, resposta.text
    assert resposta.json()["valor_total_centavos"] == 2100
    assert estoque(a, a["produto1"]) == 20
    assert len(compras(a)) == 0


def test_orcamento_loja_dois(ambiente_portal):
    a = ambiente_portal

    resposta = orcamento(
        a, "loja-publica-dois", a["produto2"]
    )

    assert resposta.status_code == 200, resposta.text
    assert resposta.json()["valor_total_centavos"] == 2400


def test_orcamento_produto_de_outra_loja(ambiente_portal):
    a = ambiente_portal

    resposta = orcamento(
        a, "loja-publica-dois", a["produto1"]
    )

    assert resposta.status_code == 404


def test_confirmacao_loja_correta(ambiente_portal):
    a = ambiente_portal

    resposta = confirmar(
        a,
        "loja-publica-um",
        a["produto1"],
        "portal-compra-1",
    )

    assert resposta.status_code == 200, resposta.text
    assert resposta.json()["acao_executada"] == "pedido_confirmado"

    registros = compras(a)
    assert len(registros) == 1
    assert registros[0].estabelecimento_id == a["loja1"]
    assert estoque(a, a["produto1"]) == 18


def test_confirmacao_produto_de_outra_loja(ambiente_portal):
    a = ambiente_portal

    resposta = confirmar(
        a,
        "loja-publica-dois",
        a["produto1"],
        "portal-compra-indevida",
    )

    assert resposta.status_code == 404, resposta.text
    assert len(compras(a)) == 0
    assert estoque(a, a["produto1"]) == 20


def test_mesma_chave_em_duas_lojas(ambiente_portal):
    a = ambiente_portal

    resposta1 = confirmar(
        a,
        "loja-publica-um",
        a["produto1"],
        "chave-compartilhada",
        total=2100,
    )

    resposta2 = confirmar(
        a,
        "loja-publica-dois",
        a["produto2"],
        "chave-compartilhada",
        total=2400,
    )

    assert resposta1.status_code == 200, resposta1.text
    assert resposta2.status_code == 200, resposta2.text

    assert (
        resposta1.json()["pedido"]["compra_id"]
        != resposta2.json()["pedido"]["compra_id"]
    )

    assert len(compras(a)) == 2
    assert estoque(a, a["produto1"]) == 18
    assert estoque(a, a["produto2"]) == 13


def test_repeticao_na_mesma_loja(ambiente_portal):
    a = ambiente_portal

    primeira = confirmar(
        a, "loja-publica-um", a["produto1"], "chave-repetida"
    )

    segunda = confirmar(
        a, "loja-publica-um", a["produto1"], "chave-repetida"
    )

    assert primeira.status_code == 200
    assert segunda.status_code == 200
    assert segunda.json()["acao_executada"] == "pedido_repetido"
    assert len(compras(a)) == 1
    assert estoque(a, a["produto1"]) == 18


def test_total_divergente_reverte_compra(ambiente_portal):
    a = ambiente_portal

    resposta = confirmar(
        a,
        "loja-publica-um",
        a["produto1"],
        "chave-total-errado",
        total=100,
    )

    assert resposta.status_code == 409, resposta.text
    assert len(compras(a)) == 0
    assert estoque(a, a["produto1"]) == 20


def test_loja_inexistente(ambiente_portal):
    a = ambiente_portal

    resposta = orcamento(
        a, "loja-inexistente", a["produto1"]
    )

    assert resposta.status_code == 404


def test_loja_inativa(ambiente_portal):
    a = ambiente_portal

    with a["SessaoTeste"]() as db:
        loja = db.get(Estabelecimento, a["loja1"])
        loja.ativo = False
        db.commit()

    resposta = orcamento(
        a, "loja-publica-um", a["produto1"]
    )

    assert resposta.status_code == 404


def test_estoque_insuficiente(ambiente_portal):
    a = ambiente_portal

    resposta = orcamento(
        a,
        "loja-publica-dois",
        a["produto2"],
        quantidade=20,
    )

    assert resposta.status_code == 409
    assert estoque(a, a["produto2"]) == 15


def test_chave_reutilizada_com_dados_diferentes(
    ambiente_portal,
):
    a = ambiente_portal

    primeira = confirmar(
        a,
        "loja-publica-um",
        a["produto1"],
        "chave-conflito",
    )

    segunda = confirmar(
        a,
        "loja-publica-um",
        a["produto1"],
        "chave-conflito",
        quantidade=3,
        total=3150,
    )

    assert primeira.status_code == 200
    assert segunda.status_code == 409
    assert len(compras(a)) == 1
    assert estoque(a, a["produto1"]) == 18



# ============================================================
# TESTES DO CATALOGO PUBLICO MULTI-MEI
# ============================================================

def test_catalogo_publico_loja_um(
    ambiente_portal,
):
    a = ambiente_portal

    resposta = a["cliente"].get(
        "/lojas/loja-publica-um/produtos"
    )

    assert resposta.status_code == 200, resposta.text

    produtos = resposta.json()

    assert len(produtos) == 1
    assert produtos[0]["id"] == a["produto1"]
    assert produtos[0]["nome"] == "Arroz Teste"


def test_catalogo_publico_loja_dois(
    ambiente_portal,
):
    a = ambiente_portal

    resposta = a["cliente"].get(
        "/lojas/loja-publica-dois/produtos"
    )

    assert resposta.status_code == 200, resposta.text

    produtos = resposta.json()

    assert len(produtos) == 1
    assert produtos[0]["id"] == a["produto2"]

    assert all(
        produto["id"] != a["produto1"]
        for produto in produtos
    )


def test_catalogo_publico_loja_inexistente(
    ambiente_portal,
):
    a = ambiente_portal

    resposta = a["cliente"].get(
        "/lojas/loja-inexistente/produtos"
    )

    assert resposta.status_code == 404


def test_catalogo_publico_loja_inativa(
    ambiente_portal,
):
    a = ambiente_portal

    with a["SessaoTeste"]() as db:
        loja = db.get(
            Estabelecimento,
            a["loja1"]
        )

        loja.ativo = False
        db.commit()

    resposta = a["cliente"].get(
        "/lojas/loja-publica-um/produtos"
    )

    assert resposta.status_code == 404
