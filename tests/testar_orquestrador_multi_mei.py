
import json
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import database.contas_models
import crew.orquestrador as orquestrador

from database.models import Base, Produto, Compra
from database.contas_models import Estabelecimento


@pytest.fixture
def ambiente_orquestrador(monkeypatch):
    # Banco exclusivamente temporario.
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    Base.metadata.create_all(bind=engine)

    SessaoTeste = sessionmaker(
        bind=engine,
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
    )

    with SessaoTeste() as db:
        loja1 = Estabelecimento(
            nome="Loja Orquestrador Um",
            slug="orquestrador-um",
            ativo=True,
        )

        loja2 = Estabelecimento(
            nome="Loja Orquestrador Dois",
            slug="orquestrador-dois",
            ativo=True,
        )

        db.add_all([loja1, loja2])
        db.flush()

        arroz1 = Produto(
            nome="Arroz Teste",
            preco=10.50,
            quantidade=20,
            descricao="Arroz da loja um",
            categoria="Alimentos",
            estabelecimento_id=loja1.id,
        )

        arroz2 = Produto(
            nome="Arroz Teste",
            preco=12.00,
            quantidade=15,
            descricao="Arroz da loja dois",
            categoria="Alimentos",
            estabelecimento_id=loja2.id,
        )

        exclusivo = Produto(
            nome="Feijao Exclusivo",
            preco=8.00,
            quantidade=10,
            descricao="Produto exclusivo da loja um",
            categoria="Alimentos",
            estabelecimento_id=loja1.id,
        )

        db.add_all([arroz1, arroz2, exclusivo])
        db.commit()

        ids = {
            "loja1": loja1.id,
            "loja2": loja2.id,
            "arroz1": arroz1.id,
            "arroz2": arroz2.id,
            "exclusivo": exclusivo.id,
        }

    # O orquestrador nao pode abrir o banco principal.
    monkeypatch.setattr(
        orquestrador,
        "SessionLocal",
        SessaoTeste,
    )

    monkeypatch.setattr(
        orquestrador,
        "init_db",
        lambda: None,
    )

    estado = {
        "cliente": "Cliente Teste",
        "produto": "Arroz Teste",
        "quantidade": 2,
        "rag_ids": [],
        "etapas": [],
        "falha_triagem": False,
        "falha_inventario": False,
    }

    def rag_simulado(
        query,
        n_resultados=3,
        *,
        estabelecimento_id=1,
    ):
        estado["rag_ids"].append(estabelecimento_id)
        return (
            f"Contexto de teste da loja "
            f"{estabelecimento_id}"
        )

    monkeypatch.setattr(
        orquestrador,
        "buscar_contexto",
        rag_simulado,
    )

    # Agentes sem conexao com Groq.
    monkeypatch.setattr(
        orquestrador,
        "criar_agente_triagem",
        lambda: object(),
    )

    monkeypatch.setattr(
        orquestrador,
        "criar_agente_inventario",
        lambda: object(),
    )

    monkeypatch.setattr(
        orquestrador,
        "criar_agente_escrita",
        lambda: object(),
    )

    # Task recebe os mesmos argumentos utilizados
    # pelo orquestrador, mas nao chama CrewAI.
    monkeypatch.setattr(
        orquestrador,
        "Task",
        lambda **kwargs: SimpleNamespace(**kwargs),
    )

    class CrewSimulado:
        def __init__(self, **kwargs):
            self.tarefa = kwargs["tasks"][0]

        def kickoff(self):
            descricao = self.tarefa.description

            if descricao.startswith(
                "Interprete a mensagem"
            ):
                estado["etapas"].append("triagem")

                if estado["falha_triagem"]:
                    return SimpleNamespace(
                        tasks_output=[
                            SimpleNamespace(raw="JSON INVALIDO")
                        ]
                    )

                dados = {
                    "cliente_nome": estado["cliente"],
                    "itens": [
                        {
                            "produto_nome": estado["produto"],
                            "quantidade": estado["quantidade"],
                        }
                    ],
                }

                return SimpleNamespace(
                    tasks_output=[
                        SimpleNamespace(
                            raw=json.dumps(
                                dados,
                                ensure_ascii=False,
                            )
                        )
                    ]
                )

            if descricao.startswith(
                "Analise o pedido estruturado"
            ):
                estado["etapas"].append("inventario")

                if estado["falha_inventario"]:
                    raise RuntimeError(
                        "Falha simulada no inventario."
                    )

                return SimpleNamespace(
                    tasks_output=[]
                )

            if descricao.startswith(
                "Escreva uma mensagem curta"
            ):
                estado["etapas"].append("escrita")

                return SimpleNamespace(
                    tasks_output=[]
                )

            raise AssertionError(
                "Tarefa inesperada no orquestrador."
            )

    monkeypatch.setattr(
        orquestrador,
        "Crew",
        CrewSimulado,
    )

    try:
        yield {
            "SessaoTeste": SessaoTeste,
            "estado": estado,
            **ids,
        }
    finally:
        engine.dispose()


