
from pathlib import Path

from sqlalchemy import create_engine, text

RAIZ = Path(__file__).resolve().parent.parent
BANCO = RAIZ / "sistema_mei_teste.db"


def migrar():
    if not BANCO.is_file():
        raise FileNotFoundError(
            f"Banco experimental nao encontrado: {BANCO}"
        )

    engine = create_engine(
        f"sqlite:///{BANCO.as_posix()}"
    )

    try:
        with engine.begin() as conexao:
            tabelas = conexao.execute(
                text(
                    "SELECT name FROM sqlite_master "
                    "WHERE type = 'table'"
                )
            ).scalars().all()

            if "compras" not in tabelas:
                raise RuntimeError(
                    "Tabela compras nao encontrada."
                )

            colunas = conexao.execute(
                text("PRAGMA table_info(compras)")
            ).mappings().all()

            nomes = {coluna["name"] for coluna in colunas}

            if "hash_mensagem" not in nomes:
                conexao.execute(
                    text(
                        "ALTER TABLE compras "
                        "ADD COLUMN hash_mensagem VARCHAR(64)"
                    )
                )
                print("Coluna hash_mensagem criada.")
            else:
                print("Coluna hash_mensagem ja existe.")

            integridade = conexao.execute(
                text("PRAGMA integrity_check")
            ).scalar()

            violacoes_fk = conexao.execute(
                text("PRAGMA foreign_key_check")
            ).fetchall()

            total_compras = conexao.execute(
                text("SELECT COUNT(*) FROM compras")
            ).scalar()

            total_itens = conexao.execute(
                text("SELECT COUNT(*) FROM itens_compra")
            ).scalar()

            print("Integridade SQLite:", integridade)
            print("Violacoes de FK:", len(violacoes_fk))
            print("Compras preservadas:", total_compras)
            print("Itens preservados:", total_itens)

            if integridade != "ok" or violacoes_fk:
                raise RuntimeError(
                    "Falha na verificacao de integridade."
                )

        print("\nMIGRACAO V2.2 CONCLUIDA!")

    finally:
        engine.dispose()


if __name__ == "__main__":
    migrar()
