import pytest

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from main import app
from database.models import Base, get_db
from security.auth import gerar_hash_senha


SENHA_TESTE = "SenhaForteExclusivaTeste!2026"


@pytest.fixture
def cliente_teste(monkeypatch):
    monkeypatch.setenv("ADMIN_USERNAME", "admin")
    monkeypatch.setenv(
        "ADMIN_PASSWORD_HASH",
        gerar_hash_senha(SENHA_TESTE)
    )
    monkeypatch.setenv(
        "SESSION_SECRET",
        "segredo-exclusivo-dos-testes-automatizados-2026"
    )
    monkeypatch.setenv("COOKIE_SECURE", "false")

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool
    )

    Base.metadata.create_all(bind=engine)

    SessionTeste = sessionmaker(
        bind=engine,
        autocommit=False,
        autoflush=False
    )

    def substituir_banco():
        db = SessionTeste()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = substituir_banco

    cliente = TestClient(app)

    try:
        yield cliente
    finally:
        cliente.close()
        app.dependency_overrides.clear()
        engine.dispose()


def autenticar(cliente):
    resposta = cliente.post(
        "/auth/login",
        json={
            "usuario": "admin",
            "senha": SENHA_TESTE
        }
    )

    assert resposta.status_code == 200, resposta.text

    return resposta.json()["csrf_token"]


# ============================================================
# ROTAS ADMINISTRATIVAS SEM AUTENTICACAO
# ============================================================

def test_listar_pedidos_sem_login(cliente_teste):
    resposta = cliente_teste.get("/pedidos")
    assert resposta.status_code == 401


def test_listar_compras_sem_login(cliente_teste):
    resposta = cliente_teste.get("/compras")
    assert resposta.status_code == 401


def test_cadastrar_produto_sem_login(cliente_teste):
    resposta = cliente_teste.post(
        "/produtos",
        json={
            "nome": "Produto Teste",
            "preco": 10.0,
            "quantidade": 5
        }
    )

    assert resposta.status_code == 401


def test_alterar_estoque_sem_login(cliente_teste):
    resposta = cliente_teste.patch(
        "/produtos/1/estoque",
        json={"quantidade": 10}
    )

    assert resposta.status_code == 401


def test_alterar_estoque_minimo_sem_login(cliente_teste):
    resposta = cliente_teste.patch(
        "/produtos/1/estoque-minimo",
        json={"estoque_minimo": 5}
    )

    assert resposta.status_code == 401


# ============================================================
# ACESSO ADMINISTRATIVO COM LOGIN
# ============================================================

def test_compras_com_login(cliente_teste):
    autenticar(cliente_teste)

    resposta = cliente_teste.get("/compras")

    assert resposta.status_code == 200
    assert isinstance(resposta.json(), list)


# ============================================================
# PROTECAO CSRF
# ============================================================

def test_cadastro_sem_csrf(cliente_teste):
    autenticar(cliente_teste)

    resposta = cliente_teste.post(
        "/produtos",
        json={
            "nome": "Produto Bloqueado",
            "preco": 10.0,
            "quantidade": 5
        }
    )

    assert resposta.status_code == 403


def test_estoque_com_csrf_invalido(cliente_teste):
    autenticar(cliente_teste)

    resposta = cliente_teste.patch(
        "/produtos/1/estoque",
        json={"quantidade": 10},
        headers={
            "X-CSRF-Token": "token-invalido"
        }
    )

    assert resposta.status_code == 403


# ============================================================
# ROTA PUBLICA
# ============================================================

def test_catalogo_publico(cliente_teste):
    resposta = cliente_teste.get("/produtos")

    assert resposta.status_code == 200
    assert isinstance(resposta.json(), list)

# ============================================================
# OPERACOES ADMINISTRATIVAS AUTORIZADAS
# ============================================================

def test_cadastrar_produto_autorizado(cliente_teste):
    csrf = autenticar(cliente_teste)

    resposta = cliente_teste.post(
        "/produtos",
        json={
            "nome": "Arroz Teste",
            "preco": 25.0,
            "quantidade": 50,
            "descricao": "Produto para teste",
            "categoria": "Alimentos"
        },
        headers={"X-CSRF-Token": csrf}
    )

    assert resposta.status_code == 200, resposta.text

    dados = resposta.json()

    assert dados["nome"] == "Arroz Teste"
    assert dados["quantidade"] == 50


def test_atualizar_estoque_autorizado(cliente_teste):
    csrf = autenticar(cliente_teste)

    cadastro = cliente_teste.post(
        "/produtos",
        json={
            "nome": "Feijao Teste",
            "preco": 8.50,
            "quantidade": 30
        },
        headers={"X-CSRF-Token": csrf}
    )

    assert cadastro.status_code == 200, cadastro.text

    produto_id = cadastro.json()["id"]

    resposta = cliente_teste.patch(
        f"/produtos/{produto_id}/estoque",
        json={"quantidade": 20},
        headers={"X-CSRF-Token": csrf}
    )

    assert resposta.status_code == 200, resposta.text
    assert resposta.json()["quantidade"] == 20


def test_configurar_estoque_minimo_autorizado(cliente_teste):
    csrf = autenticar(cliente_teste)

    cadastro = cliente_teste.post(
        "/produtos",
        json={
            "nome": "Cafe Teste",
            "preco": 12.0,
            "quantidade": 40
        },
        headers={"X-CSRF-Token": csrf}
    )

    assert cadastro.status_code == 200, cadastro.text

    produto_id = cadastro.json()["id"]

    resposta = cliente_teste.patch(
        f"/produtos/{produto_id}/estoque-minimo",
        json={"estoque_minimo": 10},
        headers={"X-CSRF-Token": csrf}
    )

    assert resposta.status_code == 200, resposta.text
    assert resposta.json()["estoque_minimo"] == 10


def test_listar_pedidos_autorizado(cliente_teste):
    autenticar(cliente_teste)

    resposta = cliente_teste.get("/pedidos")

    assert resposta.status_code == 200, resposta.text
    assert isinstance(resposta.json(), list)