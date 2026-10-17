import pytest

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from main import app
from database.models import Base, get_db, SessaoAdmin
from security.auth import gerar_hash_senha


SENHA_TESTE = "SenhaForteExclusivaTeste!2026"


@pytest.fixture
def ambiente_auth(monkeypatch):
    # Configuracoes exclusivas dos testes.
    monkeypatch.setenv("ADMIN_USERNAME", "admin")
    monkeypatch.setenv(
        "ADMIN_PASSWORD_HASH",
        gerar_hash_senha(SENHA_TESTE),
    )
    monkeypatch.setenv(
        "SESSION_SECRET",
        "segredo-exclusivo-dos-testes-automatizados-2026",
    )
    monkeypatch.setenv("COOKIE_SECURE", "false")

    # Banco temporario: nao utiliza sistema_mei_teste.db.
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
    )

    def substituir_get_db():
        db = SessionTeste()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = substituir_get_db

    # Sem context manager: nao executa o lifespan
    # nem inicializa o banco real ou o RAG.
    cliente = TestClient(app)

    try:
        yield cliente, SessionTeste
    finally:
        cliente.close()
        app.dependency_overrides.clear()
        engine.dispose()


def fazer_login(cliente):
    return cliente.post(
        "/auth/login",
        json={
            "usuario": "admin",
            "senha": SENHA_TESTE,
        },
    )


def test_login_correto(ambiente_auth):
    cliente, _ = ambiente_auth

    resposta = fazer_login(cliente)

    assert resposta.status_code == 200, resposta.text

    dados = resposta.json()

    assert dados["autenticado"] is True
    assert dados["usuario"] == "admin"
    assert dados["csrf_token"]

    cookie = resposta.headers.get("set-cookie", "").lower()

    assert "sistema_mei_admin=" in cookie
    assert "httponly" in cookie
    assert "samesite=lax" in cookie


def test_senha_incorreta(ambiente_auth):
    cliente, _ = ambiente_auth

    resposta = cliente.post(
        "/auth/login",
        json={
            "usuario": "admin",
            "senha": "SenhaIncorreta!2026",
        },
    )

    assert resposta.status_code == 401
    assert "sistema_mei_admin" not in cliente.cookies


def test_me_sem_login(ambiente_auth):
    cliente, _ = ambiente_auth

    resposta = cliente.get("/auth/me")

    assert resposta.status_code == 401


def test_me_com_login(ambiente_auth):
    cliente, _ = ambiente_auth

    login = fazer_login(cliente)
    assert login.status_code == 200

    resposta = cliente.get("/auth/me")

    assert resposta.status_code == 200
    assert resposta.json()["usuario"] == "admin"

    # O CSRF deve ser consistente na mesma sessao.
    assert (
        resposta.json()["csrf_token"]
        == login.json()["csrf_token"]
    )


def test_logout_sem_csrf_e_bloqueado(ambiente_auth):
    cliente, _ = ambiente_auth

    login = fazer_login(cliente)
    assert login.status_code == 200

    resposta = cliente.post("/auth/logout")

    assert resposta.status_code == 403

    # A tentativa sem CSRF nao deve encerrar a sessao.
    assert cliente.get("/auth/me").status_code == 200


def test_logout_revoga_sessao(ambiente_auth):
    cliente, SessionTeste = ambiente_auth

    login = fazer_login(cliente)
    assert login.status_code == 200

    csrf = login.json()["csrf_token"]

    token_original = cliente.cookies.get(
        "sistema_mei_admin"
    )
    assert token_original

    resposta = cliente.post(
        "/auth/logout",
        headers={"X-CSRF-Token": csrf},
    )

    assert resposta.status_code == 200
    assert resposta.json()["autenticado"] is False

    # Cookie removido apos logout.
    assert "sistema_mei_admin" not in cliente.cookies

    # Mesmo reutilizando o token antigo,
    # o servidor precisa rejeitar a sessao.
    cliente.cookies.set(
        "sistema_mei_admin",
        token_original,
    )

    assert cliente.get("/auth/me").status_code == 401

    with SessionTeste() as db:
        sessoes = db.query(SessaoAdmin).all()

        assert len(sessoes) == 1
        assert sessoes[0].revogada_em is not None


def test_logout_sem_login(ambiente_auth):
    cliente, _ = ambiente_auth

    resposta = cliente.post(
        "/auth/logout",
        headers={
            "X-CSRF-Token": "token-invalido"
        },
    )

    assert resposta.status_code == 401


def test_csrf_incorreto(ambiente_auth):
    cliente, _ = ambiente_auth

    login = fazer_login(cliente)
    assert login.status_code == 200

    resposta = cliente.post(
        "/auth/logout",
        headers={
            "X-CSRF-Token": "csrf-falso"
        },
    )

    assert resposta.status_code == 403
    assert cliente.get("/auth/me").status_code == 200