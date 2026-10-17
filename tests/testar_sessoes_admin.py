
import pytest

from itsdangerous import URLSafeTimedSerializer

from security.sessions import (
    criar_token_sessao,
    validar_token_sessao,
)


@pytest.fixture(autouse=True)
def configurar_chave_teste(monkeypatch):
    monkeypatch.setenv(
        "SESSION_SECRET",
        "chave-exclusiva-para-testes-automatizados-2026",
    )


def test_sessao_valida():
    token = criar_token_sessao("admin")
    assert validar_token_sessao(token) == "admin"


def test_token_adulterado():
    token = criar_token_sessao("admin")
    token_adulterado = token + "ALTERADO"

    assert validar_token_sessao(token_adulterado) is None


def test_token_vazio():
    assert validar_token_sessao("") is None


def test_usuario_invalido():
    with pytest.raises(ValueError):
        criar_token_sessao("")


def test_chave_ausente(monkeypatch):
    monkeypatch.delenv("SESSION_SECRET")

    with pytest.raises(RuntimeError):
        criar_token_sessao("admin")


def test_sessao_expirada(monkeypatch):
    import security.sessions as sessions

    token = criar_token_sessao("admin")

    monkeypatch.setattr(
        sessions,
        "TEMPO_SESSAO_SEGUNDOS",
        -1,
    )

    assert validar_token_sessao(token) is None
