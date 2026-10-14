import os
from pathlib import Path
from dotenv import load_dotenv

from sqlalchemy import event
from sqlalchemy import ForeignKey, UniqueConstraint, CheckConstraint
from sqlalchemy.orm import relationship
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime

Base = declarative_base()

# ============================================================
# TABELA DE PRODUTOS / ESTOQUE
# ============================================================
class Produto(Base):
    __tablename__ = "produtos"

    id          = Column(Integer, primary_key=True, index=True)
    nome        = Column(String, nullable=False)
    descricao   = Column(String)
    preco       = Column(Float, nullable=False)
    quantidade  = Column(Integer, nullable=False, default=0)
    categoria   = Column(String)
    criado_em   = Column(DateTime, default=datetime.now)
    atualizado_em = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    def __repr__(self):
        return f"<Produto(id={self.id}, nome={self.nome}, qtd={self.quantidade})>"


# ============================================================
# TABELA DE PEDIDOS
# ============================================================
class Pedido(Base):
    __tablename__ = "pedidos"

    id            = Column(Integer, primary_key=True, index=True)
    cliente_nome  = Column(String, nullable=False)
    produto_id    = Column(Integer, nullable=False)
    produto_nome  = Column(String, nullable=False)
    quantidade    = Column(Integer, nullable=False)
    valor_total   = Column(Float, nullable=False)
    status        = Column(String, default="pendente")  # pendente, confirmado, cancelado
    criado_em     = Column(DateTime, default=datetime.now)

    def __repr__(self):
        return f"<Pedido(id={self.id}, cliente={self.cliente_nome}, status={self.status})>"


# ============================================================
# TABELA DE LOGS DO SISTEMA (para coleta de dados do TCC)
# ============================================================
class LogSistema(Base):
    __tablename__ = "logs_sistema"

    id              = Column(Integer, primary_key=True, index=True)
    acao            = Column(String, nullable=False)  # triagem, consulta, escrita
    entrada_usuario = Column(String)                  # o que o usuário digitou
    resposta_agente = Column(String)                  # o que o agente retornou
    tempo_ms        = Column(Integer)                 # tempo de execução em ms
    sucesso         = Column(String, default="sim")   # sim ou nao
    erro            = Column(String)                  # mensagem de erro se houver
    criado_em       = Column(DateTime, default=datetime.now)


# ============================================================
# CONFIGURAÇÃO DO BANCO
# ============================================================
# Carrega as configurações do arquivo .env
load_dotenv()

# Usa o banco original quando nenhuma configuração é definida
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "sqlite:///./sistema_mei.db"
)

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False}
)

@event.listens_for(engine, "connect")
def ativar_chaves_estrangeiras(dbapi_connection, connection_record):
    if engine.dialect.name == "sqlite":
        cursor = dbapi_connection.cursor()
        try:
            cursor.execute("PRAGMA foreign_keys=ON")
        finally:
            cursor.close()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


# ============================================================
# NOVA TABELA DE COMPRAS
# ============================================================

class Compra(Base):
    __tablename__ = "compras"

    id = Column(Integer, primary_key=True, index=True)

    cliente_nome = Column(
        String,
        nullable=False
    )

    chave_idempotencia = Column(
        String,
        nullable=False,
        unique=True
    )

    hash_solicitacao = Column(
    String(64),
    nullable=True
    )
    valor_total = Column(
        Integer,
        nullable=False,
        default=0
    )  # Valor em centavos

    status = Column(
        String,
        nullable=False,
        default="confirmado"
    )

    criado_em = Column(
        DateTime,
        default=datetime.now,
        nullable=False
    )

    itens = relationship(
        "ItemCompra",
        back_populates="compra",
        cascade="all, delete-orphan"
    )

    __table_args__ = (
        CheckConstraint(
            "valor_total >= 0",
            name="ck_compra_valor_total"
        ),
    )


# ============================================================
# NOVA TABELA DE ITENS DA COMPRA
# ============================================================

class ItemCompra(Base):
    __tablename__ = "itens_compra"

    id = Column(Integer, primary_key=True, index=True)

    compra_id = Column(
        Integer,
        ForeignKey("compras.id"),
        nullable=False
    )

    produto_id = Column(
        Integer,
        ForeignKey("produtos.id"),
        nullable=False
    )

    produto_nome = Column(
        String,
        nullable=False
    )

    quantidade = Column(
        Integer,
        nullable=False
    )

    preco_unitario = Column(
        Integer,
        nullable=False
    )  # Valor em centavos

    subtotal = Column(
        Integer,
        nullable=False
    )  # Valor em centavos

    compra = relationship(
        "Compra",
        back_populates="itens"
    )

    __table_args__ = (
        CheckConstraint(
            "quantidade > 0 AND quantidade <= 50",
            name="ck_item_quantidade"
        ),
        CheckConstraint(
            "preco_unitario >= 0",
            name="ck_item_preco"
        ),
        CheckConstraint(
            "subtotal >= 0",
            name="ck_item_subtotal"
        ),
        UniqueConstraint(
            "compra_id",
            "produto_id",
            name="uq_compra_produto"
        )
    )


def init_db():
    Base.metadata.create_all(bind=engine)
    print("Banco de dados inicializado com sucesso!")

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()