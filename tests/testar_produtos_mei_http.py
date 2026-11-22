
import pytest

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import database.contas_models

from main import app
from database.models import Base, get_db, Produto
from database.contas_models import Estabelecimento, UsuarioMEI
from security.auth import gerar_hash_senha


SENHA = "SenhaTesteMEI!2026"


@pytest.fixture
def ambiente(monkeypatch):
    monkeypatch.setenv(
        "SESSION_SECRET",
        "segredo-seguro-para-testes-http-mei-2026",
    )
    monkeypatch.setenv("COOKIE_SECURE", "false")

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
        lojas = [
            Estabelecimento(
                nome="Loja HTTP Um",
                slug="loja-http-um",
                ativo=True,
            ),
            Estabelecimento(
                nome="Loja HTTP Dois",
                slug="loja-http-dois",
                ativo=True,
            ),
        ]
        db.add_all(lojas)
        db.flush()

        usuarios = [
            UsuarioMEI(
                estabelecimento_id=lojas[0].id,
                nome="MEI Um",
                email="mei-http-1@example.com",
                senha_hash=gerar_hash_senha(SENHA),
                ativo=True,
            ),
            UsuarioMEI(
                estabelecimento_id=lojas[1].id,
                nome="MEI Dois",
                email="mei-http-2@example.com",
                senha_hash=gerar_hash_senha(SENHA),
                ativo=True,
            ),
        ]
        db.add_all(usuarios)
        db.commit()

        loja1_id = lojas[0].id
        loja2_id = lojas[1].id

    def obter_db_teste():
        db = SessaoTeste()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = obter_db_teste

    with TestClient(app) as cliente1, TestClient(app) as cliente2:
        login1 = cliente1.post(
            "/auth/mei/login",
            json={
                "email": "mei-http-1@example.com",
                "senha": SENHA,
            },
        )
        login2 = cliente2.post(
            "/auth/mei/login",
            json={
                "email": "mei-http-2@example.com",
                "senha": SENHA,
            },
        )

        assert login1.status_code == 200, login1.text
        assert login2.status_code == 200, login2.text

        yield {
            "cliente1": cliente1,
            "cliente2": cliente2,
            "csrf1": login1.json()["csrf_token"],
            "csrf2": login2.json()["csrf_token"],
            "loja1": loja1_id,
            "loja2": loja2_id,
            "SessaoTeste": SessaoTeste,
        }

    app.dependency_overrides.pop(get_db, None)
    engine.dispose()


def cadastrar(cliente, csrf, nome, **campos):
    dados = {
        "nome": nome,
        "preco": 12.50,
        "quantidade": 20,
        "descricao": "Produto de teste",
        "categoria": "Teste",
    }
    dados.update(campos)

    return cliente.post(
        "/mei/produtos",
        json=dados,
        headers={"X-CSRF-Token": csrf},
    )


def test_cadastro_http_loja_correta(ambiente):
    resposta = cadastrar(
        ambiente["cliente1"],
        ambiente["csrf1"],
        "Produto Loja Um",
    )

    assert resposta.status_code == 201, resposta.text
    assert resposta.json()["estabelecimento_id"] == ambiente["loja1"]


def test_mesmo_nome_em_lojas_diferentes(ambiente):
    resposta1 = cadastrar(
        ambiente["cliente1"],
        ambiente["csrf1"],
        "Produto Compartilhado",
    )
    resposta2 = cadastrar(
        ambiente["cliente2"],
        ambiente["csrf2"],
        "Produto Compartilhado",
    )

    assert resposta1.status_code == 201, resposta1.text
    assert resposta2.status_code == 201, resposta2.text
    assert resposta1.json()["id"] != resposta2.json()["id"]


def test_listagem_isolada_http(ambiente):
    resposta1 = cadastrar(
        ambiente["cliente1"],
        ambiente["csrf1"],
        "Produto Exclusivo Um",
    )
    resposta2 = cadastrar(
        ambiente["cliente2"],
        ambiente["csrf2"],
        "Produto Exclusivo Dois",
    )

    assert resposta1.status_code == 201
    assert resposta2.status_code == 201

    lista1 = ambiente["cliente1"].get("/mei/produtos")
    lista2 = ambiente["cliente2"].get("/mei/produtos")

    assert lista1.status_code == 200
    assert lista2.status_code == 200

    assert [p["id"] for p in lista1.json()] == [
        resposta1.json()["id"]
    ]
    assert [p["id"] for p in lista2.json()] == [
        resposta2.json()["id"]
    ]


