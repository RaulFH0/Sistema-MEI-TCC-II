
import hashlib

from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from database.models import Base, Produto, Compra
from database.contas_models import Estabelecimento
from database.crud import registrar_compra_segura
import crew.orquestrador as orquestrador


def test_reenvio_sem_groq(monkeypatch):
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool
    )
    Base.metadata.create_all(engine)

    SessaoTeste = sessionmaker(bind=engine)

    mensagem = "Sou Joao e quero comprar 2 Arroz."
    chave = "fluxo-v22-teste-001"

    try:
        with SessaoTeste() as db:
            db.add(
                Estabelecimento(
                    id=1,
                    nome="Loja Inicial",
                    slug="loja-inicial",
                    ativo=True,
                )
            )
            db.flush()
            db.add(
                Produto(
                    nome="Arroz",
                    preco=25.00,
                    quantidade=50,
                    categoria="Alimentos",
                    estabelecimento_id=1,
                )
            )
            db.commit()

            original = registrar_compra_segura(
                db=db,
                cliente_nome="Joao",
                itens=[
                    {"produto_nome": "Arroz", "quantidade": 2}
                ],
                chave_idempotencia=chave,
                mensagem_original=mensagem
            )

            assert original["requisicao_repetida"] is False

        # O orquestrador deve usar somente o banco de teste.
        monkeypatch.setattr(
            orquestrador,
            "SessionLocal",
            SessaoTeste
        )

        # Evita a inicializacao do banco real.
        monkeypatch.setattr(
            orquestrador,
            "init_db",
            lambda: None
        )

        # Qualquer chamada ao RAG ou aos agentes
        # deve provocar falha neste teste.
        def proibido(*args, **kwargs):
            raise AssertionError(
                "O fluxo antecipado chamou a IA ou RAG."
            )

        monkeypatch.setattr(
            orquestrador,
            "buscar_contexto",
            proibido
        )

        monkeypatch.setattr(
            orquestrador,
            "criar_agente_triagem",
            proibido
        )

        monkeypatch.setattr(
            orquestrador,
            "criar_agente_inventario",
            proibido
        )

        monkeypatch.setattr(
            orquestrador,
            "criar_agente_escrita",
            proibido
        )

        # Reenvio identico
        resposta = orquestrador.processar_pedido(
            mensagem_usuario=mensagem,
            chave_idempotencia=chave
        )

        assert resposta["sucesso"] is True
        assert resposta["resultado"]["compra_id"] == (
            original["compra_id"]
        )
        assert resposta["resultado"]["requisicao_repetida"]

        with SessaoTeste() as db:
            assert db.query(Compra).count() == 1
            assert db.query(Produto).first().quantidade == 48

        print(
            "\nFLUXO ANTECIPADO SEM GROQ: APROVADO!"
        )

    finally:
        engine.dispose()
