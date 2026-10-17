
import hashlib
import secrets

from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from database.models import SessaoAdmin


TEMPO_SESSAO_HORAS = 8


def _agora():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


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
            SessaoAdmin.token_hash == _hash_token(token)
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