def test_busca_nao_vaza_produto(ambiente):
    resposta = cadastrar(
        ambiente["cliente1"],
        ambiente["csrf1"],
        "Produto Privado HTTP",
    )
    assert resposta.status_code == 201

    busca = ambiente["cliente2"].get(
        "/mei/produtos/buscar",
        params={"nome": "Produto Privado HTTP"},
    )

    assert busca.status_code == 404


def test_busca_autorizada_http(ambiente):
    resposta = cadastrar(
        ambiente["cliente1"],
        ambiente["csrf1"],
        "Produto Encontrado HTTP",
    )
    assert resposta.status_code == 201

    busca = ambiente["cliente1"].get(
        "/mei/produtos/buscar",
        params={"nome": "Encontrado"},
    )

    assert busca.status_code == 200
    assert busca.json()["id"] == resposta.json()["id"]


def test_cadastro_sem_csrf_bloqueado(ambiente):
    resposta = ambiente["cliente1"].post(
        "/mei/produtos",
        json={
            "nome": "Sem CSRF",
            "preco": 10,
            "quantidade": 2,
        },
    )

    assert resposta.status_code == 403


def test_cadastro_com_csrf_de_outra_loja_bloqueado(ambiente):
    resposta = cadastrar(
        ambiente["cliente1"],
        ambiente["csrf2"],
        "CSRF De Outra Loja",
    )

    assert resposta.status_code == 403


def test_estoque_da_propria_loja(ambiente):
    cadastro = cadastrar(
        ambiente["cliente1"],
        ambiente["csrf1"],
        "Produto Estoque",
    )
    assert cadastro.status_code == 201

    produto_id = cadastro.json()["id"]

    resposta = ambiente["cliente1"].patch(
        f"/mei/produtos/{produto_id}/estoque",
        json={"nova_quantidade": 35},
        headers={"X-CSRF-Token": ambiente["csrf1"]},
    )

    assert resposta.status_code == 200, resposta.text
    assert resposta.json()["quantidade"] == 35


def test_estoque_de_outra_loja_bloqueado(ambiente):
    cadastro = cadastrar(
        ambiente["cliente1"],
        ambiente["csrf1"],
        "Produto Protegido",
    )
    assert cadastro.status_code == 201

    produto_id = cadastro.json()["id"]

    resposta = ambiente["cliente2"].patch(
        f"/mei/produtos/{produto_id}/estoque",
        json={"nova_quantidade": 99},
        headers={"X-CSRF-Token": ambiente["csrf2"]},
    )

    assert resposta.status_code in (400, 404)

    with ambiente["SessaoTeste"]() as db:
        produto = db.get(Produto, produto_id)
        assert produto.quantidade == 20


def test_cliente_nao_escolhe_estabelecimento(ambiente):
    resposta = cadastrar(
        ambiente["cliente1"],
        ambiente["csrf1"],
        "Produto Com ID Falso",
        estabelecimento_id=ambiente["loja2"],
    )

    assert resposta.status_code == 201, resposta.text
    assert resposta.json()["estabelecimento_id"] == ambiente["loja1"]


def test_sem_autenticacao(ambiente):
    with TestClient(app) as anonimo:
        resposta = anonimo.get("/mei/produtos")
        assert resposta.status_code == 401


# ============================================================
# TESTES DE ESTOQUE MINIMO MEI - TCC II
# ============================================================

def test_estoque_minimo_mei_propria_loja(ambiente):
    cadastro = cadastrar(
        ambiente["cliente1"],
        ambiente["csrf1"],
        "Produto Limite Proprio",
    )

    assert cadastro.status_code == 201, cadastro.text

    produto_id = cadastro.json()["id"]

    assert cadastro.json()["estoque_minimo"] == 5

    resposta = ambiente["cliente1"].patch(
        f"/mei/produtos/{produto_id}/estoque-minimo",
        json={"estoque_minimo": 10},
        headers={
            "X-CSRF-Token": ambiente["csrf1"]
        },
    )

    assert resposta.status_code == 200, resposta.text
    assert resposta.json()["estoque_minimo"] == 10
    assert resposta.json()["estabelecimento_id"] == (
        ambiente["loja1"]
    )

    lista = ambiente["cliente1"].get("/mei/produtos")

    assert lista.status_code == 200

    produto_listado = next(
        p for p in lista.json()
        if p["id"] == produto_id
    )

    assert produto_listado["estoque_minimo"] == 10

    with ambiente["SessaoTeste"]() as db:
        produto = db.get(Produto, produto_id)
        assert produto.estoque_minimo == 10


