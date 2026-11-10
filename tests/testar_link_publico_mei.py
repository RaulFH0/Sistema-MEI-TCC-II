import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from main import app
from database.models import Base, get_db
from database.contas_models import Estabelecimento
import security.mei_routes as mei_routes


@pytest.fixture
def ambiente(tmp_path):
    caminho = tmp_path / "links_mei_teste.db"

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
            slug="loja-ana",
            ativo=True,
        )
        loja_b = Estabelecimento(
            nome="Mercadinho Jose",
            slug="mercadinho-jose",
            ativo=True,
        )
        loja_inativa = Estabelecimento(
            nome="Loja Inativa",
            slug="loja-inativa",
            ativo=False,
        )

        db.add_all([loja_a, loja_b, loja_inativa])
        db.flush()

        ids = {
            "a": loja_a.id,
            "b": loja_b.id,
            "inativa": loja_inativa.id,
        }

    def banco_teste():
        with Sessao() as db:
            yield db

    anteriores = dict(app.dependency_overrides)
    app.dependency_overrides[get_db] = banco_teste

    try:
        yield Sessao, ids
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(anteriores)
        engine.dispose()


def test_link_da_loja_a(ambiente):
    Sessao, ids = ambiente

    with Sessao() as db:
        dados = mei_routes._dados_loja_publica(
            db, ids["a"]
        )

    assert dados["slug"] == "loja-ana"
    assert dados["nome_estabelecimento"] == "Loja Ana"


def test_link_da_loja_b(ambiente):
    Sessao, ids = ambiente

    with Sessao() as db:
        dados = mei_routes._dados_loja_publica(
            db, ids["b"]
        )

    assert dados["slug"] == "mercadinho-jose"
    assert dados["nome_estabelecimento"] == "Mercadinho Jose"


def test_links_sao_diferentes(ambiente):
    Sessao, ids = ambiente

    with Sessao() as db:
        a = mei_routes._dados_loja_publica(
            db, ids["a"]
        )
        b = mei_routes._dados_loja_publica(
            db, ids["b"]
        )

    assert a["slug"] != b["slug"]
    assert a["nome_estabelecimento"] != b["nome_estabelecimento"]


def test_loja_inativa_sem_link(ambiente):
    Sessao, ids = ambiente

    with Sessao() as db:
        dados = mei_routes._dados_loja_publica(
            db, ids["inativa"]
        )

    assert dados["slug"] is None
    assert dados["nome_estabelecimento"] is None


def test_endpoint_me_retorna_loja_da_sessao(
    ambiente, monkeypatch
):
    _, ids = ambiente

    # Simula exclusivamente a identidade que o
    # mecanismo de autenticacao ja teria validado.
    # Nao simula uma escolha de loja pelo cliente.
    identidade = {
        "usuario_mei_id": 101,
        "estabelecimento_id": ids["a"],
        "email": "ana@example.test",
    }

    def identidade_validada(request, db):
        return identidade

    monkeypatch.setattr(
        mei_routes,
        "exigir_mei",
        identidade_validada,
    )
    monkeypatch.setattr(
        mei_routes,
        "_token_csrf",
        lambda token: "csrf-teste",
    )

    with TestClient(app) as cliente:
        cliente.cookies.set(
            mei_routes.COOKIE_MEI,
            "sessao-teste",
        )
        resposta = cliente.get("/auth/mei/me")

    assert resposta.status_code == 200, resposta.text

    dados = resposta.json()

    assert dados["estabelecimento_id"] == ids["a"]
    assert dados["slug"] == "loja-ana"
    assert dados["nome_estabelecimento"] == "Loja Ana"
    assert dados["slug"] != "mercadinho-jose"
