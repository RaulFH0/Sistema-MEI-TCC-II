import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from main import app
from database.models import Base, get_db
from database.contas_models import Estabelecimento, UsuarioMEI
from database.solicitacoes_models import SolicitacaoCadastroMEI
from security.routes import exigir_admin, exigir_admin_escrita
from security.auth import gerar_hash_senha


DADOS = {
    "nome_completo": "Empreendedor de Teste",
    "email": "aprovacao.teste@example.com",
    "cnpj": "11222333000181",
    "telefone": "85999999999",
    "nome_estabelecimento": "Loja Aprova??o Teste",
    "senha": "SenhaSeguraTeste!2026",
}


@pytest.fixture
def ambiente():
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

    Base.metadata.create_all(bind=engine)

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

    try:
        with TestClient(app) as cliente:
            yield cliente, Sessao
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(anteriores)
        engine.dispose()


def autorizar_admin_teste():
    return "admin_teste"


def habilitar_admin():
    app.dependency_overrides[exigir_admin] = (
        autorizar_admin_teste
    )
    app.dependency_overrides[exigir_admin_escrita] = (
        autorizar_admin_teste
    )


def criar_solicitacao(Sessao):
    with Sessao.begin() as db:
        pedido = SolicitacaoCadastroMEI(
            nome_completo=DADOS["nome_completo"],
            email=DADOS["email"],
            cnpj=DADOS["cnpj"],
            telefone=DADOS["telefone"],
            nome_estabelecimento=DADOS["nome_estabelecimento"],
            senha_hash=gerar_hash_senha(DADOS["senha"]),
            status="pendente",
        )
        db.add(pedido)
        db.flush()
        return pedido.id


def test_acesso_sem_admin_bloqueado(ambiente):
    cliente, Sessao = ambiente
    pedido_id = criar_solicitacao(Sessao)

    lista = cliente.get("/admin/solicitacoes-mei")
    aprovacao = cliente.post(
        f"/admin/solicitacoes-mei/{pedido_id}/aprovar"
    )
    rejeicao = cliente.post(
        f"/admin/solicitacoes-mei/{pedido_id}/rejeitar",
        json={"observacao": "Teste"},
    )

    assert lista.status_code == 401
    assert aprovacao.status_code == 401
    assert rejeicao.status_code == 401

    with Sessao() as db:
        assert db.query(UsuarioMEI).count() == 0
        assert db.query(Estabelecimento).count() == 0


def test_listagem_nao_expoe_senha(ambiente):
    cliente, Sessao = ambiente
    criar_solicitacao(Sessao)
    habilitar_admin()

    resposta = cliente.get("/admin/solicitacoes-mei")

    assert resposta.status_code == 200, resposta.text
    dados = resposta.json()
    assert len(dados) == 1
    assert dados[0]["status"] == "pendente"
    assert "senha_hash" not in dados[0]
    assert "senha" not in dados[0]


def test_aprovacao_cria_loja_e_usuario(ambiente):
    cliente, Sessao = ambiente
    pedido_id = criar_solicitacao(Sessao)
    habilitar_admin()

    resposta = cliente.post(
        f"/admin/solicitacoes-mei/{pedido_id}/aprovar"
    )

    assert resposta.status_code == 200, resposta.text
    dados = resposta.json()
    assert dados["slug"] == f"mei-solicitacao-{pedido_id}"

    with Sessao() as db:
        pedido = db.get(SolicitacaoCadastroMEI, pedido_id)
        usuario = db.query(UsuarioMEI).one()
        loja = db.query(Estabelecimento).one()

        assert pedido.status == "aprovado"
        assert pedido.analisado_por == "admin_teste"
        assert usuario.ativo is True
        assert loja.ativo is True
        assert usuario.estabelecimento_id == loja.id
        assert usuario.senha_hash == pedido.senha_hash


def test_aprovacao_repetida_bloqueada(ambiente):
    cliente, Sessao = ambiente
    pedido_id = criar_solicitacao(Sessao)
    habilitar_admin()

    url = f"/admin/solicitacoes-mei/{pedido_id}/aprovar"

    primeira = cliente.post(url)
    segunda = cliente.post(url)

    assert primeira.status_code == 200, primeira.text
    assert segunda.status_code == 409, segunda.text

    with Sessao() as db:
        assert db.query(UsuarioMEI).count() == 1
        assert db.query(Estabelecimento).count() == 1


def test_rejeicao_nao_cria_conta(ambiente):
    cliente, Sessao = ambiente
    pedido_id = criar_solicitacao(Sessao)
    habilitar_admin()

    resposta = cliente.post(
        f"/admin/solicitacoes-mei/{pedido_id}/rejeitar",
        json={"observacao": "Dados nao confirmados"},
    )

    assert resposta.status_code == 200, resposta.text

    with Sessao() as db:
        pedido = db.get(SolicitacaoCadastroMEI, pedido_id)

        assert pedido.status == "rejeitado"
        assert pedido.analisado_por == "admin_teste"
        assert pedido.observacao_admin == "Dados nao confirmados"
        assert db.query(UsuarioMEI).count() == 0
        assert db.query(Estabelecimento).count() == 0


def test_nao_aprova_solicitacao_rejeitada(ambiente):
    cliente, Sessao = ambiente
    pedido_id = criar_solicitacao(Sessao)
    habilitar_admin()

    rejeicao = cliente.post(
        f"/admin/solicitacoes-mei/{pedido_id}/rejeitar",
        json={"observacao": "Nao aprovado"},
    )

    aprovacao = cliente.post(
        f"/admin/solicitacoes-mei/{pedido_id}/aprovar"
    )

    assert rejeicao.status_code == 200, rejeicao.text
    assert aprovacao.status_code == 409, aprovacao.text

    with Sessao() as db:
        assert db.query(UsuarioMEI).count() == 0


def test_solicitacao_inexistente(ambiente):
    cliente, Sessao = ambiente
    habilitar_admin()

    aprovacao = cliente.post(
        "/admin/solicitacoes-mei/999999/aprovar"
    )
    rejeicao = cliente.post(
        "/admin/solicitacoes-mei/999999/rejeitar",
        json={"observacao": "Teste"},
    )

    assert aprovacao.status_code == 404
    assert rejeicao.status_code == 404