def test_estoque_minimo_mei_outra_loja_bloqueado(ambiente):
    cadastro = cadastrar(
        ambiente["cliente1"],
        ambiente["csrf1"],
        "Produto Minimo Protegido",
    )

    assert cadastro.status_code == 201, cadastro.text

    produto_id = cadastro.json()["id"]

    resposta = ambiente["cliente2"].patch(
        f"/mei/produtos/{produto_id}/estoque-minimo",
        json={"estoque_minimo": 99},
        headers={
            "X-CSRF-Token": ambiente["csrf2"]
        },
    )

    assert resposta.status_code == 404, resposta.text

    with ambiente["SessaoTeste"]() as db:
        produto = db.get(Produto, produto_id)

        assert produto is not None
        assert produto.estabelecimento_id == ambiente["loja1"]
        assert produto.estoque_minimo == 5


def test_estoque_minimo_mei_sem_csrf(ambiente):
    cadastro = cadastrar(
        ambiente["cliente1"],
        ambiente["csrf1"],
        "Produto CSRF Obrigatorio",
    )

    assert cadastro.status_code == 201

    produto_id = cadastro.json()["id"]

    resposta = ambiente["cliente1"].patch(
        f"/mei/produtos/{produto_id}/estoque-minimo",
        json={"estoque_minimo": 15},
    )

    assert resposta.status_code == 403

    with ambiente["SessaoTeste"]() as db:
        produto = db.get(Produto, produto_id)
        assert produto.estoque_minimo == 5


def test_estoque_minimo_mei_csrf_de_outra_loja(ambiente):
    cadastro = cadastrar(
        ambiente["cliente1"],
        ambiente["csrf1"],
        "Produto Token Incorreto",
    )

    assert cadastro.status_code == 201

    produto_id = cadastro.json()["id"]

    resposta = ambiente["cliente1"].patch(
        f"/mei/produtos/{produto_id}/estoque-minimo",
        json={"estoque_minimo": 22},
        headers={
            "X-CSRF-Token": ambiente["csrf2"]
        },
    )

    assert resposta.status_code == 403

    with ambiente["SessaoTeste"]() as db:
        produto = db.get(Produto, produto_id)
        assert produto.estoque_minimo == 5


def test_estoque_minimo_mei_sem_autenticacao(ambiente):
    cadastro = cadastrar(
        ambiente["cliente1"],
        ambiente["csrf1"],
        "Produto Sem Login",
    )

    assert cadastro.status_code == 201

    produto_id = cadastro.json()["id"]

    with TestClient(app) as anonimo:
        resposta = anonimo.patch(
            f"/mei/produtos/{produto_id}/estoque-minimo",
            json={"estoque_minimo": 30},
        )

    assert resposta.status_code == 401

    with ambiente["SessaoTeste"]() as db:
        produto = db.get(Produto, produto_id)
        assert produto.estoque_minimo == 5


@pytest.mark.parametrize(
    "valor",
    [-1, 1.5, True, "3"],
)
def test_estoque_minimo_mei_valores_invalidos(
    ambiente,
    valor,
):
    cadastro = cadastrar(
        ambiente["cliente1"],
        ambiente["csrf1"],
        "Produto Validacao Minimo",
    )

    assert cadastro.status_code == 201

    produto_id = cadastro.json()["id"]

    resposta = ambiente["cliente1"].patch(
        f"/mei/produtos/{produto_id}/estoque-minimo",
        json={"estoque_minimo": valor},
        headers={
            "X-CSRF-Token": ambiente["csrf1"]
        },
    )

    assert resposta.status_code == 422

    with ambiente["SessaoTeste"]() as db:
        produto = db.get(Produto, produto_id)
        assert produto.estoque_minimo == 5


