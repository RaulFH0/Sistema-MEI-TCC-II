
import hashlib
import secrets

from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from database.models import SessaoAdmin
from database.contas_models import UsuarioMEI, Estabelecimento


TEMPO_SESSAO_HORAS = 8


def _agora():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


# ============================================================
# SESSOES ADMINISTRATIVAS EXISTENTES
# ============================================================

def criar_sessao(
    db: Session,
    usuario: str,
) -> str:
    if not isinstance(usuario, str) or not usuario.strip():
        raise ValueError("Usuario invalido.")

    token = secrets.token_urlsafe(48)

    sessao = SessaoAdmin(
        token_hash=_hash_token(token),
        usuario=usuario.strip(),
        criado_em=_agora(),
        expira_em=_agora() + timedelta(
            hours=TEMPO_SESSAO_HORAS
        ),
        revogada_em=None,
        usuario_mei_id=None,
        estabelecimento_id=None,
    )

    db.add(sessao)
    db.commit()

    return token


def consultar_sessao(
    db: Session,
    token: str,
) -> str | None:
    if not isinstance(token, str) or not token:
        return None

    sessao = (
        db.query(SessaoAdmin)
        .filter(
            SessaoAdmin.token_hash == _hash_token(token),
            SessaoAdmin.usuario_mei_id.is_(None),
            SessaoAdmin.estabelecimento_id.is_(None),
        )
        .first()
    )

    if sessao is None:
        return None

    if sessao.revogada_em is not None:
        return None

    if sessao.expira_em <= _agora():
        return None

    return sessao.usuario


def revogar_sessao(
    db: Session,
    token: str,
) -> bool:
    if not isinstance(token, str) or not token:
        return False

    sessao = (
        db.query(SessaoAdmin)
        .filter(
            SessaoAdmin.token_hash == _hash_token(token)
        )
        .first()
    )

    if sessao is None or sessao.revogada_em is not None:
        return False

    sessao.revogada_em = _agora()
    db.commit()

    return True


# ============================================================
# SESSOES DOS MICROEMPREENDEDORES
# ============================================================

def criar_sessao_mei(
    db: Session,
    usuario_mei_id: int,
) -> str:
    """
    Cria sessao para um usuario MEI ativo.

    O estabelecimento e identificado pelo banco,
    nunca por um ID informado pelo frontend.

    Esta funcao deve ser chamada somente depois
    da verificacao das credenciais do usuario.
    """

    if (
        not isinstance(usuario_mei_id, int)
        or isinstance(usuario_mei_id, bool)
        or usuario_mei_id < 1
    ):
        raise ValueError("Usuario MEI invalido.")

    usuario = db.get(UsuarioMEI, usuario_mei_id)

    if usuario is None or not usuario.ativo:
        raise ValueError("Usuario MEI inexistente ou inativo.")

    estabelecimento = db.get(
        Estabelecimento,
        usuario.estabelecimento_id,
    )

    if estabelecimento is None or not estabelecimento.ativo:
        raise ValueError("Estabelecimento inexistente ou inativo.")

    token = secrets.token_urlsafe(48)

    sessao = SessaoAdmin(
        token_hash=_hash_token(token),
        usuario=str(usuario.email),
        usuario_mei_id=usuario.id,
        estabelecimento_id=estabelecimento.id,
        criado_em=_agora(),
        expira_em=_agora() + timedelta(
            hours=TEMPO_SESSAO_HORAS
        ),
        revogada_em=None,
    )

    db.add(sessao)
    db.commit()

    return token


def consultar_sessao_mei(
    db: Session,
    token: str,
) -> dict | None:
    """
    Consulta sessao MEI e verifica se usuario
    e estabelecimento continuam ativos.

    Retorna identidade validada ou None.
    """

    if not isinstance(token, str) or not token:
        return None

    sessao = (
        db.query(SessaoAdmin)
        .filter(
            SessaoAdmin.token_hash == _hash_token(token),
            SessaoAdmin.usuario_mei_id.isnot(None),
            SessaoAdmin.estabelecimento_id.isnot(None),
        )
        .first()
    )

    if sessao is None:
        return None

    if sessao.revogada_em is not None:
        return None

    if sessao.expira_em <= _agora():
        return None

    usuario = db.get(
        UsuarioMEI,
        sessao.usuario_mei_id,
    )

    if usuario is None or not usuario.ativo:
        return None

    estabelecimento = db.get(
        Estabelecimento,
        sessao.estabelecimento_id,
    )

    if estabelecimento is None or not estabelecimento.ativo:
        return None

    # Impede que a sessao continue valida caso
    # o usuario seja transferido de estabelecimento.
    if usuario.estabelecimento_id != estabelecimento.id:
        return None

    return {
        "usuario_mei_id": usuario.id,
        "estabelecimento_id": estabelecimento.id,
        "email": usuario.email,
    }
