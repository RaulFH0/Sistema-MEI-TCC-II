
from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Request,
    Response,
    status,
)
from pydantic import BaseModel, Field, SecretStr
from sqlalchemy import func
from sqlalchemy.orm import Session

from database.models import get_db
from database.contas_models import UsuarioMEI, Estabelecimento
from security.auth import verificar_senha
from security.session_store import (
    criar_sessao_mei,
    consultar_sessao_mei,
    revogar_sessao,
)
from security.routes import (
    _token_csrf,
    _cookie_seguro,
)


# ============================================================
# CONFIGURACAO DA AUTENTICACAO MEI
# ============================================================

router = APIRouter(
    prefix="/auth/mei",
    tags=["Autenticacao MEI"],
)

COOKIE_MEI = "sistema_mei_usuario"
DURACAO_SESSAO = 8 * 60 * 60

def _dados_loja_publica(
    db: Session,
    estabelecimento_id: int,
) -> dict:
    """
    Consulta somente a loja vinculada a sessao MEI.
    O cliente nao informa o ID da loja.
    """
    loja = (
        db.query(Estabelecimento)
        .filter(
            Estabelecimento.id == estabelecimento_id,
            Estabelecimento.ativo.is_(True),
        )
        .first()
    )

    if loja is None:
        return {
            "slug": None,
            "nome_estabelecimento": None,
        }

    return {
        "slug": loja.slug,
        "nome_estabelecimento": loja.nome,
    }



class LoginMEIEntrada(BaseModel):
    email: str = Field(
        min_length=3,
        max_length=254,
    )
    senha: SecretStr


# ============================================================
# CONSULTA DA SESSAO MEI
# ============================================================

def _obter_token_mei(request: Request) -> str | None:
    return request.cookies.get(COOKIE_MEI)


def exigir_mei(
    request: Request,
    db: Session = Depends(get_db),
) -> dict:
    token = _obter_token_mei(request)

    identidade = consultar_sessao_mei(
        db,
        token,
    )

    if identidade is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Autenticacao MEI necessaria.",
        )

    return identidade


def exigir_mei_escrita(
    request: Request,
    db: Session = Depends(get_db),
) -> dict:
    identidade = exigir_mei(request, db)

    token = _obter_token_mei(request)
    csrf_recebido = request.headers.get(
        "X-CSRF-Token",
        "",
    )
    csrf_esperado = _token_csrf(token)

    from hmac import compare_digest

    if not compare_digest(
        csrf_recebido,
        csrf_esperado,
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Token CSRF invalido ou ausente.",
        )

    return identidade


# ============================================================
# LOGIN DO MICROEMPREENDEDOR
# ============================================================

@router.post("/login")
def login_mei(
    entrada: LoginMEIEntrada,
    response: Response,
    db: Session = Depends(get_db),
):
    email = entrada.email.strip().casefold()
    senha = entrada.senha.get_secret_value()

    usuario = (
        db.query(UsuarioMEI)
        .filter(
            func.lower(UsuarioMEI.email) == email
        )
        .first()
    )

    mensagem_invalida = (
        "Credenciais invalidas ou conta indisponivel."
    )

    if usuario is None:
        raise HTTPException(
            status_code=401,
            detail=mensagem_invalida,
        )

    if not usuario.ativo:
        raise HTTPException(
            status_code=401,
            detail=mensagem_invalida,
        )

    if not verificar_senha(
        senha,
        usuario.senha_hash,
    ):
        raise HTTPException(
            status_code=401,
            detail=mensagem_invalida,
        )

    try:
        token = criar_sessao_mei(
            db,
            usuario.id,
        )
    except ValueError:
        raise HTTPException(
            status_code=401,
            detail=mensagem_invalida,
        ) from None

    response.set_cookie(
        key=COOKIE_MEI,
        value=token,
        httponly=True,
        secure=_cookie_seguro(),
        samesite="lax",
        max_age=DURACAO_SESSAO,
        path="/",
    )

    return {
        "autenticado": True,
        "usuario_mei_id": usuario.id,
        **_dados_loja_publica(db, usuario.estabelecimento_id),
        "estabelecimento_id": usuario.estabelecimento_id,
        "email": usuario.email,
        "csrf_token": _token_csrf(token),
    }


# ============================================================
# CONSULTAR SESSAO DO MEI
# ============================================================

@router.get("/me")
def consultar_login_mei(
    request: Request,
    db: Session = Depends(get_db),
):
    identidade = exigir_mei(request, db)

    token = _obter_token_mei(request)

    return {
        "autenticado": True,
        **identidade,
        **_dados_loja_publica(db, identidade["estabelecimento_id"]),
        "csrf_token": _token_csrf(token),
    }


# ============================================================
# LOGOUT DO MEI
# ============================================================

@router.post("/logout")
def logout_mei(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    exigir_mei_escrita(request, db)

    token = _obter_token_mei(request)

    revogar_sessao(db, token)

    response.delete_cookie(
        key=COOKIE_MEI,
        path="/",
        secure=_cookie_seguro(),
        httponly=True,
        samesite="lax",
    )

    return {
        "autenticado": False,
        "mensagem": "Sessao MEI encerrada.",
    }
