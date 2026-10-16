
import sqlite3
from pathlib import Path

CAMINHO_BANCO = Path("sistema_mei_teste.db")


def migrar():
    if not CAMINHO_BANCO.exists():
        raise FileNotFoundError(
            f"Banco não encontrado: {CAMINHO_BANCO.resolve()}"
        )

    conexao = sqlite3.connect(CAMINHO_BANCO)

    try:
        colunas = {
            coluna[1]
            for coluna in conexao.execute(
                "PRAGMA table_info(produtos)"
            ).fetchall()
        }

        if not colunas:
            raise RuntimeError(
                "A tabela produtos não foi encontrada."
            )

        if "estoque_minimo" in colunas:
            print("Migração já aplicada.")
            return

        conexao.execute(
            """
            ALTER TABLE produtos
            ADD COLUMN estoque_minimo
            INTEGER NOT NULL DEFAULT 5
            CHECK (estoque_minimo >= 0)
            """
        )

        conexao.commit()

        print("Migração concluída com sucesso.")
        print("Estoque mínimo inicial: 5 unidades.")

    finally:
        conexao.close()


if __name__ == "__main__":
    migrar()
