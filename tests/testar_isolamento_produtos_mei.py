
import pytest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import database.contas_models

from database.models import Base, Produto
from database.contas_models import Estabelecimento

from database.crud import (
    criar_produto_mei,
    buscar_produto_por_nome_mei,
    listar_produtos_mei,
    atualizar_estoque_mei,
)


# ============================================================
# BANCO TEMPORARIO DE TESTES
# ============================================================

@pytest.fixture
def ambiente_isolamento():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    Base.metadata.create_all(bind=engine)

    SessionTeste = sessionmaker(
        bind=engine,
        autocommit=False,
        autoflush=False,
        expire_on_commit=False,
    )

    db = SessionTeste()

    try:
        loja1 = Estabelecimento(
            nome="Mercado Teste Um",
            slug="mercado-teste-um",
            ativo=True,
        )

        loja2 = Estabelecimento(
            nome="Mercado Teste Dois",
            slug="mercado-teste-dois",
            ativo=True,
        )

        db.add_all([loja1, loja2])
        db.commit()

        yield {
            "db": db,
            "loja1": loja1,
            "loja2": loja2,
        }

    finally:
        db.close()
        engine.dispose()


def cadastrar(db, loja_id, nome="Arroz Teste"):
    return criar_produto_mei(
        db=db,
        estabelecimento_id=loja_id,
        nome=nome,
        preco=10.50,
        quantidade=20,
        descricao="Produto de teste",
        categoria="Alimentos",
    )


# ============================================================
# TESTES DE ISOLAMENTO
# ============================================================

def test_cadastro_associa_loja(ambiente_isolamento):
    dados = ambiente_isolamento

    produto = cadastrar(
        dados["db"],
        dados["loja1"].id,
    )

    assert produto.estabelecimento_id == dados["loja1"].id
    assert produto.quantidade == 20


def test_mesmo_nome_em_lojas_diferentes(ambiente_isolamento):
    dados = ambiente_isolamento

    produto1 = cadastrar(
        dados["db"],
        dados["loja1"].id,
    )

    produto2 = cadastrar(
        dados["db"],
        dados["loja2"].id,
    )

    assert produto1.id != produto2.id
    assert produto1.nome == produto2.nome
    assert produto1.estabelecimento_id != produto2.estabelecimento_id


def test_nome_duplicado_na_mesma_loja(ambiente_isolamento):
    dados = ambiente_isolamento

    cadastrar(dados["db"], dados["loja1"].id)

    with pytest.raises(ValueError, match="ja cadastrado"):
        cadastrar(dados["db"], dados["loja1"].id)


def test_listagem_isolada(ambiente_isolamento):
    dados = ambiente_isolamento

    produto1 = cadastrar(
        dados["db"],
        dados["loja1"].id,
        "Produto Exclusivo Um",
    )

    produto2 = cadastrar(
        dados["db"],
        dados["loja2"].id,
        "Produto Exclusivo Dois",
    )

    lista1 = listar_produtos_mei(
        dados["db"],
        dados["loja1"].id,
    )

    lista2 = listar_produtos_mei(
        dados["db"],
        dados["loja2"].id,
    )

    assert [p.id for p in lista1] == [produto1.id]
    assert [p.id for p in lista2] == [produto2.id]


def test_busca_nao_encontra_produto_de_outra_loja(
    ambiente_isolamento,
):
    dados = ambiente_isolamento

    cadastrar(
        dados["db"],
        dados["loja1"].id,
        "Produto Privado Um",
    )

    resultado = buscar_produto_por_nome_mei(
        dados["db"],
        dados["loja2"].id,
        "Produto Privado Um",
    )

    assert resultado is None


def test_atualizacao_estoque_autorizada(
    ambiente_isolamento,
):
    dados = ambiente_isolamento

    produto = cadastrar(
        dados["db"],
        dados["loja1"].id,
    )

    atualizado = atualizar_estoque_mei(
        db=dados["db"],
        estabelecimento_id=dados["loja1"].id,
        produto_id=produto.id,
        nova_quantidade=35,
    )

    assert atualizado.quantidade == 35


def test_estoque_outra_loja_bloqueado(
    ambiente_isolamento,
):
    dados = ambiente_isolamento

    produto = cadastrar(
        dados["db"],
        dados["loja1"].id,
    )

    with pytest.raises(ValueError, match="nao encontrado"):
        atualizar_estoque_mei(
            db=dados["db"],
            estabelecimento_id=dados["loja2"].id,
            produto_id=produto.id,
            nova_quantidade=99,
        )

    dados["db"].refresh(produto)

    assert produto.quantidade == 20


def test_estabelecimento_inexistente(
    ambiente_isolamento,
):
    dados = ambiente_isolamento

    with pytest.raises(ValueError):
        listar_produtos_mei(
            dados["db"],
            999999,
        )


def test_estabelecimento_inativo(
    ambiente_isolamento,
):
    dados = ambiente_isolamento

    loja = dados["loja1"]
    loja.ativo = False
    dados["db"].commit()

    with pytest.raises(ValueError):
        cadastrar(
            dados["db"],
            loja.id,
        )


def test_ids_de_loja_invalidos(
    ambiente_isolamento,
):
    dados = ambiente_isolamento

    for loja_id in (None, 0, -1, True, "1"):
        with pytest.raises(ValueError):
            listar_produtos_mei(
                dados["db"],
                loja_id,
            )
