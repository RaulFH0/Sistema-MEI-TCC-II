import pytest

from sqlalchemy import create_engine, inspect
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from database.solicitacoes_models import (
    SolicitacaoCadastroMEI,
)


@pytest.fixture
def banco():
    engine = create_engine("sqlite:///:memory:")
    SolicitacaoCadastroMEI.__table__.create(bind=engine)

    try:
        yield engine
    finally:
        engine.dispose()


def inserir(session, email, cnpj, status):
    session.add(
        SolicitacaoCadastroMEI(
            nome_completo="Pessoa Teste",
            email=email,
            cnpj=cnpj,
            telefone="85999999999",
            nome_estabelecimento="Loja Teste",
            senha_hash="hash-ficticio-de-teste",
            status=status,
        )
    )
    session.flush()


def test_indice_aprovado_existe(banco):
    indices = {
        item["name"]
        for item in inspect(banco).get_indexes(
            "solicitacoes_cadastro_mei"
        )
    }

    assert (
        "uq_solicitacao_mei_cnpj_aprovado"
        in indices
    )


def test_impede_dois_cnpjs_aprovados(banco):
    with Session(banco) as session:
        inserir(
            session,
            "primeiro@example.com",
            "11222333000181",
            "aprovado",
        )
        session.commit()

    with Session(banco) as session:
        with pytest.raises(IntegrityError):
            inserir(
                session,
                "segundo@example.com",
                "11222333000181",
                "aprovado",
            )
        session.rollback()

    with Session(banco) as session:
        registros = session.query(
            SolicitacaoCadastroMEI
        ).filter_by(
            cnpj="11222333000181",
            status="aprovado",
        ).count()

        assert registros == 1


def test_rejeicoes_historicas_sao_permitidas(banco):
    with Session(banco) as session:
        inserir(
            session,
            "rejeitado1@example.com",
            "11222333000181",
            "rejeitado",
        )
        inserir(
            session,
            "rejeitado2@example.com",
            "11222333000181",
            "rejeitado",
        )
        session.commit()

    with Session(banco) as session:
        assert session.query(
            SolicitacaoCadastroMEI
        ).filter_by(
            cnpj="11222333000181",
            status="rejeitado",
        ).count() == 2


def test_aprovado_e_pendente_podem_coexistir(banco):
    with Session(banco) as session:
        inserir(
            session,
            "aprovado@example.com",
            "11222333000181",
            "aprovado",
        )
        inserir(
            session,
            "pendente@example.com",
            "11222333000181",
            "pendente",
        )
        session.commit()

    with Session(banco) as session:
        assert session.query(
            SolicitacaoCadastroMEI
        ).filter_by(
            cnpj="11222333000181",
        ).count() == 2
