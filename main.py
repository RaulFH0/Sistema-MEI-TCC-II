
import json
import logging

from fastapi import FastAPI, Depends, HTTPException, Header
from sqlalchemy.orm import Session
from typing import List

from sqlalchemy.orm import selectinload
from database.models import Compra
from schemas.pedido import CompraHistoricoResponse

from database.models import init_db, get_db
from database import crud
from contextlib import asynccontextmanager

from schemas.pedido import (
    ProdutoCreate,
    ProdutoResponse,
    PedidoResponse,
    EntradaUsuario,
    RespostaAgente,
    EstoqueUpdate
)

from rag.loader import carregar_base_conhecimento
from crew.orquestrador import processar_pedido


# ============================================================
# CONFIGURACOES
# ============================================================

logger = logging.getLogger(__name__)

VERSAO_API = "1.2.2"

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("Inicializando banco de dados...")
    init_db()

    print("Carregando base de conhecimento RAG...")
    carregar_base_conhecimento()

    print("Sistema pronto!")

    yield

    print("Encerrando Sistema MEI.")

app = FastAPI(
    title="Sistema MEI - Agentes de IA",
    description=(
        "Sistema multiagente para atendimento "
        "e controle de estoque de microempreendedores"
    ),
    version=VERSAO_API,
    lifespan=lifespan
)





# ============================================================
# TRATAMENTO DE ERROS DE ATENDIMENTO
# ============================================================

def identificar_erro_atendimento(erro: str):
    """
    Classifica erros conhecidos retornados pelo orquestrador.

    O orquestrador atual retorna erros como texto.
    Essa classificacao e temporaria ate adotarmos
    erros estruturados e excecoes especificas.
    """

    mensagem = str(erro).strip()
    texto = mensagem.casefold()

    # Reutilizacao indevida da chave de idempotencia
    if (
        "chave de idempotencia" in texto
        and (
            "mensagem diferente" in texto
            or "dados diferentes" in texto
            or "ja utilizada" in texto
        )
    ):
        return 409, mensagem

    # Conflitos comerciais relacionados ao estoque
    if (
        "estoque insuficiente" in texto
        or "duplicado" in texto
    ):
        return 409, mensagem

    # Erros conhecidos de validacao do pedido
    erros_validacao = (
        "mensagem vazia",
        "mensagem invalida",
        "mensagem original invalida",
        "mensagem original vazia",
        "chave de idempotencia invalida",
        "chave de idempotencia muito longa",
        "mensagem original obrigatoria",
        "quantidade",
        "limite de 50",
        "compra sem produtos",
        "pedido sem produtos",
        "nao cadastrado",
        "não cadastrado",
        "produto inexistente",
        "item invalido",
        "item inválido",
        "nome do cliente",
        "nome do produto",
    )

    if any(
        trecho in texto
        for trecho in erros_validacao
    ):
        return 422, mensagem

    # Erros desconhecidos nao devem expor detalhes internos
    return 500, "Erro interno ao processar o atendimento."


# ============================================================
# ROTAS DE PRODUTOS
# ============================================================

@app.get(
    "/produtos",
    response_model=List[ProdutoResponse]
)
def listar_produtos(
    db: Session = Depends(get_db)
):
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
# ATUALIZACAO MANUAL DO ESTOQUE
# ============================================================

@app.patch(
    "/produtos/{produto_id}/estoque",
    response_model=ProdutoResponse
)
def atualizar_estoque_produto(
    produto_id: int,
    entrada: EstoqueUpdate,
    db: Session = Depends(get_db)
):
    if produto_id < 1:
        raise HTTPException(
            status_code=422,
            detail="Identificador do produto invalido."
        )

    try:
        return crud.atualizar_estoque(
            db=db,
            produto_id=produto_id,
            nova_quantidade=entrada.quantidade
        )

    except ValueError as erro:
        mensagem = str(erro)

        codigo = (
            404
            if mensagem == "Produto não encontrado."
            else 422
        )

        raise HTTPException(
            status_code=codigo,
            detail=mensagem
        ) from erro
# ============================================================
# ROTAS DE PEDIDOS LEGADOS
# ============================================================

@app.get(
    "/pedidos",
    response_model=List[PedidoResponse]
)
def listar_pedidos(
    db: Session = Depends(get_db)
):
    return crud.listar_pedidos(db)



