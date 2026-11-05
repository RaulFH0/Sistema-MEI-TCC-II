
import pytest

from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import database.contas_models

from main import app
from database.models import Base, get_db, SessaoAdmin
from database.contas_models import Estabelecimento, UsuarioMEI
from security.auth import gerar_hash_senha


SENHA_TESTE = "SenhaForteMEI!2026"
COOKIE_MEI = "sistema_mei_usuario"


def agora():
    return datetime.now(timezone.utc).replace(tzinfo=None)


@pytest.fixture
def ambiente_mei_http(monkeypatch):
    monkeypatch.setenv(
        "SESSION_SECRET",
        "segredo-exclusivo-de-testes-http-mei-2026",
    )
    monkeypatch.setenv("COOKIE_SECURE", "false")

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    Base.metadata.create_all(bind=engine)

    SessionTeste = sessionmaker(
        bind=engine,
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
    )

    with SessionTeste() as db:
        loja1 = Estabelecimento(
            nome="Loja Teste Um",
            slug="loja-teste-um",
            ativo=True,
        )
        loja2 = Estabelecimento(
            nome="Loja Teste Dois",
            slug="loja-teste-dois",
            ativo=True,
        )

        db.add_all([loja1, loja2])
        db.flush()

        usuario1 = UsuarioMEI(
            estabelecimento_id=loja1.id,
            nome="Empreendedor Um",
            email="mei1@example.com",
            senha_hash=gerar_hash_senha(SENHA_TESTE),
            ativo=True,
        )

        usuario2 = UsuarioMEI(
            estabelecimento_id=loja2.id,
            nome="Empreendedor Dois",
            email="mei2@example.com",
            senha_hash=gerar_hash_senha(SENHA_TESTE),
            ativo=True,
        )

        db.add_all([usuario1, usuario2])
        db.commit()

        ids = {
            "loja1": loja1.id,
            "loja2": loja2.id,
            "usuario1": usuario1.id,
            "usuario2": usuario2.id,
        }

    def substituir_get_db():
        db = SessionTeste()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = substituir_get_db

    cliente = TestClient(app)

    try:
        yield {
            "cliente": cliente,
            "SessionTeste": SessionTeste,
            **ids,
        }
    finally:
        cliente.close()
        app.dependency_overrides.pop(get_db, None)
        engine.dispose()


def fazer_login(cliente, email="mei1@example.com", senha=SENHA_TESTE):
    return cliente.post(
        "/auth/mei/login",
        json={"email": email, "senha": senha},
    )


def test_login_mei_correto(ambiente_mei_http):
    ambiente = ambiente_mei_http
    cliente = ambiente["cliente"]

    resposta = fazer_login(cliente)

    assert resposta.status_code == 200, resposta.text

    dados = resposta.json()

    assert dados["autenticado"] is True
    assert dados["usuario_mei_id"] == ambiente["usuario1"]
    assert dados["estabelecimento_id"] == ambiente["loja1"]
    assert dados["csrf_token"]

    cookie = resposta.headers.get("set-cookie", "").lower()

    assert f"{COOKIE_MEI}=" in cookie
    assert "httponly" in cookie
    assert "samesite=lax" in cookie


def test_senha_incorreta(ambiente_mei_http):
    cliente = ambiente_mei_http["cliente"]

    resposta = fazer_login(
        cliente,
        senha="SenhaIncorreta!2026",
    )

    assert resposta.status_code == 401
    assert COOKIE_MEI not in cliente.cookies


def test_email_inexistente(ambiente_mei_http):
    cliente = ambiente_mei_http["cliente"]

    resposta = fazer_login(
        cliente,
        email="inexistente@example.com",
    )

    assert resposta.status_code == 401


def test_me_sem_login(ambiente_mei_http):
    cliente = ambiente_mei_http["cliente"]

    resposta = cliente.get("/auth/mei/me")

    assert resposta.status_code == 401


def test_me_com_login(ambiente_mei_http):
    cliente = ambiente_mei_http["cliente"]

    login = fazer_login(cliente)
    assert login.status_code == 200

    resposta = cliente.get("/auth/mei/me")

    assert resposta.status_code == 200
    assert resposta.json()["csrf_token"] == login.json()["csrf_token"]


