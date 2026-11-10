from datetime import datetime, time, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from main import app
from database.models import (
    Base, Compra, ItemCompra, Produto, get_db,
)
from database.contas_models import Estabelecimento
from security.mei_routes import exigir_mei


@pytest.fixture
def ambiente(tmp_path):
    banco = tmp_path / "dashboard_teste.db"
    engine = create_engine(
        "sqlite:///" + banco.as_posix(),
        connect_args={"check_same_thread": False},
    )

    @event.listens_for(engine, "connect")
    def configurar_sqlite(conexao, registro):
        cursor = conexao.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(bind=engine)

    Sessao = sessionmaker(
        bind=engine,
        expire_on_commit=False,
    )

    hoje = datetime.now().date()

    with Sessao.begin() as db:
        lojas = [
            Estabelecimento(
                nome="Loja Dashboard A",
                slug="dashboard-teste-a",
                ativo=True,
            ),
            Estabelecimento(
                nome="Loja Dashboard B",
                slug="dashboard-teste-b",
                ativo=True,
            ),
        ]
        db.add_all(lojas)
        db.flush()

        produtos = [
            Produto(
                nome="Produto A",
                preco=25.90,
                quantidade=20,
                categoria="Testes",
                estabelecimento_id=lojas[0].id,
            ),
            Produto(
                nome="Produto B",
                preco=99.99,
                quantidade=20,
                categoria="Testes",
                estabelecimento_id=lojas[1].id,
            ),
        ]
        db.add_all(produtos)
        db.flush()

        def inserir(loja, produto, dias, centavos,
                    unidades, status, chave):
            compra = Compra(
                cliente_nome="Cliente de teste",
                chave_idempotencia=chave,
                valor_total=centavos,
                status=status,
                estabelecimento_id=loja.id,
                criado_em=datetime.combine(
                    hoje - timedelta(days=dias),
                    time(12, 0),
                ),
            )
            db.add(compra)
            db.flush()

            db.add(ItemCompra(
                compra_id=compra.id,
                produto_id=produto.id,
                produto_nome=produto.nome,
                quantidade=unidades,
                preco_unitario=centavos // unidades,
                subtotal=centavos,
            ))

        inserir(lojas[0], produtos[0], 0, 5180, 2,
                "confirmado", "dash-a-01")
        inserir(lojas[0], produtos[0], 6, 1000, 1,
                "confirmado", "dash-a-02")
        inserir(lojas[0], produtos[0], 29, 2500, 1,
                "confirmado", "dash-a-03")
        inserir(lojas[0], produtos[0], 40, 700, 1,
                "confirmado", "dash-a-04")
        inserir(lojas[0], produtos[0], 0, 4000, 1,
                "cancelado", "dash-a-05")
        inserir(lojas[1], produtos[1], 0, 9999, 1,
                "confirmado", "dash-b-01")

        ids = (lojas[0].id, lojas[1].id)

    anteriores = dict(app.dependency_overrides)

    def banco_teste():
        with Sessao() as db:
            yield db

    app.dependency_overrides[get_db] = banco_teste

    cliente = TestClient(app)

    try:
        yield cliente, ids, hoje
    finally:
        cliente.close()
        app.dependency_overrides.clear()
        app.dependency_overrides.update(anteriores)
        engine.dispose()


def autenticar(loja_id):
    app.dependency_overrides[exigir_mei] = (
        lambda: {"estabelecimento_id": loja_id}
    )


def test_sem_sessao_retorna_401(ambiente):
    cliente, _, _ = ambiente
    assert cliente.get("/mei/dashboard").status_code == 401


def test_hoje_exclui_canceladas_e_outras_lojas(ambiente):
    cliente, lojas, _ = ambiente
    autenticar(lojas[0])

    resposta = cliente.get("/mei/dashboard?periodo=hoje")
    assert resposta.status_code == 200, resposta.text

    dados = resposta.json()
    assert dados["pedidos_confirmados"] == 1
    assert dados["valor_total_centavos"] == 5180
    assert dados["ticket_medio_centavos"] == 5180
    assert dados["unidades_vendidas"] == 2
    assert len(dados["evolucao_diaria"]) == 1


def test_ultimos_sete_dias(ambiente):
    cliente, lojas, _ = ambiente
    autenticar(lojas[0])

    resposta = cliente.get("/mei/dashboard?periodo=7d")
    assert resposta.status_code == 200, resposta.text

    dados = resposta.json()
    assert dados["pedidos_confirmados"] == 2
    assert dados["valor_total_centavos"] == 6180
    assert dados["ticket_medio_centavos"] == 3090
    assert dados["unidades_vendidas"] == 3
    assert len(dados["evolucao_diaria"]) == 2


def test_trinta_dias_sem_limitar_a_lista(ambiente):
    cliente, lojas, _ = ambiente
    autenticar(lojas[0])

    resposta = cliente.get("/mei/dashboard?periodo=30d")
    assert resposta.status_code == 200, resposta.text

    dados = resposta.json()
    assert dados["pedidos_confirmados"] == 3
    assert dados["valor_total_centavos"] == 8680
    assert dados["ticket_medio_centavos"] == 2893
    assert dados["unidades_vendidas"] == 4
    assert len(dados["evolucao_diaria"]) == 3


def test_periodo_personalizado(ambiente):
    cliente, lojas, hoje = ambiente
    autenticar(lojas[0])

    dia = (hoje - timedelta(days=6)).isoformat()
    resposta = cliente.get(
        "/mei/dashboard",
        params={
            "periodo": "personalizado",
            "inicio": dia,
            "fim": dia,
        },
    )

    assert resposta.status_code == 200, resposta.text
    assert resposta.json()["valor_total_centavos"] == 1000
    assert resposta.json()["pedidos_confirmados"] == 1


def test_segunda_loja_nao_enxerga_primeira(ambiente):
    cliente, lojas, _ = ambiente
    autenticar(lojas[1])

    resposta = cliente.get("/mei/dashboard?periodo=30d")
    assert resposta.status_code == 200, resposta.text

    dados = resposta.json()
    assert dados["pedidos_confirmados"] == 1
    assert dados["valor_total_centavos"] == 9999
    assert dados["unidades_vendidas"] == 1


def test_periodo_sem_vendas(ambiente):
    cliente, lojas, _ = ambiente
    autenticar(lojas[0])

    resposta = cliente.get(
        "/mei/dashboard",
        params={
            "periodo": "personalizado",
            "inicio": "2020-01-01",
            "fim": "2020-01-31",
        },
    )

    assert resposta.status_code == 200, resposta.text
    dados = resposta.json()
    assert dados["pedidos_confirmados"] == 0
    assert dados["valor_total_centavos"] == 0
    assert dados["ticket_medio_centavos"] == 0
    assert dados["unidades_vendidas"] == 0
    assert dados["evolucao_diaria"] == []


@pytest.mark.parametrize("parametros", [
    {"periodo": "personalizado"},
    {
        "periodo": "personalizado",
        "inicio": "2026-11-10",
        "fim": "2026-11-09",
    },
    {
        "periodo": "personalizado",
        "inicio": "2020-01-01",
        "fim": "2022-01-01",
    },
    {"periodo": "30d", "inicio": "2026-11-01"},
    {"periodo": "invalido"},
])
def test_periodos_invalidos(ambiente, parametros):
    cliente, lojas, _ = ambiente
    autenticar(lojas[0])

    resposta = cliente.get(
        "/mei/dashboard",
        params=parametros,
    )

    assert resposta.status_code == 422
