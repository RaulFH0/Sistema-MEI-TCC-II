
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
)
from sqlalchemy.orm import relationship

def agora_utc():
    return datetime.now(timezone.utc).replace(tzinfo=None)


from database.models import Base


# ============================================================
# ESTABELECIMENTOS
# ============================================================

class Estabelecimento(Base):
    __tablename__ = "estabelecimentos"

    id = Column(
        Integer,
        primary_key=True,
        index=True,
    )

    nome = Column(
        String(150),
        nullable=False,
    )

    slug = Column(
        String(80),
        unique=True,
        nullable=False,
        index=True,
    )

    ativo = Column(
        Boolean,
        nullable=False,
        default=True,
    )

    criado_em = Column(
        DateTime,
        nullable=False,
        default=agora_utc,
    )

    usuarios = relationship(
        "UsuarioMEI",
        back_populates="estabelecimento",
    )


# ============================================================
# CONTAS DOS MICROEMPREENDEDORES
# ============================================================

class UsuarioMEI(Base):
    __tablename__ = "usuarios_mei"

    id = Column(
        Integer,
        primary_key=True,
        index=True,
    )

    estabelecimento_id = Column(
        Integer,
        ForeignKey("estabelecimentos.id"),
        nullable=False,
        index=True,
    )

    nome = Column(
        String(150),
        nullable=False,
    )

    email = Column(
        String(254),
        nullable=False,
        unique=True,
        index=True,
    )

    senha_hash = Column(
        String(255),
        nullable=False,
    )

    ativo = Column(
        Boolean,
        nullable=False,
        default=True,
    )

    criado_em = Column(
        DateTime,
        nullable=False,
        default=agora_utc,
    )

    estabelecimento = relationship(
        "Estabelecimento",
        back_populates="usuarios",
    )
