
import pytest

from security.auth import gerar_hash_senha, verificar_senha


def test_senha_correta():
    senha = "SenhaForteDeTeste!2026"
    hash_gerado = gerar_hash_senha(senha)

    assert hash_gerado != senha
    assert verificar_senha(senha, hash_gerado) is True


def test_senha_incorreta():
    hash_gerado = gerar_hash_senha("SenhaCorreta!2026")

    assert verificar_senha("SenhaErrada!2026", hash_gerado) is False


def test_hashs_diferentes_para_mesma_senha():
    senha = "OutraSenhaForte!2026"

    primeiro = gerar_hash_senha(senha)
    segundo = gerar_hash_senha(senha)

    assert primeiro != segundo
    assert verificar_senha(senha, primeiro)
    assert verificar_senha(senha, segundo)


@pytest.mark.parametrize("senha", ["", None, 123])
def test_senha_invalida(senha):
    with pytest.raises(ValueError):
        gerar_hash_senha(senha)


def test_hash_invalido():
    assert verificar_senha("qualquer", "hash-invalido") is False
