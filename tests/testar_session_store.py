
from datetime import datetime, timedelta

import pytest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from database.models import Base, SessaoAdmin

from security.session_store import (
    criar_sessao,
    consultar_sessao,
    revogar_sessao,
)


@pytest.fixture
def db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    Base.metadata.create_all(bind=engine)

    SessionTeste = sessionmaker(bind=engine)
    sessao = SessionTeste()

    try:
        yield sessao
    finally:
        sessao.close()
        engine.dispose()


def test_criar_e_consultar_sessao(db):
    token = criar_sessao(db, "admin")

    assert consultar_sessao(db, token) == "admin"


def test_token_nao_e_salvo_em_texto_puro(db):
    token = criar_sessao(db, "admin")

    registro = db.query(SessaoAdmin).one()

    assert registro.token_hash != token
    assert len(registro.token_hash) == 64


def test_token_desconhecido(db):
    assert consultar_sessao(db, "token-desconhecido") is None


def test_revogar_sessao(db):
    token = criar_sessao(db, "admin")

    assert revogar_sessao(db, token) is True
    assert consultar_sessao(db, token) is None


def test_revogacao_repetida(db):
    token = criar_sessao(db, "admin")

    assert revogar_sessao(db, token) is True
    assert revogar_sessao(db, token) is False


def test_sessao_expirada(db):
    token = criar_sessao(db, "admin")

    registro = db.query(SessaoAdmin).one()
    registro.expira_em = (
        datetime.utcnow() - timedelta(minutes=1)
    )
    db.commit()

    assert consultar_sessao(db, token) is None


def test_usuario_invalido(db):
    with pytest.raises(ValueError):
        criar_sessao(db, "")


def test_tokens_diferentes(db):
    primeiro = criar_sessao(db, "admin")
    segundo = criar_sessao(db, "admin")

    assert primeiro != segundo
    assert consultar_sessao(db, primeiro) == "admin"
    assert consultar_sessao(db, segundo) == "admin"
