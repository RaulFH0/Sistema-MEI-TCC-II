
import json
import logging

from fastapi import FastAPI, Depends, HTTPException, Header
from sqlalchemy.orm import Session
from typing import List
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload
from database.models import Compra
from schemas.pedido import CompraHistoricoResponse
from database.models import Produto
from database.models import init_db, get_db
from database import crud
from contextlib import asynccontextmanager

from security.routes import router as auth_router
from security.routes import (
    exigir_admin,
    exigir_admin_escrita
)

from decimal import Decimal, ROUND_HALF_UP

from schemas.pedido import (
    ProdutoCreate,
    ProdutoResponse,
    PedidoResponse,
    EntradaUsuario,
    RespostaAgente,
    EstoqueUpdate,
    EstoqueMinimoUpdate,
    OrcamentoEntrada,
    OrcamentoResposta,
    ConfirmacaoLojaEntrada
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


app.include_router(auth_router)


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
    response_model=ProdutoResponse,
    dependencies=[Depends(exigir_admin_escrita)]
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
    response_model=ProdutoResponse,
    dependencies=[Depends(exigir_admin_escrita)]
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
# CONFIGURACAO DO ESTOQUE MINIMO
# ============================================================

@app.patch(
    "/produtos/{produto_id}/estoque-minimo",
    response_model=ProdutoResponse,
    dependencies=[Depends(exigir_admin_escrita)]
)
def configurar_estoque_minimo(
    produto_id: int,
    entrada: EstoqueMinimoUpdate,
    db: Session = Depends(get_db)
):
    if produto_id < 1:
        raise HTTPException(
            status_code=422,
            detail="Identificador do produto invalido."
        )

    produto = db.query(Produto).filter(
        Produto.id == produto_id
    ).first()

    if produto is None:
        raise HTTPException(
            status_code=404,
            detail="Produto não encontrado."
        )

    produto.estoque_minimo = entrada.estoque_minimo

    try:
        db.commit()
        db.refresh(produto)
    except Exception:
        db.rollback()
        raise

    return produto

# ============================================================
# ROTAS DE PEDIDOS LEGADOS
# ============================================================

@app.get(
    "/pedidos",
    response_model=List[PedidoResponse],
    dependencies=[Depends(exigir_admin)]
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
    response_model=List[CompraHistoricoResponse],
    dependencies=[Depends(exigir_admin)]
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
# PORTAL DO CLIENTE - ORCAMENTO SEM VENDA
# ============================================================

@app.post(
    "/loja/orcamento",
    response_model=OrcamentoResposta
)
def gerar_orcamento(
    entrada: OrcamentoEntrada,
    db: Session = Depends(get_db)
):
    cliente = entrada.cliente_nome.strip()

    if not cliente:
        raise HTTPException(
            status_code=422,
            detail="Nome do cliente obrigatorio."
        )

    quantidades: dict[int, int] = {}

    for item in entrada.itens:
        quantidades[item.produto_id] = (
            quantidades.get(item.produto_id, 0)
            + item.quantidade
        )

    if any(qtd > 50 for qtd in quantidades.values()):
        raise HTTPException(
            status_code=422,
            detail="Limite de 50 unidades por produto."
        )

    itens_resposta = []
    total_centavos = 0

    for produto_id, quantidade in sorted(quantidades.items()):
        produto = db.get(Produto, produto_id)

        if produto is None:
            raise HTTPException(
                status_code=404,
                detail=f"Produto {produto_id} nao encontrado."
            )

        if produto.quantidade < quantidade:
            raise HTTPException(
                status_code=409,
                detail=(
                    f"Estoque insuficiente para {produto.nome}. "
                    f"Disponivel: {produto.quantidade}."
                )
            )

        preco = Decimal(str(produto.preco))

        if not preco.is_finite() or preco <= 0:
            raise HTTPException(
                status_code=422,
                detail=f"Preco invalido: {produto.nome}."
            )

        preco_centavos = int(
            (preco * 100).quantize(
                Decimal("1"),
                rounding=ROUND_HALF_UP
            )
        )

        subtotal = preco_centavos * quantidade
        total_centavos += subtotal

        itens_resposta.append({
            "produto_id": produto.id,
            "produto_nome": produto.nome,
            "quantidade": quantidade,
            "preco_unitario_centavos": preco_centavos,
            "subtotal_centavos": subtotal
        })

    return {
        "cliente_nome": cliente,
        "itens": itens_resposta,
        "valor_total_centavos": total_centavos,
        "mensagem": (
            "Orcamento calculado. "
            "Nenhuma compra foi registrada. "
            "Precos e estoque sujeitos a verificacao "
            "no momento da confirmacao."
        )
    }


# ============================================================
# PORTAL DO CLIENTE - CONFIRMACAO DE COMPRA
# ============================================================

@app.post("/loja/confirmar")
def confirmar_compra_loja(
    entrada: ConfirmacaoLojaEntrada,
    idempotency_key: str = Header(
        ...,
        alias="Idempotency-Key",
        min_length=1,
        max_length=128
    ),
    db: Session = Depends(get_db)
):
    # Consultar os produtos por ID e consolidar itens.
    # O registro definitivo validara novamente cada ID
    # dentro da transacao.
    quantidades: dict[int, int] = {}

    for item in entrada.itens:
        quantidades[item.produto_id] = (
            quantidades.get(item.produto_id, 0)
            + item.quantidade
        )

    if any(qtd > 50 for qtd in quantidades.values()):
        raise HTTPException(
            status_code=422,
            detail="Limite de 50 unidades por produto."
        )

    itens_compra = [
        {
            "produto_id": produto_id,
            "quantidade": quantidade
        }
        for produto_id, quantidade in sorted(quantidades.items())
    ]

    try:
        resultado = crud.registrar_compra_segura(
            db=db,
            cliente_nome=entrada.cliente_nome,
            itens=itens_compra,
            chave_idempotencia=idempotency_key,
            total_aprovado_centavos=entrada.valor_total_centavos,
            identificar_por_id=True
        )

        return {
            "sucesso": True,
            "acao_executada": (
                "pedido_repetido"
                if resultado["requisicao_repetida"]
                else "pedido_confirmado"
            ),
            "pedido": resultado
        }

    except ValueError as erro:
        mensagem = str(erro)

        if (
            "Chave de idempotencia" in mensagem
            or "chave de idempotencia" in mensagem
        ):
            codigo = 409
        elif (
            "Estoque insuficiente" in mensagem
            or "valor do pedido mudou" in mensagem
        ):
            codigo = 409
        elif "nao cadastrado" in mensagem:
            codigo = 404
        else:
            codigo = 422

        raise HTTPException(
            status_code=codigo,
            detail=mensagem
        ) from erro

    except IntegrityError as erro:
        logger.exception(
            "Conflito de integridade na confirmacao da loja"
        )
        raise HTTPException(
            status_code=409,
            detail=(
                "Nao foi possivel confirmar a compra. "
                "Verifique o pedido antes de reenviar."
            )
        ) from erro

    except Exception as erro:
        logger.exception(
            "Falha interna na confirmacao da loja"
        )
        raise HTTPException(
            status_code=500,
            detail=(
                "Resultado da confirmacao incerto. "
                "Nao crie outra chave para repetir a compra."
            )
        ) from erro




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
