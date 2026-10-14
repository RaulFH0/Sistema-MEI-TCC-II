
import tempfile
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from database.models import Base, Produto, Compra, ItemCompra
from database.crud import registrar_compra_segura


def executar_teste():
    # Cria um banco temporario em arquivo.
    # Os bancos do projeto nao serao modificados.
    with tempfile.TemporaryDirectory() as pasta:
        caminho = Path(pasta) / "concorrencia.db"

        engine = create_engine(
            f"sqlite:///{caminho.as_posix()}",
            connect_args={
                "check_same_thread": False,
                "timeout": 10
            }
        )

        @event.listens_for(engine, "connect")
        def configurar_sqlite(conexao, registro):
            cursor = conexao.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

        Base.metadata.create_all(engine)

        Sessao = sessionmaker(
            bind=engine,
            expire_on_commit=False
        )

        # Preparar estoque inicial
        with Sessao() as db:
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

        barreira = Barrier(2)

        itens = [
            {"produto_nome": "Arroz", "quantidade": 2},
            {"produto_nome": "Feijão", "quantidade": 1}
        ]

        # Cada thread utiliza sua propria sessao.
        def processar(numero):
            with Sessao() as db:
                try:
                    barreira.wait(timeout=10)

                    resultado = registrar_compra_segura(
                        db=db,
                        cliente_nome="Joao Teste",
                        itens=itens,
                        chave_idempotencia="compra-concorrente-001"
                    )

                    return {
                        "thread": numero,
                        "sucesso": True,
                        "resultado": resultado
                    }

                except Exception as erro:
                    db.rollback()
                    return {
                        "thread": numero,
                        "sucesso": False,
                        "erro": str(erro),
                        "tipo_erro": type(erro).__name__
                    }

        print("=== TESTE DE CONCORRENCIA ===")

        try:
            # Dispara duas requisicoes em paralelo
            with ThreadPoolExecutor(max_workers=2) as executor:
                resultados = list(
                    executor.map(processar, [1, 2])
                )

            for resultado in resultados:
                print(
                    f"\nRequisicao {resultado['thread']}:"
                )
                print(resultado)

            # Verificar estado final do banco
            with Sessao() as db:
                compras = db.query(Compra).all()
                registros = db.query(ItemCompra).all()

                arroz = db.query(Produto).filter_by(
                    nome="Arroz"
                ).one()

                feijao = db.query(Produto).filter_by(
                    nome="Feijão"
                ).one()

                print("\n=== ESTADO FINAL ===")
                print("Compras:", len(compras))
                print("Itens:", len(registros))
                print("Estoque Arroz:", arroz.quantidade)
                print("Estoque Feijão:", feijao.quantidade)

                assert len(compras) == 1, (
                    "Falha: compra duplicada."
                )

                assert len(registros) == 2, (
                    "Falha: quantidade incorreta de itens."
                )

                assert arroz.quantidade == 48, (
                    "Falha: estoque de Arroz incorreto."
                )

                assert feijao.quantidade == 39, (
                    "Falha: estoque de Feijão incorreto."
                )

                assert compras[0].valor_total == 5850, (
                    "Falha: valor total incorreto."
                )

                print(
                    "\nINTEGRIDADE DOS DADOS: APROVADA!"
                )

                sucessos = [
                    r for r in resultados
                    if r["sucesso"]
                ]

                if len(sucessos) == 2:
                    ids = {
                        r["resultado"]["compra_id"]
                        for r in sucessos
                    }

                    assert len(ids) == 1

                    print(
                        "IDEMPOTENCIA CONCORRENTE: APROVADA!"
                    )
                else:
                    print(
                        "ATENCAO: Uma ou mais requisicoes "
                        "falharam. Analisar os erros antes "
                        "de aprovar a concorrencia."
                    )

        finally:
            engine.dispose()


if __name__ == "__main__":
    executar_teste()
