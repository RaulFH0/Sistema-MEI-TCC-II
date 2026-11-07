import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from main import app
from database.models import Base, get_db
from database.solicitacoes_models import SolicitacaoCadastroMEI
from database.contas_models import UsuarioMEI, Estabelecimento
from security.session_store import criar_sessao
from security.routes import COOKIE_SESSAO, _token_csrf


@pytest.fixture
def ambiente(monkeypatch):
    monkeypatch.setenv(
        "SESSION_SECRET",
        "segredo-exclusivo-de-testes-com-mais-de-32-caracteres"
    )

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def ativar_fk(conexao, registro):
        cursor = conexao.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(engine)

    Sessao = sessionmaker(
        bind=engine,
        autoflush=False,
        expire_on_commit=False,
    )

    def obter_db_teste():
        with Sessao() as db:
            yield db

    anteriores = dict(app.dependency_overrides)
    app.dependency_overrides[get_db] = obter_db_teste

    cliente = TestClient(app)

    try:
        with Sessao.begin() as db:
            pedido = SolicitacaoCadastroMEI(
                nome_completo="MEI Seguranca Teste",
                email="seguranca-mei@example.com",
                cnpj="11222333000181",
                telefone="85999999999",
                nome_estabelecimento="Loja Seguranca Teste",
                senha_hash="hash-ficticio-apenas-para-testes",
                status="pendente",
            )
            db.add(pedido)
            db.flush()
            pedido_id = pedido.id

        yield cliente, Sessao, pedido_id

    finally:
        cliente.close()
        app.dependency_overrides.clear()
        app.dependency_overrides.update(anteriores)
        engine.dispose()


def autenticar_admin_real(cliente, Sessao):
    with Sessao() as db:
        token = criar_sessao(db, "admin_seguranca_teste")

    cliente.cookies.set(COOKIE_SESSAO, token)
    return _token_csrf(token)


def test_sem_sessao_nao_lista_solicitacoes(ambiente):
    cliente, _, _ = ambiente

    resposta = cliente.get("/admin/solicitacoes-mei")

    assert resposta.status_code == 401, resposta.text


def test_sem_sessao_nao_aprova(ambiente):
    cliente, Sessao, pedido_id = ambiente

    resposta = cliente.post(
        f"/admin/solicitacoes-mei/{pedido_id}/aprovar"
    )

    assert resposta.status_code == 401, resposta.text

    with Sessao() as db:
        assert db.query(UsuarioMEI).count() == 0
        assert db.query(Estabelecimento).count() == 0


def test_sessao_valida_sem_csrf_nao_aprova(ambiente):
    cliente, Sessao, pedido_id = ambiente

    autenticar_admin_real(cliente, Sessao)

    resposta = cliente.post(
        f"/admin/solicitacoes-mei/{pedido_id}/aprovar"
    )

    assert resposta.status_code == 403, resposta.text

    with Sessao() as db:
        pedido = db.get(SolicitacaoCadastroMEI, pedido_id)
        assert pedido.status == "pendente"
        assert db.query(UsuarioMEI).count() == 0


def test_csrf_incorreto_nao_aprova(ambiente):
    cliente, Sessao, pedido_id = ambiente

    autenticar_admin_real(cliente, Sessao)

    resposta = cliente.post(
        f"/admin/solicitacoes-mei/{pedido_id}/aprovar",
        headers={"X-CSRF-Token": "token-invalido"},
    )

    assert resposta.status_code == 403, resposta.text

    with Sessao() as db:
        assert db.query(UsuarioMEI).count() == 0


def test_sessao_e_csrf_validos_permitem_aprovacao(ambiente):
    cliente, Sessao, pedido_id = ambiente

    csrf = autenticar_admin_real(cliente, Sessao)

    resposta = cliente.post(
        f"/admin/solicitacoes-mei/{pedido_id}/aprovar",
        headers={"X-CSRF-Token": csrf},
    )

    assert resposta.status_code == 200, resposta.text

    with Sessao() as db:
        pedido = db.get(SolicitacaoCadastroMEI, pedido_id)

        assert pedido.status == "aprovado"
        assert pedido.analisado_por == "admin_seguranca_teste"
        assert db.query(UsuarioMEI).count() == 1
        assert db.query(Estabelecimento).count() == 1
