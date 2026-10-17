
import os
import secrets
from dotenv import load_dotenv

load_dotenv()


from itsdangerous import (
    URLSafeTimedSerializer,
    BadSignature,
    SignatureExpired,
)

TEMPO_SESSAO_SEGUNDOS = 60 * 60 * 8

NOME_COOKIE_SESSAO = "sistema_mei_admin"


def _serializer():
    segredo = os.getenv("SESSION_SECRET")

    if not segredo or len(segredo) < 32:
        raise RuntimeError(
            "SESSION_SECRET nao configurado corretamente."
        )

    return URLSafeTimedSerializer(
        secret_key=segredo,
        salt="sistema-mei-admin-v1",
    )


def criar_token_sessao(usuario: str) -> str:
    if not isinstance(usuario, str) or not usuario.strip():
        raise ValueError("Usuario invalido.")

    return _serializer().dumps({
        "usuario": usuario.strip(),
        "nonce": secrets.token_urlsafe(16),
    })


def validar_token_sessao(token: str) -> str | None:
    if not isinstance(token, str) or not token:
        return None

    try:
        dados = _serializer().loads(
            token,
            max_age=TEMPO_SESSAO_SEGUNDOS,
        )
    except (BadSignature, SignatureExpired):
        return None

    if not isinstance(dados, dict):
        return None

    usuario = dados.get("usuario")

    if not isinstance(usuario, str) or not usuario.strip():
        return None

    return usuario
