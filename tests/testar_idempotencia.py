
from sqlalchemy import create_engine, select, func
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from database.models import Base, Produto, Compra, ItemCompra
from database.crud import registrar_compra_segura


engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool
)

Base.metadata.create_all(engine)


def consultar_estoque(db, nome):
    db.expire_all()
    return db.query(Produto).filter_by(nome=nome).one().quantidade


try:
    with Session(engine) as db:

        db.add_all([
            Produto(
                nome="Arroz",
                preco=25.00,
                quantidade=50,
                categoria="Alimentos"
            ),
            Produto(
                nome="Feijão",
                preco=8.50,
                quantidade=40,
                categoria="Alimentos"
            )
        ])
        db.commit()

        itens = [
            {"produto_nome": "Arroz", "quantidade": 2},
            {"produto_nome": "Feijão", "quantidade": 1}
        ]

        chave = "teste-idempotencia-001"

        # PRIMEIRA CHAMADA
        primeiro = registrar_compra_segura(
            db=db,
            cliente_nome="Joao Teste",
            itens=itens,
            chave_idempotencia=chave
        )

        assert primeiro["pedido_confirmado"] is True
        assert primeiro["requisicao_repetida"] is False
        assert primeiro["valor_total"] == 58.50

        assert consultar_estoque(db, "Arroz") == 48
        assert consultar_estoque(db, "Feijão") == 39

        print("TESTE 1: Primeira compra registrada.")

        # SEGUNDA CHAMADA COM A MESMA CHAVE
        segundo = registrar_compra_segura(
            db=db,
            cliente_nome="Joao Teste",
            itens=itens,
            chave_idempotencia=chave
        )

        assert segundo["compra_id"] == primeiro["compra_id"]
        assert segundo["requisicao_repetida"] is True

        assert consultar_estoque(db, "Arroz") == 48
        assert consultar_estoque(db, "Feijão") == 39

        assert db.query(Compra).count() == 1
        assert db.query(ItemCompra).count() == 2

        print("TESTE 2: Reenvio não duplicou a compra.")

        # TERCEIRA CHAMADA: MESMA CHAVE, CONTEÚDO DIFERENTE
        try:
            registrar_compra_segura(
                db=db,
                cliente_nome="Joao Teste",
                itens=[
                    {"produto_nome": "Arroz", "quantidade": 3}
                ],
                chave_idempotencia=chave
            )
        except ValueError:
            print("TESTE 3: Conflito de chave rejeitado.")
        else:
            raise AssertionError(
                "Falha: chave reutilizada com dados diferentes."
            )

        assert consultar_estoque(db, "Arroz") == 48
        assert consultar_estoque(db, "Feijão") == 39
        assert db.query(Compra).count() == 1
        assert db.query(ItemCompra).count() == 2

        print("\nTODOS OS TESTES DE IDEMPOTENCIA APROVADOS!")

finally:
    engine.dispose()
