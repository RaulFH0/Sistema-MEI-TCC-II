import sqlite3

from sqlalchemy import create_engine

from database.models import Base


def test_inicializacao_banco_novo(tmp_path):
    banco = tmp_path / "instalacao_nova.db"

    engine = create_engine(
        "sqlite:///" + banco.as_posix(),
        connect_args={"check_same_thread": False},
    )

    try:
        Base.metadata.create_all(bind=engine)

        # A conexao precisa ser fechada antes do fim do teste.
        with sqlite3.connect(banco) as conexao:
            tabela = conexao.execute(
                """
                SELECT COUNT(*)
                FROM sqlite_master
                WHERE type = 'table'
                AND name = 'solicitacoes_cadastro_mei'
                """
            ).fetchone()[0]

            indices = {
                linha[0]
                for linha in conexao.execute(
                    """
                    SELECT name
                    FROM sqlite_master
                    WHERE type = 'index'
                    AND tbl_name = 'solicitacoes_cadastro_mei'
                    """
                )
            }

            integridade = conexao.execute(
                "PRAGMA integrity_check"
            ).fetchone()[0]

        esperados = {
            "uq_solicitacao_mei_email_pendente",
            "uq_solicitacao_mei_cnpj_pendente",
            "uq_solicitacao_mei_cnpj_aprovado",
        }

        assert tabela == 1
        assert esperados <= indices
        assert integridade == "ok"

    finally:
        engine.dispose()
