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


DADOS = {
    "nome_completo": "Empreendedor Teste Integrado",
    "email": "fluxo.mei@example.com",
    "cnpj": "11.222.333/0001-81",
    "telefone": "85999999999",
    "nome_estabelecimento": "Loja Integrada Teste",
    "senha": "SenhaSeguraIntegracao!2026",
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

    # Sem entrar no contexto do TestClient:
    # nao executa o lifespan e nao carrega o RAG.
    cliente = TestClient(app)

    try:
        yield cliente, Sessao
    finally:
        cliente.close()
        app.dependency_overrides.clear()
        app.dependency_overrides.update(anteriores)
        engine.dispose()


def autorizar_admin_teste():
    return "admin_teste_integracao"


def habilitar_admin_teste():
    # Substituicao apenas para testar as regras de negocio.
    # Nao equivale a validar login e CSRF administrativos reais.
    app.dependency_overrides[exigir_admin] = autorizar_admin_teste
    app.dependency_overrides[exigir_admin_escrita] = autorizar_admin_teste


def solicitar(cliente):
    resposta = cliente.post(
        "/cadastro-mei/solicitar",
        json=DADOS,
    )
    assert resposta.status_code == 202, resposta.text
    return resposta


def tentar_login(cliente):
    return cliente.post(
        "/auth/mei/login",
        json={
            "email": DADOS["email"],
            "senha": DADOS["senha"],
        },
    )


def test_aprovacao_permite_primeiro_login(ambiente):
    cliente, Sessao = ambiente

    # 1. Empreendedor solicita cadastro.
    solicitar(cliente)

    with Sessao() as db:
        pedido = db.query(SolicitacaoCadastroMEI).one()
        pedido_id = pedido.id
        assert pedido.status == "pendente"
        assert db.query(UsuarioMEI).count() == 0

    # 2. Cadastro pendente nao permite login.
    antes = tentar_login(cliente)
    assert antes.status_code == 401, antes.text

    # 3. Administrador aprova a solicitacao.
    habilitar_admin_teste()

    aprovacao = cliente.post(
        f"/admin/solicitacoes-mei/{pedido_id}/aprovar"
    )
    assert aprovacao.status_code == 200, aprovacao.text

    dados_aprovacao = aprovacao.json()
    assert dados_aprovacao["slug"] == (
        f"mei-solicitacao-{pedido_id}"
    )

    # 4. Validar os vinculos no banco temporario.
    with Sessao() as db:
        pedido = db.get(SolicitacaoCadastroMEI, pedido_id)
        usuario = db.query(UsuarioMEI).one()
        loja = db.query(Estabelecimento).one()

        assert pedido.status == "aprovado"
        assert usuario.estabelecimento_id == loja.id
        assert usuario.ativo is True
        assert loja.ativo is True
        assert usuario.email == DADOS["email"]

        estabelecimento_id = loja.id

    # 5. Retirar a simulacao do administrador.
    app.dependency_overrides.pop(exigir_admin, None)
    app.dependency_overrides.pop(exigir_admin_escrita, None)

    # 6. Agora o empreendedor consegue fazer login.
    login = tentar_login(cliente)
    assert login.status_code == 200, login.text

    sessao = login.json()
    assert sessao["autenticado"] is True
    assert sessao["estabelecimento_id"] == estabelecimento_id
    assert sessao["csrf_token"]

    # 7. Sua sessao pode ser consultada.
    consulta = cliente.get("/auth/mei/me")
    assert consulta.status_code == 200, consulta.text
    assert (
        consulta.json()["estabelecimento_id"]
        == estabelecimento_id
    )

    # 8. Acesso ao catalogo privado do MEI.
    produtos = cliente.get("/mei/produtos")
    assert produtos.status_code == 200, produtos.text
    assert produtos.json() == []

    # 9. Encerrar a sessao usando CSRF.
    saida = cliente.post(
        "/auth/mei/logout",
        headers={
            "X-CSRF-Token": sessao["csrf_token"],
        },
    )
    assert saida.status_code == 200, saida.text

    depois = cliente.get("/auth/mei/me")
    assert depois.status_code == 401


def test_rejeicao_impede_login(ambiente):
    cliente, Sessao = ambiente

    solicitar(cliente)

    with Sessao() as db:
        pedido_id = db.query(SolicitacaoCadastroMEI).one().id

    habilitar_admin_teste()

    rejeicao = cliente.post(
        f"/admin/solicitacoes-mei/{pedido_id}/rejeitar",
        json={"observacao": "Reprovado no teste."},
    )
    assert rejeicao.status_code == 200, rejeicao.text

    app.dependency_overrides.pop(exigir_admin, None)
    app.dependency_overrides.pop(exigir_admin_escrita, None)

    login = tentar_login(cliente)
    assert login.status_code == 401, login.text

    with Sessao() as db:
        pedido = db.get(SolicitacaoCadastroMEI, pedido_id)

        assert pedido.status == "rejeitado"
        assert db.query(UsuarioMEI).count() == 0
        assert db.query(Estabelecimento).count() == 0
