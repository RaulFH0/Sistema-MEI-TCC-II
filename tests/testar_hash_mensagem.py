
import hashlib

from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from database.models import Base, Produto, Compra
from database.crud import registrar_compra_segura


engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool
)

Base.metadata.create_all(engine)

mensagem = "Sou Joao e quero comprar 2 Arroz."

itens = [
    {"produto_nome": "Arroz", "quantidade": 2}
]

try:
    with Session(engine) as db:
        db.add(
            Produto(
                nome="Arroz",
                preco=25.00,
                quantidade=50,
                categoria="Alimentos"
            )
        )
        db.commit()

        print("=== TESTE 1: REGISTRAR HASH ===")

        primeira = registrar_compra_segura(
            db=db,
            cliente_nome="Joao",
            itens=itens,
            chave_idempotencia="hash-v22-001",
            mensagem_original=mensagem
        )

        compra = db.query(Compra).filter_by(
            chave_idempotencia="hash-v22-001"
        ).one()

        esperado = hashlib.sha256(
            mensagem.encode("utf-8")
        ).hexdigest()

        assert compra.hash_mensagem == esperado
        assert primeira["requisicao_repetida"] is False

        print("TESTE 1 APROVADO!")

        print("\n=== TESTE 2: MENSAGEM IGUAL ===")

        segunda = registrar_compra_segura(
            db=db,
            cliente_nome="Joao",
            itens=itens,
            chave_idempotencia="hash-v22-001",
            mensagem_original=mensagem
        )

        assert segunda["requisicao_repetida"] is True
        assert segunda["compra_id"] == primeira["compra_id"]

        print("TESTE 2 APROVADO!")

        print("\n=== TESTE 3: MENSAGEM DIFERENTE ===")

        try:
            registrar_compra_segura(
                db=db,
                cliente_nome="Joao",
                itens=itens,
                chave_idempotencia="hash-v22-001",
                mensagem_original="Mensagem alterada."
            )
        except ValueError:
            print("TESTE 3 APROVADO!")
        else:
            raise AssertionError(
                "Mensagem diferente foi aceita."
            )

        print("\n=== TESTE 4: ESTOQUE PRESERVADO ===")

        db.expire_all()

        produto = db.query(Produto).filter_by(
            nome="Arroz"
        ).one()

        assert produto.quantidade == 48
        assert db.query(Compra).count() == 1

        print("TESTE 4 APROVADO!")

        print(
            "\nTODOS OS TESTES DO HASH V2.2 APROVADOS!"
        )

finally:
    engine.dispose()
