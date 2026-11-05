
import pytest

from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import database.contas_models

from database.models import (
    Base,
    Produto,
    Compra,
    ItemCompra,
)
from database.contas_models import Estabelecimento

from database.crud import (
    registrar_compra_segura,
    consultar_compra_por_mensagem,
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
        autoflush=False,
        expire_on_commit=False,
    )

    with SessaoTeste() as db:
        loja1 = Estabelecimento(
            nome="Loja Compras Um",
            slug="loja-compras-um",
            ativo=True,
        )
        loja2 = Estabelecimento(
            nome="Loja Compras Dois",
            slug="loja-compras-dois",
            ativo=True,
        )

        db.add_all([loja1, loja2])
        db.flush()

        produto1 = Produto(
            nome="Arroz Teste",
            preco=10.50,
            quantidade=20,
            descricao="Produto loja 1",
            categoria="Alimentos",
            estabelecimento_id=loja1.id,
        )
        produto2 = Produto(
            nome="Arroz Teste",
            preco=10.50,
            quantidade=20,
            descricao="Produto loja 2",
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

    db = SessaoTeste()

    try:
        yield {"db": db, **dados}
    finally:
        db.close()
        engine.dispose()


def comprar(
    ambiente,
    loja,
    produto,
    chave,
    quantidade=2,
    total=2100,
    mensagem=None,
):
    return registrar_compra_segura(
        db=ambiente["db"],
        cliente_nome="Cliente Teste",
        itens=[
            {
                "produto_id": produto,
                "quantidade": quantidade,
            }
        ],
        chave_idempotencia=chave,
        identificar_por_id=True,
        total_aprovado_centavos=total,
        mensagem_original=mensagem,
        estabelecimento_id=loja,
    )


def estoque(ambiente, produto_id):
    ambiente["db"].expire_all()
    produto = ambiente["db"].get(Produto, produto_id)
    return produto.quantidade


def quantidade_compras(ambiente):
    return len(
        ambiente["db"].scalars(
            select(Compra)
        ).all()
    )


def test_compra_vinculada_a_loja(ambiente):
    resultado = comprar(
        ambiente,
        ambiente["loja1"],
        ambiente["produto1"],
        "chave-vinculo",
    )

    assert resultado["pedido_confirmado"] is True

    compra = ambiente["db"].get(
        Compra,
        resultado["compra_id"],
    )

    assert compra.estabelecimento_id == ambiente["loja1"]
    assert estoque(ambiente, ambiente["produto1"]) == 18


def test_duas_lojas_mesma_chave(ambiente):
    resultado1 = comprar(
        ambiente,
        ambiente["loja1"],
        ambiente["produto1"],
        "mesma-chave",
    )

    resultado2 = comprar(
        ambiente,
        ambiente["loja2"],
        ambiente["produto2"],
        "mesma-chave",
    )

    assert resultado1["compra_id"] != resultado2["compra_id"]
    assert quantidade_compras(ambiente) == 2

    assert estoque(ambiente, ambiente["produto1"]) == 18
    assert estoque(ambiente, ambiente["produto2"]) == 18


def test_repeticao_na_mesma_loja(ambiente):
    primeiro = comprar(
        ambiente,
        ambiente["loja1"],
        ambiente["produto1"],
        "chave-repetida",
    )

    segundo = comprar(
        ambiente,
        ambiente["loja1"],
        ambiente["produto1"],
        "chave-repetida",
    )

    assert primeiro["compra_id"] == segundo["compra_id"]
    assert segundo["requisicao_repetida"] is True
    assert quantidade_compras(ambiente) == 1
    assert estoque(ambiente, ambiente["produto1"]) == 18


def test_chave_com_dados_diferentes(ambiente):
    comprar(
        ambiente,
        ambiente["loja1"],
        ambiente["produto1"],
        "chave-conflito",
    )

    with pytest.raises(ValueError):
        comprar(
            ambiente,
            ambiente["loja1"],
            ambiente["produto1"],
            "chave-conflito",
            quantidade=3,
            total=3150,
        )

    assert quantidade_compras(ambiente) == 1
    assert estoque(ambiente, ambiente["produto1"]) == 18


def test_produto_de_outra_loja_bloqueado(ambiente):
    with pytest.raises(ValueError):
        comprar(
            ambiente,
            ambiente["loja2"],
            ambiente["produto1"],
            "chave-produto-indevido",
        )

    assert quantidade_compras(ambiente) == 0
    assert estoque(ambiente, ambiente["produto1"]) == 20


def test_estoque_insuficiente_reverte_compra(ambiente):
    with pytest.raises(ValueError):
        comprar(
            ambiente,
            ambiente["loja1"],
            ambiente["produto1"],
            "chave-sem-estoque",
            quantidade=25,
            total=26250,
        )

    assert quantidade_compras(ambiente) == 0
    assert estoque(ambiente, ambiente["produto1"]) == 20


def test_total_divergente_reverte_estoque(ambiente):
    with pytest.raises(ValueError):
        comprar(
            ambiente,
            ambiente["loja1"],
            ambiente["produto1"],
            "chave-total-errado",
            quantidade=2,
            total=100,
        )

    assert quantidade_compras(ambiente) == 0
    assert estoque(ambiente, ambiente["produto1"]) == 20


def test_compra_por_nome_isolada(ambiente):
    resultado = registrar_compra_segura(
        db=ambiente["db"],
        cliente_nome="Cliente IA",
        itens=[
            {
                "produto_nome": "Arroz Teste",
                "quantidade": 2,
            }
        ],
        chave_idempotencia="chave-ia",
        estabelecimento_id=ambiente["loja2"],
    )

    assert resultado["pedido_confirmado"] is True
    assert estoque(ambiente, ambiente["produto1"]) == 20
    assert estoque(ambiente, ambiente["produto2"]) == 18


def test_consulta_ia_nao_vaza_outra_loja(ambiente):
    mensagem = "Quero dois arrozes"

    comprar(
        ambiente,
        ambiente["loja1"],
        ambiente["produto1"],
        "chave-mensagem",
        mensagem=mensagem,
    )

    resultado = consultar_compra_por_mensagem(
        ambiente["db"],
        chave_idempotencia="chave-mensagem",
        mensagem_original=mensagem,
        estabelecimento_id=ambiente["loja2"],
    )

    assert resultado is None


def test_consulta_ia_recupera_propria_compra(ambiente):
    mensagem = "Comprar dois arrozes"

    compra = comprar(
        ambiente,
        ambiente["loja1"],
        ambiente["produto1"],
        "chave-mensagem-propria",
        mensagem=mensagem,
    )

    consulta = consultar_compra_por_mensagem(
        ambiente["db"],
        chave_idempotencia="chave-mensagem-propria",
        mensagem_original=mensagem,
        estabelecimento_id=ambiente["loja1"],
    )

    assert consulta is not None
    assert consulta["compra_id"] == compra["compra_id"]
    assert consulta["requisicao_repetida"] is True


def test_mensagem_diferente_mesma_chave(ambiente):
    comprar(
        ambiente,
        ambiente["loja1"],
        ambiente["produto1"],
        "chave-mensagem-diferente",
        mensagem="Comprar arroz",
    )

    with pytest.raises(ValueError):
        consultar_compra_por_mensagem(
            ambiente["db"],
            chave_idempotencia="chave-mensagem-diferente",
            mensagem_original="Comprar feijao",
            estabelecimento_id=ambiente["loja1"],
        )


def test_loja_inativa_nao_registra_compra(ambiente):
    loja = ambiente["db"].get(
        Estabelecimento,
        ambiente["loja1"],
    )

    loja.ativo = False
    ambiente["db"].commit()

    with pytest.raises(ValueError):
        comprar(
            ambiente,
            ambiente["loja1"],
            ambiente["produto1"],
            "chave-loja-inativa",
        )

    assert quantidade_compras(ambiente) == 0


def test_integridade_referencial(ambiente):
    resultado = comprar(
        ambiente,
        ambiente["loja1"],
        ambiente["produto1"],
        "chave-integridade",
    )

    compra = ambiente["db"].get(
        Compra,
        resultado["compra_id"],
    )

    assert len(compra.itens) == 1
    assert compra.itens[0].produto_id == ambiente["produto1"]

    verificacao = ambiente["db"].execute(
        text("PRAGMA foreign_key_check")
    ).fetchall()

    assert verificacao == []
