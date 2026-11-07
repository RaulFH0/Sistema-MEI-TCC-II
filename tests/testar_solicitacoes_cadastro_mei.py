import pytest

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from database.models import Base, get_db
from database.contas_models import Estabelecimento, UsuarioMEI
from database.solicitacoes_models import SolicitacaoCadastroMEI
from security.auth import verificar_senha
from main import app


DADOS_VALIDOS = {
    "nome_completo": "Empreendedor de Teste",
    "email": "cadastro.teste@example.com",
    "cnpj": "11.222.333/0001-81",
    "telefone": "85999999999",
    "nome_estabelecimento": "Loja Teste Cadastro",
    "senha": "SenhaSeguraTeste!2026",
}


@pytest.fixture
def ambiente_cadastro():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def ativar_foreign_keys(conexao, registro):
        cursor = conexao.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(engine)

    SessaoTeste = sessionmaker(
        bind=engine,
        autoflush=False,
        expire_on_commit=False,
    )

    def obter_db_teste():
        db = SessaoTeste()
        try:
            yield db
        finally:
            db.close()

    anterior = app.dependency_overrides.get(get_db)
    app.dependency_overrides[get_db] = obter_db_teste

    cliente = TestClient(app)

    try:
        yield cliente, SessaoTeste
    finally:
        cliente.close()

        if anterior is None:
            app.dependency_overrides.pop(get_db, None)
        else:
            app.dependency_overrides[get_db] = anterior

        engine.dispose()


def test_cadastro_valido_fica_pendente(ambiente_cadastro):
    cliente, SessaoTeste = ambiente_cadastro

    resposta = cliente.post(
        "/cadastro-mei/solicitar",
        json=DADOS_VALIDOS,
    )

    assert resposta.status_code == 202, resposta.text
    assert resposta.json()["status"] == "pendente"

    with SessaoTeste() as db:
        solicitacoes = db.query(SolicitacaoCadastroMEI).all()

        assert len(solicitacoes) == 1
        assert solicitacoes[0].status == "pendente"
        assert solicitacoes[0].cnpj == "11222333000181"


def test_senha_protegida(ambiente_cadastro):
    cliente, SessaoTeste = ambiente_cadastro

    resposta = cliente.post(
        "/cadastro-mei/solicitar",
        json=DADOS_VALIDOS,
    )

    assert resposta.status_code == 202, resposta.text

    with SessaoTeste() as db:
        solicitacao = db.query(
            SolicitacaoCadastroMEI
        ).one()

        assert solicitacao.senha_hash != DADOS_VALIDOS["senha"]
        assert verificar_senha(
            DADOS_VALIDOS["senha"],
            solicitacao.senha_hash,
        )


def test_cadastro_nao_cria_usuario_ou_loja(ambiente_cadastro):
    cliente, SessaoTeste = ambiente_cadastro

    resposta = cliente.post(
        "/cadastro-mei/solicitar",
        json=DADOS_VALIDOS,
    )

    assert resposta.status_code == 202, resposta.text

    with SessaoTeste() as db:
        assert db.query(UsuarioMEI).count() == 0
        assert db.query(Estabelecimento).count() == 0


def test_solicitacao_duplicada_bloqueada(ambiente_cadastro):
    cliente, SessaoTeste = ambiente_cadastro

    primeira = cliente.post(
        "/cadastro-mei/solicitar",
        json=DADOS_VALIDOS,
    )

    segunda = cliente.post(
        "/cadastro-mei/solicitar",
        json=DADOS_VALIDOS,
    )

    assert primeira.status_code == 202, primeira.text
    assert segunda.status_code == 409, segunda.text

    with SessaoTeste() as db:
        assert db.query(SolicitacaoCadastroMEI).count() == 1


def test_cadastro_pendente_nao_permite_login(ambiente_cadastro):
    cliente, SessaoTeste = ambiente_cadastro

    cadastro = cliente.post(
        "/cadastro-mei/solicitar",
        json=DADOS_VALIDOS,
    )

    assert cadastro.status_code == 202, cadastro.text

    login = cliente.post(
        "/auth/mei/login",
        json={
            "email": DADOS_VALIDOS["email"],
            "senha": DADOS_VALIDOS["senha"],
        },
    )

    assert login.status_code == 401, login.text

    with SessaoTeste() as db:
        assert db.query(UsuarioMEI).count() == 0


def test_cnpj_ja_aprovado_nao_permite_nova_solicitacao(
    ambiente_cadastro,
):
    cliente, SessaoTeste = ambiente_cadastro

    with SessaoTeste.begin() as db:
        db.add(
            SolicitacaoCadastroMEI(
                nome_completo="Empreendedor Aprovado",
                email="aprovado@example.com",
                cnpj="11222333000181",
                telefone="85999999999",
                nome_estabelecimento="Loja Aprovada",
                senha_hash="hash-ficticio-exclusivo-do-teste",
                status="aprovado",
            )
        )

    nova_solicitacao = {
        **DADOS_VALIDOS,
        "email": "outro.empreendedor@example.com",
    }

    resposta = cliente.post(
        "/cadastro-mei/solicitar",
        json=nova_solicitacao,
    )

    assert resposta.status_code == 409, resposta.text

    with SessaoTeste() as db:
        assert db.query(SolicitacaoCadastroMEI).count() == 1
        assert (
            db.query(SolicitacaoCadastroMEI)
            .filter_by(status="pendente")
            .count()
        ) == 0