def test_estoque_minimo_mei_zero_permitido(ambiente):
    cadastro = cadastrar(
        ambiente["cliente1"],
        ambiente["csrf1"],
        "Produto Limite Zero",
    )

    assert cadastro.status_code == 201

    produto_id = cadastro.json()["id"]

    resposta = ambiente["cliente1"].patch(
        f"/mei/produtos/{produto_id}/estoque-minimo",
        json={"estoque_minimo": 0},
        headers={
            "X-CSRF-Token": ambiente["csrf1"]
        },
    )

    assert resposta.status_code == 200, resposta.text
    assert resposta.json()["estoque_minimo"] == 0


def test_estoque_minimo_mei_id_invalido(ambiente):
    resposta = ambiente["cliente1"].patch(
        "/mei/produtos/0/estoque-minimo",
        json={"estoque_minimo": 10},
        headers={
            "X-CSRF-Token": ambiente["csrf1"]
        },
    )

    assert resposta.status_code == 422


def test_estoque_minimo_mei_produto_inexistente(ambiente):
    resposta = ambiente["cliente1"].patch(
        "/mei/produtos/999999/estoque-minimo",
        json={"estoque_minimo": 10},
        headers={
            "X-CSRF-Token": ambiente["csrf1"]
        },
    )

    assert resposta.status_code == 404


# TESTES ATENDIMENTO CONVERSACIONAL V2

@pytest.mark.parametrize(
    "mensagem",
    [
        "Oi",
        "Ola bom dia",
        "Ol\u00e1, bom dia!",
        "Boa tarde",
        "Oi, tudo bem?",
    ],
)
def test_saudacoes_conversacionais(mensagem):
    from security.atendimento_conversacional import (
        responder_saudacao,
    )

    assert responder_saudacao(mensagem) is not None


def test_saudacao_com_compra_nao_interceptada():
    from security.atendimento_conversacional import (
        responder_saudacao,
    )

    assert responder_saudacao(
        "Ola, quero comprar duas camisetas"
    ) is None


def test_triagem_incompleta_pede_esclarecimento():
    from security.atendimento_conversacional import (
        esclarecimento_triagem,
    )

    dados = {
        "cliente_nome": None,
        "itens": [],
        "erro": "Dados insuficientes",
    }

    resposta = esclarecimento_triagem(dados)

    assert resposta is not None
    assert "informe" in resposta.lower()


def test_triagem_valida_nao_interceptada():
    from security.atendimento_conversacional import (
        esclarecimento_triagem,
    )

    dados = {
        "cliente_nome": "Ana",
        "itens": [
            {
                "produto_nome": "Camiseta",
                "quantidade": 2,
            }
        ],
    }

    assert esclarecimento_triagem(dados) is None


def test_loja_saudacao_sem_iniciar_compra(
    ambiente,
    monkeypatch,
):
    import main

    def compra_proibida(*args, **kwargs):
        pytest.fail("Saudacao iniciou fluxo de compra.")

    monkeypatch.setattr(
        main,
        "processar_pedido",
        compra_proibida,
    )

    resposta = ambiente["cliente1"].post(
        "/lojas/loja-http-um/atender",
        json={"mensagem": "Ol\u00e1, bom dia!"},
        headers={
            "Idempotency-Key": "teste-saudacao-2026-v2"
        },
    )

    assert resposta.status_code == 200, resposta.text

    dados = resposta.json()

    assert dados["sucesso"] is True
    assert dados["acao_executada"] == "saudacao"
    assert "pedido" not in (dados.get("dados") or {})


def test_loja_esclarecimento_sem_compra(
    ambiente,
    monkeypatch,
):
    import main

    monkeypatch.setattr(
        main,
        "consultar_catalogo",
        lambda *args, **kwargs: None,
    )

    monkeypatch.setattr(
        main,
        "processar_pedido",
        lambda **kwargs: {
            "sucesso": False,
            "tipo": "esclarecimento",
            "resposta": "Informe os dados do pedido.",
            "tempo_ms": 1,
        },
    )

    resposta = ambiente["cliente1"].post(
        "/lojas/loja-http-um/atender",
        json={"mensagem": "Quero fazer um pedido"},
        headers={
            "Idempotency-Key": "teste-esclarecimento-v2"
        },
    )

    assert resposta.status_code == 200, resposta.text

    dados = resposta.json()

    assert dados["sucesso"] is True
    assert dados["acao_executada"] == "esclarecimento"
    assert "pedido" not in (dados.get("dados") or {})
