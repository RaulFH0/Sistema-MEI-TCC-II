
import pytest

from security.auth import (
    gerar_hash_senha,
    verificar_credenciais_admin,
)


@pytest.fixture(autouse=True)
def credenciais_teste(monkeypatch):
    monkeypatch.setenv("ADMIN_USERNAME", "admin")
    monkeypatch.setenv(
        "ADMIN_PASSWORD_HASH",
        gerar_hash_senha("SenhaExclusivaDeTeste!2026"),
    )


def test_login_correto():
    assert verificar_credenciais_admin(
        "admin", "SenhaExclusivaDeTeste!2026"
    )


def test_senha_incorreta():
    assert not verificar_credenciais_admin(
        "admin", "SenhaIncorreta!2026"
    )


def test_usuario_incorreto():
    assert not verificar_credenciais_admin(
        "outro", "SenhaExclusivaDeTeste!2026"
    )


def test_usuario_e_senha_vazios():
    assert not verificar_credenciais_admin("", "")


def test_configuracao_ausente(monkeypatch):
    monkeypatch.delenv("ADMIN_PASSWORD_HASH")

    with pytest.raises(RuntimeError):
        verificar_credenciais_admin(
            "admin", "SenhaExclusivaDeTeste!2026"
        )