def executar(ambiente, loja, chave, mensagem=None):
    return orquestrador.processar_pedido(
        mensagem_usuario=(
            mensagem
            or "Cliente Teste quer 2 Arroz Teste"
        ),
        chave_idempotencia=chave,
        estabelecimento_id=loja,
    )


def compras(ambiente):
    with ambiente["SessaoTeste"]() as db:
        return db.scalars(
            select(Compra).order_by(Compra.id)
        ).all()


def estoque(ambiente, produto_id):
    with ambiente["SessaoTeste"]() as db:
        return db.get(Produto, produto_id).quantidade


def test_compra_orquestrada_loja_um(
    ambiente_orquestrador,
):
    a = ambiente_orquestrador

    resultado = executar(
        a, a["loja1"], "ia-compra-loja1"
    )

    assert resultado["sucesso"] is True, resultado
    assert len(compras(a)) == 1

    assert compras(a)[0].estabelecimento_id == (
        a["loja1"]
    )

    assert estoque(a, a["arroz1"]) == 18
    assert estoque(a, a["arroz2"]) == 15
    assert a["estado"]["rag_ids"] == [a["loja1"]]


def test_compra_orquestrada_loja_dois(
    ambiente_orquestrador,
):
    a = ambiente_orquestrador

    resultado = executar(
        a, a["loja2"], "ia-compra-loja2"
    )

    assert resultado["sucesso"] is True, resultado

    registros = compras(a)

    assert len(registros) == 1
    assert registros[0].estabelecimento_id == a["loja2"]

    assert estoque(a, a["arroz1"]) == 20
    assert estoque(a, a["arroz2"]) == 13
    assert a["estado"]["rag_ids"] == [a["loja2"]]


def test_mesma_chave_em_duas_lojas(
    ambiente_orquestrador,
):
    a = ambiente_orquestrador

    primeira = executar(
        a, a["loja1"], "mesma-chave-ia"
    )

    segunda = executar(
        a, a["loja2"], "mesma-chave-ia"
    )

    assert primeira["sucesso"] is True, primeira
    assert segunda["sucesso"] is True, segunda

    assert (
        primeira["resultado"]["compra_id"]
        != segunda["resultado"]["compra_id"]
    )

    assert len(compras(a)) == 2
    assert estoque(a, a["arroz1"]) == 18
    assert estoque(a, a["arroz2"]) == 13

    assert a["estado"]["rag_ids"] == [
        a["loja1"],
        a["loja2"],
    ]


def test_repeticao_nao_gera_nova_compra(
    ambiente_orquestrador,
):
    a = ambiente_orquestrador

    primeira = executar(
        a, a["loja1"], "ia-chave-repetida"
    )

    segunda = executar(
        a, a["loja1"], "ia-chave-repetida"
    )

    assert primeira["sucesso"] is True
    assert segunda["sucesso"] is True

    assert segunda["resultado"][
        "requisicao_repetida"
    ] is True

    assert len(compras(a)) == 1
    assert estoque(a, a["arroz1"]) == 18

    # A segunda chamada deve terminar na
    # consulta antecipada de idempotencia.
    assert a["estado"]["rag_ids"] == [a["loja1"]]


def test_produto_de_outra_loja_bloqueado(
    ambiente_orquestrador,
):
    a = ambiente_orquestrador

    a["estado"]["produto"] = "Feijao Exclusivo"

    resultado = executar(
        a,
        a["loja2"],
        "ia-produto-outra-loja",
    )

    assert resultado["sucesso"] is False
    assert len(compras(a)) == 0

    assert estoque(a, a["exclusivo"]) == 10
    assert a["estado"]["rag_ids"] == [a["loja2"]]


def test_rag_recebe_estabelecimento_correto(
    ambiente_orquestrador,
):
    a = ambiente_orquestrador

    executar(a, a["loja2"], "ia-verificar-rag")

    assert a["estado"]["rag_ids"] == [a["loja2"]]

    assert "triagem" in a["estado"]["etapas"]
    assert "inventario" in a["estado"]["etapas"]


def test_falha_triagem_nao_registra_compra(
    ambiente_orquestrador,
):
    a = ambiente_orquestrador

    a["estado"]["falha_triagem"] = True

    resultado = executar(
        a, a["loja1"], "ia-falha-triagem"
    )

    assert resultado["sucesso"] is False
    assert len(compras(a)) == 0
    assert estoque(a, a["arroz1"]) == 20


def test_falha_inventario_nao_registra_compra(
    ambiente_orquestrador,
):
    a = ambiente_orquestrador

    a["estado"]["falha_inventario"] = True

    resultado = executar(
        a, a["loja1"], "ia-falha-inventario"
    )

    assert resultado["sucesso"] is False
    assert len(compras(a)) == 0
    assert estoque(a, a["arroz1"]) == 20


@pytest.mark.parametrize(
    "identificador",
    [None, 0, -1, True, "1"],
)
def test_estabelecimento_invalido(
    ambiente_orquestrador,
    identificador,
):
    a = ambiente_orquestrador

    resultado = executar(
        a,
        identificador,
        "ia-identificador-invalido",
    )

    assert resultado["sucesso"] is False
    assert len(compras(a)) == 0

    assert a["estado"]["rag_ids"] == []
    assert a["estado"]["etapas"] == []
