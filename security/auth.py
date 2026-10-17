
from pwdlib import PasswordHash

# Algoritmo Argon2 para armazenamento seguro de senhas.
password_hash = PasswordHash.recommended()


def gerar_hash_senha(senha: str) -> str:
    if not isinstance(senha, str) or not senha:
        raise ValueError("Senha invalida.")

    return password_hash.hash(senha)


def verificar_senha(senha: str, hash_armazenado: str) -> bool:
    if (
        not isinstance(senha, str)
        or not isinstance(hash_armazenado, str)
        or not hash_armazenado
    ):
        return False

    try:
        return password_hash.verify(senha, hash_armazenado)
    except Exception:
        return False


import os
from hmac import compare_digest

from dotenv import load_dotenv

load_dotenv()


def verificar_credenciais_admin(
    usuario: str,
    senha: str,
) -> bool:
    usuario_configurado = os.getenv("ADMIN_USERNAME")
    hash_configurado = os.getenv("ADMIN_PASSWORD_HASH")

    if not usuario_configurado or not hash_configurado:
        raise RuntimeError(
            "Credenciais administrativas nao configuradas."
        )

    if not isinstance(usuario, str) or not isinstance(senha, str):
        return False

    if not compare_digest(usuario, usuario_configurado):
        return False

    return verificar_senha(senha, hash_configurado)
