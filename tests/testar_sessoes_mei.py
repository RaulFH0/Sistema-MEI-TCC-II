
import pytest

from datetime import datetime, timedelta, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from database.models import Base, SessaoAdmin
from database.contas_models import Estabelecimento, UsuarioMEI
from security.session_store import (
    criar_sessao,
    consultar_sessao,
    criar_sessao_mei,
    consultar_sessao_mei,
    revogar_sessao,
)


def agora():
    return datetime.now(timezone.utc).replace(tzinfo=None)


@pytest.fixture
def ambiente_mei():
    # Banco temporario, isolado do banco do projeto.
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
        expire_on_commit=False,
    )

    db = SessionTeste()

    try:
        loja1 = Estabelecimento(
            nome="Loja Teste 1",
            slug="loja-teste-1",
            ativo=True,
        )

        loja2 = Estabelecimento(
            nome="Loja Teste 2",
            slug="loja-teste-2",
            ativo=True,
        )

        db.add_all([loja1, loja2])
        db.flush()

        usuario1 = UsuarioMEI(
            estabelecimento_id=loja1.id,
            nome="Empreendedor Um",
            email="mei1@example.com",
            senha_hash="hash-ficticio-exclusivo-dos-testes",
            ativo=True,
        )

        usuario2 = UsuarioMEI(
            estabelecimento_id=loja2.id,
            nome="Empreendedor Dois",
            email="mei2@example.com",
            senha_hash="hash-ficticio-exclusivo-dos-testes",
            ativo=True,
        )

        db.add_all([usuario1, usuario2])
        db.commit()

        yield {
            "db": db,
            "loja1": loja1,
            "loja2": loja2,
            "usuario1": usuario1,
            "usuario2": usuario2,
        }

    finally:
        db.close()
        engine.dispose()


def test_sessao_mei_identifica_loja(ambiente_mei):
    db = ambiente_mei["db"]
    usuario = ambiente_mei["usuario1"]
    loja = ambiente_mei["loja1"]

    token = criar_sessao_mei(db, usuario.id)
    identidade = consultar_sessao_mei(db, token)

    assert identidade is not None
    assert identidade["usuario_mei_id"] == usuario.id
    assert identidade["estabelecimento_id"] == loja.id
    assert identidade["email"] == usuario.email


def test_sessoes_de_lojas_diferentes(ambiente_mei):
    db = ambiente_mei["db"]

    usuario1 = ambiente_mei["usuario1"]
    usuario2 = ambiente_mei["usuario2"]

    token1 = criar_sessao_mei(db, usuario1.id)
    token2 = criar_sessao_mei(db, usuario2.id)

    identidade1 = consultar_sessao_mei(db, token1)
    identidade2 = consultar_sessao_mei(db, token2)

    assert identidade1 is not None
    assert identidade2 is not None

    assert (
        identidade1["estabelecimento_id"]
        != identidade2["estabelecimento_id"]
    )


def test_sessao_mei_nao_e_admin_legado(ambiente_mei):
    db = ambiente_mei["db"]
    usuario = ambiente_mei["usuario1"]

    token = criar_sessao_mei(db, usuario.id)

    assert consultar_sessao(db, token) is None


def test_sessao_revogada(ambiente_mei):
    db = ambiente_mei["db"]
    usuario = ambiente_mei["usuario1"]

    token = criar_sessao_mei(db, usuario.id)

    assert revogar_sessao(db, token) is True
    assert consultar_sessao_mei(db, token) is None


def test_sessao_expirada(ambiente_mei):
    db = ambiente_mei["db"]
    usuario = ambiente_mei["usuario1"]

    token = criar_sessao_mei(db, usuario.id)

    sessao = db.query(SessaoAdmin).filter(
        SessaoAdmin.usuario_mei_id == usuario.id
    ).one()

    sessao.expira_em = agora() - timedelta(seconds=1)
    db.commit()

    assert consultar_sessao_mei(db, token) is None


def test_usuario_inativo(ambiente_mei):
    db = ambiente_mei["db"]
    usuario = ambiente_mei["usuario1"]

    token = criar_sessao_mei(db, usuario.id)

    usuario.ativo = False
    db.commit()

    assert consultar_sessao_mei(db, token) is None

    with pytest.raises(ValueError):
        criar_sessao_mei(db, usuario.id)


def test_estabelecimento_inativo(ambiente_mei):
    db = ambiente_mei["db"]
    usuario = ambiente_mei["usuario1"]
    loja = ambiente_mei["loja1"]

    token = criar_sessao_mei(db, usuario.id)

    loja.ativo = False
    db.commit()

    assert consultar_sessao_mei(db, token) is None

    with pytest.raises(ValueError):
        criar_sessao_mei(db, usuario.id)


def test_transferencia_invalida_sessao(ambiente_mei):
    db = ambiente_mei["db"]
    usuario = ambiente_mei["usuario1"]
    loja2 = ambiente_mei["loja2"]

    token = criar_sessao_mei(db, usuario.id)

    usuario.estabelecimento_id = loja2.id
    db.commit()

    assert consultar_sessao_mei(db, token) is None


def test_usuario_inexistente(ambiente_mei):
    db = ambiente_mei["db"]

    with pytest.raises(ValueError):
        criar_sessao_mei(db, 999999)


def test_admin_legado_continua_funcionando(ambiente_mei):
    db = ambiente_mei["db"]

    token = criar_sessao(db, "admin_teste")

    assert consultar_sessao(db, token) == "admin_teste"
    assert consultar_sessao_mei(db, token) is None
