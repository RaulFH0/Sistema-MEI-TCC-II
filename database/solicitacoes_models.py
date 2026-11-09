from sqlalchemy import (
    Column,
    Integer,
    String,
    DateTime,
    CheckConstraint,
)

from database.models import Base
from database.contas_models import agora_utc


class SolicitacaoCadastroMEI(Base):
    __tablename__ = "solicitacoes_cadastro_mei"

    __table_args__ = (
        CheckConstraint(
            "status IN ('pendente', 'aprovado', 'rejeitado')",
            name="ck_solicitacao_mei_status",
        ),
    )

    id = Column(
        Integer,
        primary_key=True,
        index=True,
    )

    nome_completo = Column(
        String(150),
        nullable=False,
    )

    email = Column(
        String(254),
        nullable=False,
        index=True,
    )

    cnpj = Column(
        String(14),
        nullable=False,
        index=True,
    )

    telefone = Column(
        String(20),
        nullable=False,
    )

    nome_estabelecimento = Column(
        String(150),
        nullable=False,
    )

    senha_hash = Column(
        String(255),
        nullable=False,
    )

    status = Column(
        String(20),
        nullable=False,
        default="pendente",
        index=True,
    )

    criado_em = Column(
        DateTime,
        nullable=False,
        default=agora_utc,
    )

    analisado_em = Column(
        DateTime,
        nullable=True,
    )

    analisado_por = Column(
        String(100),
        nullable=True,
    )

    observacao_admin = Column(
        String(500),
        nullable=True,
    )


# Indices parciais: apenas solicitacoes pendentes.
# A mesma regra passa a valer nos bancos de teste.
from sqlalchemy import Index, func, text

Index(
    "uq_solicitacao_mei_email_pendente",
    func.lower(SolicitacaoCadastroMEI.__table__.c.email),
    unique=True,
    sqlite_where=text("status = 'pendente'"),
)

Index(
    "uq_solicitacao_mei_cnpj_pendente",
    SolicitacaoCadastroMEI.__table__.c.cnpj,
    unique=True,
    sqlite_where=text("status = 'pendente'"),
)


# Garante que um CNPJ possua no maximo
# uma solicitacao aprovada.
Index(
    "uq_solicitacao_mei_cnpj_aprovado",
    SolicitacaoCadastroMEI.__table__.c.cnpj,
    unique=True,
    sqlite_where=text("status = 'aprovado'"),
)
