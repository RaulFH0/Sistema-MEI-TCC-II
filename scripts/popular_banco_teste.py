
from pathlib import Path

from database.models import (
    DATABASE_URL,
    SessionLocal,
    Produto,
    init_db
)

# Estoques fictícios exclusivamente para experimentos.
# Os preços são os valores do catalogo.txt.
PRODUTOS_TESTE = [
    ("Arroz", 25.00, 50, "Pacote de 5kg", "Alimentos"),
    ("Feijão", 8.50, 40, "Pacote de 1kg", "Alimentos"),
    ("Açúcar", 4.80, 60, "Pacote de 1kg", "Alimentos"),
    ("Óleo de soja", 7.20, 35, "Garrafa de 900ml", "Alimentos"),
    ("Farinha de trigo", 5.50, 45, "Pacote de 1kg", "Alimentos"),
    ("Macarrão", 4.00, 70, "Pacote de 500g", "Alimentos"),
    ("Sal", 2.50, 55, "Pacote de 1kg", "Alimentos"),
    ("Café", 12.00, 30, "Pacote de 250g", "Alimentos"),
]


def popular_banco():
    # Impede que este script modifique o banco original.
    banco_esperado = (
        Path(__file__).resolve().parent.parent
        / "sistema_mei_teste.db"
    ).resolve()

    url_esperada = (
        f"sqlite:///{banco_esperado.as_posix()}"
    )

    # Normaliza o destino do banco antes de comparar.
    from sqlalchemy.engine import make_url

    url = make_url(DATABASE_URL)

    if url.get_backend_name() != "sqlite":
        raise RuntimeError("Banco não é SQLite.")

    if url.database in (None, ":memory:"):
        raise RuntimeError("Banco de testes inválido.")

    destino = Path(url.database).resolve()

    if destino != banco_esperado:
        raise RuntimeError(
            "OPERAÇÃO CANCELADA: DATABASE_URL não "
            "aponta para sistema_mei_teste.db"
        )

    print("Banco experimental:", destino)

    init_db()
    db = SessionLocal()

    try:
        existentes = db.query(Produto).all()

        # Evita inserir os mesmos produtos duas vezes.
        if existentes:
            print(
                "Banco já contém produtos. "
                "Nenhuma alteração realizada."
            )
            for produto in existentes:
                print(
                    produto.id,
                    produto.nome,
                    produto.quantidade
                )
            return

        for nome, preco, qtd, descricao, categoria in PRODUTOS_TESTE:
            db.add(
                Produto(
                    nome=nome,
                    preco=preco,
                    quantidade=qtd,
                    descricao=descricao,
                    categoria=categoria
                )
            )

        db.commit()
        print("8 produtos experimentais cadastrados.")

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()


if __name__ == "__main__":
    popular_banco()
