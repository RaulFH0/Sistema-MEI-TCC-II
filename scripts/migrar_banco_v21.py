
from pathlib import Path
import sqlite3

from database.models import DATABASE_URL
from sqlalchemy.engine import make_url


def migrar():
    raiz = Path(__file__).resolve().parent.parent
    esperado = (raiz / "sistema_mei_teste.db").resolve()

    url = make_url(DATABASE_URL)

    if (
        url.get_backend_name() != "sqlite"
        or not url.database
        or Path(url.database).resolve() != esperado
    ):
        raise RuntimeError(
            "Migracao cancelada: banco de testes nao selecionado."
        )

    if not esperado.is_file():
        raise RuntimeError("Banco experimental inexistente.")

    with sqlite3.connect(esperado) as db:
        db.execute("PRAGMA foreign_keys=ON")

        integridade = db.execute(
            "PRAGMA integrity_check"
        ).fetchone()[0]

        if integridade != "ok":
            raise RuntimeError("Banco com integridade invalida.")

        colunas = {
            coluna[1]
            for coluna in db.execute(
                "PRAGMA table_info(compras)"
            )
        }

        if not colunas:
            raise RuntimeError("Tabela compras nao encontrada.")

        if "hash_solicitacao" not in colunas:
            db.execute(
                "ALTER TABLE compras "
                "ADD COLUMN hash_solicitacao VARCHAR(64)"
            )

        db.commit()

        print("Integridade:", db.execute(
            "PRAGMA integrity_check"
        ).fetchone()[0])

        print("Compras existentes:", db.execute(
            "SELECT COUNT(*) FROM compras"
        ).fetchone()[0])

        print("Migracao V2.1 concluida!")


if __name__ == "__main__":
    migrar()
