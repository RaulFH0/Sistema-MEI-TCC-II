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



# ============================================================
# CONSULTAS ESPECIFICAS DE PRODUTOS
# ============================================================

from security.consulta_produto_ia import (
    consultar_produto_especifico,
)


def test_consulta_especifica_caderno(ambiente):
    _, Sessao = ambiente

    with Sessao() as db:
        resultado = consultar_produto_especifico(
            db,
            1,
            "Quanto custa o caderno?",
        )

        assert resultado is not None
        assert resultado["sucesso"] is True
        assert "Caderno Alpha" in resultado["resposta"]
        assert "R$ 25,90" in resultado["resposta"]


def test_consulta_especifica_isolamento(ambiente):
    _, Sessao = ambiente

    with Sessao() as db:
        resultado = consultar_produto_especifico(
            db,
            1,
            "Quanto custa o Produto Secreto Beta?",
        )

        assert resultado is None


def test_consulta_especifica_sem_estoque(ambiente):
    _, Sessao = ambiente

    with Sessao() as db:
        resultado = consultar_produto_especifico(
            db,
            1,
            "Quanto custa a Caneta Sem Estoque?",
        )

        assert resultado is None


def test_consulta_especifica_inexistente(ambiente):
    _, Sessao = ambiente

    with Sessao() as db:
        resultado = consultar_produto_especifico(
            db,
            1,
            "Quanto custa o notebook?",
        )

        assert resultado is None


def test_consulta_especifica_nao_altera_estoque(ambiente):
    _, Sessao = ambiente

    with Sessao() as db:
        antes = {
            produto.id: produto.quantidade
            for produto in db.query(Produto).all()
        }

        consultar_produto_especifico(
            db,
            1,
            "Quanto custa o caderno?",
        )

        depois = {
            produto.id: produto.quantidade
            for produto in db.query(Produto).all()
        }

        assert antes == depois



# ============================================================
# INTEGRACAO MULTIINTENCAO COM BANCO TEMPORARIO
# ============================================================

from security.atendimento_multiintencao import (
    atender_multiintencao,
)


def _loja_teste(db, slug):
    loja = (
        db.query(Estabelecimento)
        .filter(Estabelecimento.slug == slug)
        .one()
    )
    return loja.id


def _classificacao_teste(intencao, origem="agente"):
    def executar(mensagem):
        return {
            "intencao": intencao,
            "confianca": 0.95,
            "origem": origem,
            "tempo_ms": 1.0,
        }

    return executar


def _estado_comercial(db):
    from sqlalchemy import text

    produtos = [
        (
            produto.id,
            produto.estabelecimento_id,
            produto.quantidade,
            str(produto.preco),
        )
        for produto in db.query(Produto)
        .order_by(Produto.id)
        .all()
    ]

    compras = db.execute(
        text("SELECT COUNT(*) FROM compras")
    ).scalar_one()

    return produtos, compras


def test_integracao_real_catalogo_loja_a(ambiente):
    _, Sessao = ambiente

    with Sessao() as db:
        loja = _loja_teste(db, "loja-ia-a")

        resposta = atender_multiintencao(
            db,
            loja,
            "Quais produtos estao disponiveis nesta loja?",
            classificador=_classificacao_teste(
                "consulta_catalogo"
            ),
        )

        assert resposta["acao_executada"] == (
            "consulta_catalogo"
        )
        assert "Caderno Alpha" in resposta["resposta"]
        assert "R$ 25,90" in resposta["resposta"]
        assert "Produto Secreto Beta" not in resposta["resposta"]
        assert resposta["dados"]["compra_registrada"] is False


def test_integracao_real_produto_especifico(ambiente):
    _, Sessao = ambiente

    with Sessao() as db:
        loja = _loja_teste(db, "loja-ia-a")

        resposta = atender_multiintencao(
            db,
            loja,
            "Quanto custa o caderno?",
            classificador=_classificacao_teste(
                "consulta_catalogo"
            ),
        )

        assert resposta["acao_executada"] == (
            "consulta_catalogo"
        )
        assert "Caderno Alpha" in resposta["resposta"]
        assert "R$ 25,90" in resposta["resposta"]


def test_integracao_real_isolamento_entre_lojas(ambiente):
    _, Sessao = ambiente

    with Sessao() as db:
        loja_b = _loja_teste(db, "loja-ia-b")

        resposta = atender_multiintencao(
            db,
            loja_b,
            "Quanto custa o caderno?",
            classificador=_classificacao_teste(
                "consulta_catalogo"
            ),
        )

        assert resposta["acao_executada"] == (
            "solicitar_esclarecimento"
        )
        assert "Caderno Alpha" not in resposta["resposta"]
        assert "R$ 25,90" not in resposta["resposta"]


def test_integracao_real_compra_nao_registra(ambiente):
    _, Sessao = ambiente

    with Sessao() as db:
        loja = _loja_teste(db, "loja-ia-a")
        antes = _estado_comercial(db)

        resposta = atender_multiintencao(
            db,
            loja,
            "Quero comprar dois cadernos.",
            classificador=_classificacao_teste("compra"),
        )

        db.expire_all()
        depois = _estado_comercial(db)

        assert resposta["acao_executada"] == (
            "compra_pendente_confirmacao"
        )
        assert resposta["dados"]["compra_registrada"] is False
        assert antes == depois


def test_integracao_real_falha_agente_nao_registra(ambiente):
    _, Sessao = ambiente

    def falhar(mensagem):
        raise RuntimeError("Provedor indisponivel")

    with Sessao() as db:
        loja = _loja_teste(db, "loja-ia-a")
        antes = _estado_comercial(db)

        resposta = atender_multiintencao(
            db,
            loja,
            "Quero comprar dois cadernos.",
            classificador=falhar,
        )

        db.expire_all()
        depois = _estado_comercial(db)

        assert resposta["acao_executada"] == (
            "solicitar_esclarecimento"
        )
        assert resposta["dados"]["compra_registrada"] is False
        assert antes == depois
