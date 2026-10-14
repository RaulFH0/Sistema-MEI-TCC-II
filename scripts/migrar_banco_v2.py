
from pathlib import Path
import os
import sqlite3

from sqlalchemy import inspect
from sqlalchemy.engine import make_url

from database.models import (
    Base,
    engine,
    DATABASE_URL
)


def migrar():
    # Impede migração acidental do banco original.
    raiz = Path(__file__).resolve().parent.parent

    esperado = (
        raiz / "sistema_mei_teste.db"
    ).resolve()

    url = make_url(DATABASE_URL)

    if (
        url.get_backend_name() != "sqlite"
        or not url.database
        or Path(url.database).resolve() != esperado
    ):
        raise RuntimeError(
            "MIGRACAO CANCELADA: "
            "o banco experimental nao esta selecionado."
        )

    if not esperado.is_file():
        raise RuntimeError(
            "Banco experimental nao encontrado."
        )

    # Verifica integridade antes de alterar a estrutura.
    with sqlite3.connect(esperado) as conexao:
        integridade = conexao.execute(
            "PRAGMA integrity_check"
        ).fetchone()[0]

        if integridade != "ok":
            raise RuntimeError(
                f"Integridade invalida: {integridade}"
            )

    inspector = inspect(engine)

    tabelas_antes = set(
        inspector.get_table_names()
    )

    obrigatorias = {
        "produtos",
        "pedidos",
        "logs_sistema"
    }

    if not obrigatorias.issubset(tabelas_antes):
        raise RuntimeError(
            "Estrutura original incompleta."
        )

    # Cria somente as tabelas novas.
    Base.metadata.create_all(
        bind=engine,
        tables=[
            Base.metadata.tables["compras"],
            Base.metadata.tables["itens_compra"]
        ],
        checkfirst=True
    )

    tabelas_depois = set(
        inspect(engine).get_table_names()
    )

    esperadas = obrigatorias | {
        "compras",
        "itens_compra"
    }

    if not esperadas.issubset(tabelas_depois):
        raise RuntimeError(
            "As tabelas esperadas nao foram criadas."
        )

    with sqlite3.connect(esperado) as conexao:
        integridade_final = conexao.execute(
            "PRAGMA integrity_check"
        ).fetchone()[0]

        pedidos_antigos = conexao.execute(
            "SELECT COUNT(*) FROM pedidos"
        ).fetchone()[0]

        produtos = conexao.execute(
            "SELECT COUNT(*) FROM produtos"
        ).fetchone()[0]

        compras = conexao.execute(
            "SELECT COUNT(*) FROM compras"
        ).fetchone()[0]

        itens = conexao.execute(
            "SELECT COUNT(*) FROM itens_compra"
        ).fetchone()[0]

    print("=== MIGRACAO V2 ===")
    print("Integridade:", integridade_final)
    print("Produtos preservados:", produtos)
    print("Pedidos legados:", pedidos_antigos)
    print("Novas compras:", compras)
    print("Novos itens:", itens)
    print("Tabelas:", sorted(tabelas_depois))

    if integridade_final != "ok":
        raise RuntimeError(
            "Falha na verificacao final."
        )

    print("MIGRACAO CONCLUIDA!")


if __name__ == "__main__":
    migrar()
