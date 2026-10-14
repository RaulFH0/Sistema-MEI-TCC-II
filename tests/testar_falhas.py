
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from database.models import Base, Produto, Pedido
from database.crud import registrar_pedido_seguro


def criar_banco_temporario():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool
    )

    Base.metadata.create_all(engine)
    return engine


def cadastrar_produtos(db):
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
            quantidade=10,
            categoria="Alimentos"
        )
    ])
    db.commit()


def verificar_estado(db, arroz, feijao):
    db.expire_all()

    produto_arroz = db.query(Produto).filter_by(
        nome="Arroz"
    ).one()

    produto_feijao = db.query(Produto).filter_by(
        nome="Feijão"
    ).one()

    assert produto_arroz.quantidade == arroz
    assert produto_feijao.quantidade == feijao
    assert db.query(Pedido).count() == 0


def executar_teste(nome, itens, mensagem_esperada):
    engine = criar_banco_temporario()

    try:
        with Session(engine) as db:
            cadastrar_produtos(db)

            print(f"\n=== {nome} ===")

            try:
                registrar_pedido_seguro(
                    db=db,
                    cliente_nome="Joao Teste",
                    itens=itens
                )
            except ValueError as erro:
                print("Pedido rejeitado:", erro)

                assert mensagem_esperada in str(erro), (
                    "O pedido foi rejeitado por um motivo "
                    "diferente do esperado."
                )
            else:
                raise AssertionError(
                    "FALHA: pedido inválido foi aceito."
                )

            verificar_estado(
                db,
                arroz=50,
                feijao=10
            )

            print("Estoque preservado.")
            print("Nenhum pedido registrado.")
            print("TESTE APROVADO!")

    finally:
        engine.dispose()


def main():
    # TESTE 1: ultrapassar limite comercial
    executar_teste(
        nome="TESTE 1 - LIMITE DE QUANTIDADE",
        itens=[
            {
                "produto_nome": "Arroz",
                "quantidade": 100
            }
        ],
        mensagem_esperada="entre 1 e 50"
    )

    # TESTE 2: estoque insuficiente
    executar_teste(
        nome="TESTE 2 - ESTOQUE INSUFICIENTE",
        itens=[
            {
                "produto_nome": "Feijão",
                "quantidade": 20
            }
        ],
        mensagem_esperada="Estoque insuficiente"
    )

    # TESTE 3: falha depois de processar
    # parcialmente um pedido com dois itens.
    executar_teste(
        nome="TESTE 3 - ROLLBACK ATOMICO",
        itens=[
            {
                "produto_nome": "Arroz",
                "quantidade": 2
            },
            {
                "produto_nome": "Produto Inexistente",
                "quantidade": 1
            }
        ],
        mensagem_esperada="não cadastrado"
    )

    print("\nTODOS OS TESTES FORAM APROVADOS!")


if __name__ == "__main__":
    main()
