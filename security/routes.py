
import hashlib
import hmac
import os
import secrets

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Request,
    Response,
    status,
)
from pydantic import BaseModel, Field, SecretStr
from sqlalchemy.orm import Session

from database.models import get_db
from security.auth import verificar_credenciais_admin
from security.session_store import (
    criar_sessao,
    consultar_sessao,
    revogar_sessao,
)


router = APIRouter(prefix="/auth", tags=["Autenticacao"])

COOKIE_SESSAO = "sistema_mei_admin"
DURACAO_SESSAO = 8 * 60 * 60


class LoginEntrada(BaseModel):
    usuario: str = Field(min_length=1, max_length=100)
    senha: SecretStr


def _segredo_csrf() -> bytes:
    segredo = os.getenv("SESSION_SECRET")

    if not segredo or len(segredo) < 32:
        raise RuntimeError(
            "SESSION_SECRET nao configurado corretamente."
        )

    return segredo.encode("utf-8")


def _token_csrf(token_sessao: str) -> str:
    """
    Gera uma prova CSRF vinculada a esta sessao.

    O token de sessao permanece apenas no cookie HttpOnly.
    """
    return hmac.new(
        _segredo_csrf(),
        token_sessao.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def _cookie_seguro() -> bool:
    """
    Em ambiente local HTTP, usar COOKIE_SECURE=false.
    Em producao HTTPS, configurar COOKIE_SECURE=true.
    """
    valor = os.getenv("COOKIE_SECURE", "false").lower()
    return valor == "true"


def _obter_token(request: Request) -> str | None:
    return request.cookies.get(COOKIE_SESSAO)


def _usuario_autenticado(
    request: Request,
    db: Session,
) -> str:
    token = _obter_token(request)

    usuario = consultar_sessao(db, token)

    if usuario is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Autenticacao necessaria.",
        )

    return usuario


def exigir_admin(
    request: Request,
    db: Session = Depends(get_db),
) -> str:
    """
    Dependencia reutilizavel para proteger rotas administrativas.
    """
    return _usuario_autenticado(request, db)


def exigir_admin_escrita(
    request: Request,
    db: Session = Depends(get_db),
) -> str:
    """
    Exige autenticacao e CSRF para operacoes administrativas
    que modificam dados.
    """
    usuario = _usuario_autenticado(request, db)

    token_sessao = _obter_token(request)
    csrf_recebido = request.headers.get("X-CSRF-Token", "")
    csrf_esperado = _token_csrf(token_sessao)

    if not hmac.compare_digest(
        csrf_recebido,
        csrf_esperado,
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Token CSRF invalido ou ausente.",
        )

    return usuario


@router.post("/login")
def login(
    entrada: LoginEntrada,
    response: Response,
    db: Session = Depends(get_db),
):
    usuario = entrada.usuario.strip()

    if not verificar_credenciais_admin(
        usuario,
        entrada.senha.get_secret_value(),
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario ou senha incorretos.",
        )

    token = criar_sessao(db, usuario)

    response.set_cookie(
        key=COOKIE_SESSAO,
        value=token,
        httponly=True,
        secure=_cookie_seguro(),
        samesite="lax",
        max_age=DURACAO_SESSAO,
        path="/",
    )

    return {
        "autenticado": True,
        "usuario": usuario,
        "csrf_token": _token_csrf(token),
    }


@router.get("/me")
def consultar_login(
    request: Request,
    db: Session = Depends(get_db),
):
    usuario = _usuario_autenticado(request, db)
    token = _obter_token(request)

    return {
        "autenticado": True,
        "usuario": usuario,
        "csrf_token": _token_csrf(token),
    }


@router.post("/logout")
def logout(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    # A verificacao de CSRF ocorre antes da revogacao.
    exigir_admin_escrita(request, db)

    token = _obter_token(request)
    revogar_sessao(db, token)

    response.delete_cookie(
        key=COOKIE_SESSAO,
        path="/",
        secure=_cookie_seguro(),
        httponly=True,
        samesite="lax",
    )

    return {
        "autenticado": False,
        "mensagem": "Sessao encerrada.",
    }