# ============================================================
# HISTORICO DE COMPRAS V2
# ============================================================

@app.get(
    "/compras",
    response_model=List[CompraHistoricoResponse]
)
def listar_compras_v2(
    limite: int = 50,
    db: Session = Depends(get_db)
):
    if not 1 <= limite <= 100:
        raise HTTPException(
            status_code=422,
            detail="O limite deve estar entre 1 e 100."
        )

    compras = (
        db.query(Compra)
        .options(selectinload(Compra.itens))
        .order_by(Compra.id.desc())
        .limit(limite)
        .all()
    )

    return [
        {
            "id": compra.id,
            "cliente_nome": compra.cliente_nome,
            "valor_total": compra.valor_total,
            "status": compra.status,
            "criado_em": compra.criado_em,
            "itens": [
                {
                    "produto_id": item.produto_id,
                    "produto_nome": item.produto_nome,
                    "quantidade": item.quantidade,
                    "preco_unitario": item.preco_unitario,
                    "subtotal": item.subtotal,
                }
                for item in sorted(
                    compra.itens,
                    key=lambda item: item.id
                )
            ],
        }
        for compra in compras
    ]




# ============================================================
# ATENDIMENTO COM AGENTES DE IA - V2.2
# ============================================================

@app.post(
    "/atender",
    response_model=RespostaAgente
)
def atender_cliente(
    entrada: EntradaUsuario,
    idempotency_key: str = Header(
        ...,
        alias="Idempotency-Key",
        min_length=1,
        max_length=128
    )
):
    """
    Processa uma solicitacao de compra.

    A chave de idempotencia permite identificar
    reenvios sem registrar outra compra.

    Codigos:
    200 - Atendimento confirmado ou repetido
    409 - Conflito de chave ou estoque
    422 - Dados invalidos
    500 - Falha interna
    """

    try:
        resultado = processar_pedido(
            mensagem_usuario=entrada.mensagem,
            chave_idempotencia=idempotency_key
        )

    except Exception:
        logger.exception(
            "Falha inesperada na rota /atender"
        )

        raise HTTPException(
            status_code=500,
            detail=(
                "Erro interno ao processar o atendimento. "
                "Consulte o estado da compra antes de reenviar."
            )
        )

    tempo_ms = resultado.get("tempo_ms", 0)

    # ========================================================
    # COMPRA CONFIRMADA OU REQUISICAO REPETIDA
    # ========================================================

    if resultado.get("sucesso") is True:

        pedido = resultado["resultado"]

        compra_id = pedido["compra_id"]
        cliente = pedido["cliente_nome"]
        total = pedido["valor_total"]

        valor_formatado = (
            f"R$ {total:.2f}".replace(".", ",")
        )

        if pedido.get("requisicao_repetida"):
            acao = "pedido_repetido"

            mensagem = (
                f"Compra #{compra_id} de {cliente} "
                f"ja registrada anteriormente. "
                f"Valor total: {valor_formatado}. "
                "Nenhuma nova compra foi realizada."
            )

        else:
            acao = "pedido_confirmado"

            mensagem = (
                f"Compra #{compra_id} de {cliente} "
                f"confirmada com sucesso! "
                f"Valor total: {valor_formatado}."
            )

        return RespostaAgente(
            resposta=mensagem,
            acao_executada=acao,
            sucesso=True,
            dados={
                "tempo_ms": tempo_ms,
                "pedido": pedido
            }
        )

    # ========================================================
    # ATENDIMENTO REJEITADO
    # ========================================================

    erro = resultado.get(
        "erro",
        "Erro desconhecido."
    )

    codigo_http, mensagem_erro = (
        identificar_erro_atendimento(erro)
    )

    if codigo_http == 500:
        logger.error(
            "Erro nao classificado no atendimento: %s",
            erro
        )

    raise HTTPException(
        status_code=codigo_http,
        detail={
            "sucesso": False,
            "acao_executada": "pedido_nao_confirmado",
            "mensagem": mensagem_erro,
            "tempo_ms": tempo_ms
        }
    )


# ============================================================
# ROTA DE SAUDE
# ============================================================

@app.get("/")
def health_check():
    return {
        "status": "online",
        "sistema": "MEI Agentes IA",
        "versao": VERSAO_API
    }
