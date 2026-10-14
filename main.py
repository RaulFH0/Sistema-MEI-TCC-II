from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from database.models import init_db, get_db
from database import crud
from schemas.pedido import (
    ProdutoCreate, ProdutoResponse,
    PedidoResponse, EntradaUsuario, RespostaAgente
)
from rag.loader import carregar_base_conhecimento
from crew.orquestrador import processar_pedido
from typing import List

# ============================================================
# INICIALIZAÇÃO
# ============================================================
app = FastAPI(
    title="Sistema MEI - Agentes de IA",
    description="Sistema multi-agente para microempreendedores",
    version="1.0.0"
)

@app.on_event("startup")
def startup():
    print("Inicializando banco de dados...")
    init_db()
    print("Carregando base de conhecimento RAG...")
    carregar_base_conhecimento()
    print("Sistema pronto!")


# ============================================================
# ROTAS DE PRODUTOS
# ============================================================
@app.get("/produtos", response_model=List[ProdutoResponse])
def listar_produtos(db: Session = Depends(get_db)):
    """Lista todos os produtos no estoque."""
    return crud.listar_produtos(db)

@app.post("/produtos", response_model=ProdutoResponse)
def criar_produto(produto: ProdutoCreate, db: Session = Depends(get_db)):
    """Cadastra um novo produto no estoque."""
    return crud.criar_produto(
        db=db,
        nome=produto.nome,
        preco=produto.preco,
        quantidade=produto.quantidade,
        descricao=produto.descricao,
        categoria=produto.categoria
    )


# ============================================================
# ROTAS DE PEDIDOS
# ============================================================
@app.get("/pedidos", response_model=List[PedidoResponse])
def listar_pedidos(db: Session = Depends(get_db)):
    """Lista todos os pedidos registrados."""
    return crud.listar_pedidos(db)


# ============================================================
# ROTA PRINCIPAL — AGENTES DE IA
# ============================================================
@app.post("/atender", response_model=RespostaAgente)
def atender_cliente(entrada: EntradaUsuario):
    """
    Recebe uma mensagem em linguagem natural e aciona
    os agentes CrewAI para processar o pedido completo.
    """
    resultado = processar_pedido(entrada.mensagem)

    if resultado["sucesso"]:
        return RespostaAgente(
            resposta=resultado["resultado"],
            acao_executada="pedido_processado",
            sucesso=True,
            dados={"tempo_ms": resultado["tempo_ms"]}
        )
    else:
        return RespostaAgente(
            resposta=f"Erro ao processar: {resultado['erro']}",
            acao_executada="erro",
            sucesso=False,
            dados={"tempo_ms": resultado["tempo_ms"]}
        )


# ============================================================
# ROTA DE SAÚDE
# ============================================================
@app.get("/")
def health_check():
    return {"status": "online", "sistema": "MEI Agentes IA"}