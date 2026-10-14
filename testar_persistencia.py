
from pathlib import Path

from sqlalchemy import event
from sqlalchemy.engine import make_url

from database.models import (
    DATABASE_URL,
    SessionLocal,
    Produto,
    Pedido,
    engine
)
from database.crud import registrar_pedido_seguro


def main():
    url = make_url(DATABASE_URL)
    esperado = (
        Path(__file__).resolve().parent
        / "sistema_mei_teste.db"
    ).resolve()

    if (
        url.get_backend_name() != "sqlite"
        or not url.database
        or Path(url.database).resolve() != esperado
    ):
        raise RuntimeError(
            "Teste cancelado: banco experimental não selecionado."
        )

    # Banco SQLite temporário, isolado do banco experimental.
    from sqlalchemy.pool import StaticPool
    from sqlalchemy import create_engine
    from database.models import Base
    from sqlalchemy.orm import Session

    engine_teste = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool
    )

    Base.metadata.create_all(engine_teste)

    with Session(engine_teste) as db:
        db.add(Produto(
            nome="Arroz",
            preco=25.00,
            quantidade=50,
            categoria="Alimentos"
        ))
        db.add(Produto(
            nome="Feijão",
            preco=8.50,
            quantidade=40,
            categoria="Alimentos"
        ))
        db.commit()

        resultado = registrar_pedido_seguro(
            db=db,
            cliente_nome="Joao Teste",
            itens=[
                {"produto_nome": "Arroz", "quantidade": 2},
                {"produto_nome": "Feijão", "quantidade": 1}
            ]
        )

        arroz = db.query(Produto).filter_by(nome="Arroz").one()
        feijao = db.query(Produto).filter_by(nome="Feijão").one()
        pedidos = db.query(Pedido).all()

        assert arroz.quantidade == 48
        assert feijao.quantidade == 39
        assert len(pedidos) == 2
        assert abs(resultado["valor_total"] - 58.50) < 0.001

        print("TESTE APROVADO!")
        print("Pedido:", resultado)
        print("Estoque de Arroz:", arroz.quantidade)
        print("Estoque de Feijao:", feijao.quantidade)
        print("Registros de itens:", len(pedidos))

    engine_teste.dispose()


if __name__ == "__main__":
    main()
