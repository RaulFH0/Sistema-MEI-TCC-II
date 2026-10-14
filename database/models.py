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
DATABASE_URL = "sqlite:///./sistema_mei.db"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False}
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def init_db():
    Base.metadata.create_all(bind=engine)
    print("Banco de dados inicializado com sucesso!")

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()