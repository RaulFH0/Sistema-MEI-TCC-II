import pytest

from security.limite_cadastro import LimitadorCadastro


def test_cinco_tentativas_permitidas():
    limite = LimitadorCadastro(
        limite=5,
        janela_segundos=900,
        relogio=lambda: 100.0,
    )

    for _ in range(5):
        assert limite.consumir("ip-teste") is None


def test_sexta_tentativa_bloqueada():
    limite = LimitadorCadastro(
        limite=5,
        janela_segundos=900,
        relogio=lambda: 100.0,
    )

    for _ in range(5):
        limite.consumir("ip-teste")

    assert limite.consumir("ip-teste") == 900


def test_liberacao_apos_quinze_minutos():
    instante = [100.0]

    limite = LimitadorCadastro(
        limite=5,
        janela_segundos=900,
        relogio=lambda: instante[0],
    )

    for _ in range(5):
        limite.consumir("ip-teste")

    assert limite.consumir("ip-teste") == 900

    instante[0] += 900

    assert limite.consumir("ip-teste") is None


def test_chaves_diferentes_sao_independentes():
    limite = LimitadorCadastro(
        limite=1,
        janela_segundos=900,
        relogio=lambda: 100.0,
    )

    assert limite.consumir("ip-a") is None
    assert limite.consumir("ip-a") == 900
    assert limite.consumir("ip-b") is None


def test_limite_de_memoria():
    instante = [100.0]

    limite = LimitadorCadastro(
        limite=1,
        janela_segundos=900,
        capacidade=2,
        relogio=lambda: instante[0],
    )

    assert limite.consumir("ip-a") is None
    assert limite.consumir("ip-b") is None

    # A capacidade esgotada deve bloquear novas chaves.
    assert limite.consumir("ip-c") == 900

    # Depois da expiracao, registros antigos sao liberados.
    instante[0] += 900

    assert limite.consumir("ip-c") is None


def test_chave_vazia_rejeitada():
    limite = LimitadorCadastro()

    with pytest.raises(ValueError):
        limite.consumir("")
