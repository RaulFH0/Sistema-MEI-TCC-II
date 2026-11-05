
import logging
from decimal import Decimal, ROUND_HALF_UP

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from database import crud
from database.models import Produto, get_db
from database.contas_models import Estabelecimento

from schemas.pedido import ProdutoResponse

from schemas.pedido import (
    OrcamentoEntrada,
    OrcamentoResposta,
    ConfirmacaoLojaEntrada,
)


logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/lojas",
    tags=["Portal Publico Multi-MEI"],
)


def _resolver_loja(db: Session, slug: str) -> Estabelecimento:
    loja = (
        db.query(Estabelecimento)
        .filter(
            Estabelecimento.slug == slug,
            Estabelecimento.ativo.is_(True),
        )
        .first()
    )

    if loja is None:
        raise HTTPException(
            status_code=404,
            detail="Loja nao encontrada.",
        )

    return loja


# ============================================================
# CATALOGO PUBLICO - MULTI-MEI
# ============================================================

@router.get(
    "/{slug}/produtos",
    response_model=list[ProdutoResponse],
)
def listar_produtos_publicos_mei(
    slug: str,
    db: Session = Depends(get_db),
):
    """
    Lista somente os produtos de uma loja ativa.

    O slug identifica o estabelecimento publico.
    O ID da loja e resolvido pelo backend.

    Nenhum produto de outro estabelecimento
    pode ser retornado por esta rota.
    """

    loja = _resolver_loja(db, slug)

    produtos = (
        db.query(Produto)
        .filter(
            Produto.estabelecimento_id == loja.id
        )
        .order_by(Produto.id)
        .all()
    )

    return produtos


def _consolidar_itens(itens):
    quantidades = {}

    for item in itens:
        produto_id = item.produto_id
        quantidade = item.quantidade

        if type(produto_id) is not int or produto_id < 1:
            raise HTTPException(
                status_code=422,
                detail="ID do produto invalido.",
            )

        if type(quantidade) is not int or quantidade < 1:
            raise HTTPException(
                status_code=422,
                detail="Quantidade invalida.",
            )

        quantidades[produto_id] = (
            quantidades.get(produto_id, 0) + quantidade
        )

    if not quantidades:
        raise HTTPException(
            status_code=422,
            detail="Pedido sem produtos.",
        )

    if any(qtd > 50 for qtd in quantidades.values()):
        raise HTTPException(
            status_code=422,
            detail="Limite de 50 unidades por produto.",
        )

    return quantidades


@router.post(
    "/{slug}/orcamento",
    response_model=OrcamentoResposta,
)
def gerar_orcamento_publico_mei(
    slug: str,
    entrada: OrcamentoEntrada,
    db: Session = Depends(get_db),
):
    loja = _resolver_loja(db, slug)

    cliente = entrada.cliente_nome.strip()

    if not cliente:
        raise HTTPException(
            status_code=422,
            detail="Nome do cliente obrigatorio.",
        )

    quantidades = _consolidar_itens(entrada.itens)

    itens_resposta = []
    total_centavos = 0

    for produto_id, quantidade in sorted(
        quantidades.items()
    ):
        produto = (
            db.query(Produto)
            .filter(
                Produto.id == produto_id,
                Produto.estabelecimento_id == loja.id,
            )
            .first()
        )

        if produto is None:
            raise HTTPException(
                status_code=404,
                detail=f"Produto {produto_id} nao encontrado.",
            )

        if produto.quantidade < quantidade:
            raise HTTPException(
                status_code=409,
                detail=(
                    f"Estoque insuficiente para {produto.nome}. "
                    f"Disponivel: {produto.quantidade}."
                ),
            )

        preco = Decimal(str(produto.preco))

        if not preco.is_finite() or preco <= 0:
            raise HTTPException(
                status_code=422,
                detail=f"Preco invalido: {produto.nome}.",
            )

        preco_centavos = int(
            (preco * 100).quantize(
                Decimal("1"),
                rounding=ROUND_HALF_UP,
            )
        )

        subtotal = preco_centavos * quantidade
        total_centavos += subtotal

        itens_resposta.append({
            "produto_id": produto.id,
            "produto_nome": produto.nome,
            "quantidade": quantidade,
            "preco_unitario_centavos": preco_centavos,
            "subtotal_centavos": subtotal,
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
        ),
    }


@router.post("/{slug}/confirmar")
def confirmar_compra_publica_mei(
    slug: str,
    entrada: ConfirmacaoLojaEntrada,
    idempotency_key: str = Header(
        ...,
        alias="Idempotency-Key",
        min_length=1,
        max_length=128,
    ),
    db: Session = Depends(get_db),
):
    loja = _resolver_loja(db, slug)
    quantidades = _consolidar_itens(entrada.itens)

    itens_compra = [
        {
            "produto_id": produto_id,
            "quantidade": quantidade,
        }
        for produto_id, quantidade
        in sorted(quantidades.items())
    ]

    try:
        resultado = crud.registrar_compra_segura(
            db=db,
            cliente_nome=entrada.cliente_nome,
            itens=itens_compra,
            chave_idempotencia=idempotency_key,
            total_aprovado_centavos=(
                entrada.valor_total_centavos
            ),
            identificar_por_id=True,
            estabelecimento_id=loja.id,
        )

        return {
            "sucesso": True,
            "acao_executada": (
                "pedido_repetido"
                if resultado["requisicao_repetida"]
                else "pedido_confirmado"
            ),
            "pedido": resultado,
        }

    except ValueError as erro:
        mensagem = str(erro)
        texto = mensagem.casefold()

        if (
            "chave de idempotencia" in texto
            or "estoque insuficiente" in texto
            or "valor do pedido mudou" in texto
        ):
            codigo = 409
        elif "nao cadastrado" in texto:
            codigo = 404
        else:
            codigo = 422

        raise HTTPException(
            status_code=codigo,
            detail=mensagem,
        ) from erro

    except IntegrityError as erro:
        db.rollback()
        logger.exception(
            "Conflito de integridade na compra publica"
        )
        raise HTTPException(
            status_code=409,
            detail="Nao foi possivel confirmar a compra.",
        ) from erro

    except Exception as erro:
        db.rollback()
        logger.exception(
            "Falha interna na compra publica"
        )
        raise HTTPException(
            status_code=500,
            detail="Erro interno ao confirmar a compra.",
        ) from erro
