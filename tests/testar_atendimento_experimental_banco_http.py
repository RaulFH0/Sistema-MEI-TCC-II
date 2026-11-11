import re

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import sessionmaker

from main import app
from database.models import Base, Produto, get_db
from database.contas_models import Estabelecimento

import security.atendimento_multiintencao as multi
from security.limite_atendimento_ia import limitador_atendimento_ia


CHAVE_TESTE = "teste-local-" + "x" * 48

TABELAS_COMERCIAIS = (
    "produtos",
    "pedidos",
    "compras",
)


@pytest.fixture
def ambiente(tmp_path, monkeypatch):
    caminho = tmp_path / "seguranca_experimental.db"

    engine = create_engine(
        "sqlite:///" + caminho.as_posix(),
        connect_args={"check_same_thread": False},
    )

    Base.metadata.create_all(bind=engine)

    Sessao = sessionmaker(
        bind=engine,
        expire_on_commit=False,
    )

    with Sessao.begin() as db:
        loja_a = Estabelecimento(
            nome="Loja Ana",
            slug="loja-ana-ia",
            ativo=True,
        )
        loja_b = Estabelecimento(
            nome="Loja Beto",
            slug="loja-beto-ia",
            ativo=True,
        )

        db.add_all([loja_a, loja_b])
        db.flush()

        db.add_all([
            Produto(
                nome="Caderno Exclusivo Ana",
                descricao="Produto da primeira loja",
                preco=25.90,
                quantidade=13,
                categoria="Papelaria",
                estabelecimento_id=loja_a.id,
            ),
            Produto(
                nome="Caneca Exclusiva Beto",
                descricao="Produto da segunda loja",
                preco=39.90,
                quantidade=8,
                categoria="Casa",
                estabelecimento_id=loja_b.id,
            ),
        ])

    def banco_teste():
        with Sessao() as db:
            yield db

    anteriores = dict(app.dependency_overrides)
    app.dependency_overrides[get_db] = banco_teste

    monkeypatch.setenv(
        "MEI_ATENDIMENTO_IA_EXPERIMENTAL", "1"
    )
    monkeypatch.setenv(
        "MEI_ATENDIMENTO_IA_EXPERIMENTAL_KEY",
        CHAVE_TESTE,
    )

    limitador_atendimento_ia.limpar_para_testes()

    def classificar(mensagem):
        texto = mensagem.lower()
        if "comprar" in texto:
            intencao = "compra"
        elif "ajuda" in texto:
            intencao = "esclarecimento"
        else:
            intencao = "consulta_catalogo"

        return {
            "intencao": intencao,
            "confianca": 0.99,
            "origem": "teste_sem_groq",
            "tempo_ms": 0.0,
        }

    monkeypatch.setattr(
        multi, "classificar_intencao", classificar
    )

    escritas = []

    def observar_sql(conn, cursor, sql, parametros, contexto, muitos):
        if re.match(
            r"^\s*(INSERT|UPDATE|DELETE|REPLACE|"
            r"CREATE|ALTER|DROP)\b",
            sql,
            flags=re.IGNORECASE,
        ):
            escritas.append(sql)

    event.listen(
        engine,
        "before_cursor_execute",
        observar_sql,
    )

    try:
        with TestClient(
            app, raise_server_exceptions=False
        ) as cliente:
            yield {
                "cliente": cliente,
                "engine": engine,
                "escritas": escritas,
            }
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(anteriores)
        limitador_atendimento_ia.limpar_para_testes()
        event.remove(
            engine,
            "before_cursor_execute",
            observar_sql,
        )
        engine.dispose()


def retrato_comercial(engine):
    retrato = {}

    with engine.connect() as conexao:
        for nome in TABELAS_COMERCIAIS:
            tabela = Base.metadata.tables[nome]
            linhas = conexao.execute(
                select(tabela)
            ).mappings().all()

            retrato[nome] = sorted(
                (
                    repr(dict(linha))
                    for linha in linhas
                )
            )

    return retrato


def perguntar(ambiente, slug, mensagem):
    return ambiente["cliente"].post(
        f"/lojas/{slug}/atendimento-experimental",
        headers={
            "X-MEI-Experimental-Key": CHAVE_TESTE
        },
        json={"mensagem": mensagem},
    )


def garantir_sem_escrita(ambiente, antes):
    assert ambiente["escritas"] == []
    assert retrato_comercial(
        ambiente["engine"]
    ) == antes


def test_consulta_loja_a_nao_altera_comercio(ambiente):
    antes = retrato_comercial(ambiente["engine"])

    resposta = perguntar(
        ambiente,
        "loja-ana-ia",
        "Quais produtos voces tem?",
    )

    assert resposta.status_code == 200, resposta.text
    assert resposta.json()["dados"][
        "compra_registrada"
    ] is False

    garantir_sem_escrita(ambiente, antes)


def test_consulta_loja_b_nao_altera_comercio(ambiente):
    antes = retrato_comercial(ambiente["engine"])

    resposta = perguntar(
        ambiente,
        "loja-beto-ia",
        "Quais produtos voces tem?",
    )

    assert resposta.status_code == 200, resposta.text
    assert resposta.json()["dados"][
        "compra_registrada"
    ] is False

    garantir_sem_escrita(ambiente, antes)


def test_intencao_compra_nao_registra_pedido(ambiente):
    antes = retrato_comercial(ambiente["engine"])

    resposta = perguntar(
        ambiente,
        "loja-ana-ia",
        "Quero comprar dois cadernos.",
    )

    assert resposta.status_code == 200, resposta.text
    assert resposta.json()["acao_executada"] in (
        "compra_pendente_confirmacao",
        "solicitar_esclarecimento",
    )
    assert resposta.json()["dados"][
        "compra_registrada"
    ] is False

    garantir_sem_escrita(ambiente, antes)


def test_mensagem_ambigua_nao_registra_pedido(ambiente):
    antes = retrato_comercial(ambiente["engine"])

    resposta = perguntar(
        ambiente,
        "loja-ana-ia",
        "Preciso de ajuda para escolher.",
    )

    assert resposta.status_code == 200, resposta.text
    assert resposta.json()["acao_executada"] == (
        "solicitar_esclarecimento"
    )

    garantir_sem_escrita(ambiente, antes)


def test_consulta_nao_exibe_produto_de_outra_loja(ambiente):
    antes = retrato_comercial(ambiente["engine"])

    resposta = perguntar(
        ambiente,
        "loja-ana-ia",
        "Quais produtos voces tem?",
    )

    assert resposta.status_code == 200, resposta.text

    texto = resposta.json()["resposta"].lower()

    assert "caneca exclusiva beto" not in texto

    garantir_sem_escrita(ambiente, antes)


def test_loja_inexistente_nao_consulta_ia(ambiente):
    antes = retrato_comercial(ambiente["engine"])

    resposta = perguntar(
        ambiente,
        "loja-inexistente",
        "Quais produtos voces tem?",
    )

    assert resposta.status_code == 404
    garantir_sem_escrita(ambiente, antes)
