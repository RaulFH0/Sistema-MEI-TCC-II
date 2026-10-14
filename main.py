
import json

from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from database.models import init_db, get_db
from database import crud

from schemas.pedido import (
    ProdutoCreate,
    ProdutoResponse,
    PedidoResponse,
    EntradaUsuario,
    RespostaAgente
)

from rag.loader import carregar_base_conhecimento
from crew.orquestrador import processar_pedido


# ============================================================
# INICIALIZAÇÃO
# ============================================================

app = FastAPI(
    title="Sistema MEI - Agentes de IA",
    description=(
        "Sistema multiagente para atendimento "
        "e controle de estoque de microempreendedores"
    ),
    version="1.1.0"
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

@app.get(
    "/produtos",
    response_model=List[ProdutoResponse]
)
def listar_produtos(db: Session = Depends(get_db)):
    return crud.listar_produtos(db)


@app.post(
    "/produtos",
    response_model=ProdutoResponse
)
def criar_produto(
    produto: ProdutoCreate,
    db: Session = Depends(get_db)
):
    try:
        return crud.criar_produto(
            db=db,
            nome=produto.nome,
            preco=produto.preco,
            quantidade=produto.quantidade,
            descricao=produto.descricao,
            categoria=produto.categoria
        )

    except ValueError as erro:
        raise HTTPException(
            status_code=400,
            detail=str(erro)
        ) from erro


# ============================================================
# ROTAS DE PEDIDOS
# ============================================================

@app.get(
    "/pedidos",
    response_model=List[PedidoResponse]
)
def listar_pedidos(db: Session = Depends(get_db)):
    return crud.listar_pedidos(db)


# ============================================================
# ATENDIMENTO COM AGENTES DE IA
# ============================================================

@app.post(
    "/atender",
    response_model=RespostaAgente
)
def atender_cliente(entrada: EntradaUsuario):

    resultado = processar_pedido(entrada.mensagem)
    tempo_ms = resultado.get("tempo_ms", 0)

    if resultado.get("sucesso") is True:

        pedido = resultado["resultado"]

        # A confirmação utiliza somente os dados
        # persistidos pelo CRUD.
        return RespostaAgente(
            resposta=json.dumps(
                pedido,
                ensure_ascii=False
            ),
            acao_executada="pedido_confirmado",
            sucesso=True,
            dados={
                "tempo_ms": tempo_ms,
                "pedido": pedido
            }
        )

    return RespostaAgente(
        resposta=(
            "Não foi possível confirmar o pedido: "
            f"{resultado.get('erro', 'erro desconhecido')}"
        ),
        acao_executada="pedido_nao_confirmado",
        sucesso=False,
        dados={
            "tempo_ms": tempo_ms
        }
    )


# ============================================================
# ROTA DE SAÚDE
# ============================================================

@app.get("/")
def health_check():
    return {
        "status": "online",
        "sistema": "MEI Agentes IA",
        "versao": "1.1.0"
    }