def test_lojas_diferentes(ambiente_mei_http):
    ambiente = ambiente_mei_http
    cliente = ambiente["cliente"]

    login1 = fazer_login(cliente)
    assert login1.status_code == 200

    dados1 = cliente.get("/auth/mei/me").json()

    login2 = fazer_login(
        cliente,
        email="mei2@example.com",
    )
    assert login2.status_code == 200

    dados2 = cliente.get("/auth/mei/me").json()

    assert dados1["estabelecimento_id"] == ambiente["loja1"]
    assert dados2["estabelecimento_id"] == ambiente["loja2"]
    assert dados1["usuario_mei_id"] != dados2["usuario_mei_id"]


def test_sessao_mei_nao_acessa_admin(ambiente_mei_http):
    cliente = ambiente_mei_http["cliente"]

    assert fazer_login(cliente).status_code == 200

    resposta = cliente.get("/compras")

    assert resposta.status_code == 401


def test_logout_sem_csrf(ambiente_mei_http):
    cliente = ambiente_mei_http["cliente"]

    assert fazer_login(cliente).status_code == 200

    resposta = cliente.post("/auth/mei/logout")

    assert resposta.status_code == 403
    assert cliente.get("/auth/mei/me").status_code == 200


def test_logout_com_csrf_invalido(ambiente_mei_http):
    cliente = ambiente_mei_http["cliente"]

    assert fazer_login(cliente).status_code == 200

    resposta = cliente.post(
        "/auth/mei/logout",
        headers={"X-CSRF-Token": "csrf-invalido"},
    )

    assert resposta.status_code == 403
    assert cliente.get("/auth/mei/me").status_code == 200


def test_logout_revoga_sessao(ambiente_mei_http):
    cliente = ambiente_mei_http["cliente"]

    login = fazer_login(cliente)
    assert login.status_code == 200

    csrf = login.json()["csrf_token"]
    token_original = cliente.cookies.get(COOKIE_MEI)

    assert token_original

    resposta = cliente.post(
        "/auth/mei/logout",
        headers={"X-CSRF-Token": csrf},
    )

    assert resposta.status_code == 200
    assert resposta.json()["autenticado"] is False
    assert COOKIE_MEI not in cliente.cookies

    cliente.cookies.set(COOKIE_MEI, token_original)

    assert cliente.get("/auth/mei/me").status_code == 401


def test_usuario_desativado(ambiente_mei_http):
    ambiente = ambiente_mei_http
    cliente = ambiente["cliente"]

    assert fazer_login(cliente).status_code == 200

    with ambiente["SessionTeste"]() as db:
        usuario = db.get(UsuarioMEI, ambiente["usuario1"])
        usuario.ativo = False
        db.commit()

    assert cliente.get("/auth/mei/me").status_code == 401


def test_loja_desativada(ambiente_mei_http):
    ambiente = ambiente_mei_http
    cliente = ambiente["cliente"]

    assert fazer_login(cliente).status_code == 200

    with ambiente["SessionTeste"]() as db:
        loja = db.get(Estabelecimento, ambiente["loja1"])
        loja.ativo = False
        db.commit()

    assert cliente.get("/auth/mei/me").status_code == 401


def test_sessao_expirada(ambiente_mei_http):
    ambiente = ambiente_mei_http
    cliente = ambiente["cliente"]

    assert fazer_login(cliente).status_code == 200

    with ambiente["SessionTeste"]() as db:
        sessao = (
            db.query(SessaoAdmin)
            .filter(
                SessaoAdmin.usuario_mei_id
                == ambiente["usuario1"]
            )
            .one()
        )
        sessao.expira_em = agora() - timedelta(seconds=1)
        db.commit()

    assert cliente.get("/auth/mei/me").status_code == 401


def test_logout_sem_login(ambiente_mei_http):
    cliente = ambiente_mei_http["cliente"]

    resposta = cliente.post(
        "/auth/mei/logout",
        headers={"X-CSRF-Token": "token-invalido"},
    )

    assert resposta.status_code == 401
