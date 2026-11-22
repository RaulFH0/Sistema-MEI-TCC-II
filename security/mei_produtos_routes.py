
from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
)
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from database.models import Produto, get_db

from database.crud import (
    criar_produto_mei,
    buscar_produto_por_nome_mei,
    listar_produtos_mei,
    atualizar_estoque_mei,
)

from security.mei_routes import (
    exigir_mei,
    exigir_mei_escrita,
)


router = APIRouter(
    prefix="/mei/produtos",
    tags=["Produtos MEI"],
)


# ============================================================
# MODELOS DE ENTRADA
# ============================================================

class ProdutoMEIEntrada(BaseModel):
    nome: str = Field(min_length=1, max_length=150)
    preco: float = Field(gt=0)
    quantidade: int = Field(ge=0)
    descricao: str = ""
    categoria: str = ""


class EstoqueMEIEntrada(BaseModel):
    nova_quantidade: int = Field(ge=0)


class EstoqueMinimoMEIEntrada(BaseModel):
    estoque_minimo: int = Field(strict=True, ge=0)


# ============================================================
# FORMATACAO DOS RESULTADOS
# ============================================================

def _produto_resposta(produto):
    return {
        "id": produto.id,
        "estabelecimento_id": produto.estabelecimento_id,
        "nome": produto.nome,
        "preco": produto.preco,
        "quantidade": produto.quantidade,
        "estoque_minimo": produto.estoque_minimo,
        "descricao": produto.descricao,
        "categoria": produto.categoria,
    }


def _erro_validacao(erro: ValueError):
    raise HTTPException(
        status_code=400,
        detail=str(erro),
    ) from erro


# ============================================================
# LISTAR PRODUTOS DA LOJA AUTENTICADA
# ============================================================

@router.get("")
def listar_produtos_autenticados(
    identidade: dict = Depends(exigir_mei),
    db: Session = Depends(get_db),
):
    try:
        produtos = listar_produtos_mei(
            db=db,
            estabelecimento_id=identidade[
                "estabelecimento_id"
            ],
        )

    except ValueError as erro:
        _erro_validacao(erro)

    return [
        _produto_resposta(produto)
        for produto in produtos
    ]


# ============================================================
# BUSCAR PRODUTO DA LOJA AUTENTICADA
# ============================================================

@router.get("/buscar")
def buscar_produto_autenticado(
    nome: str = Query(min_length=1),
    identidade: dict = Depends(exigir_mei),
    db: Session = Depends(get_db),
):
    try:
        produto = buscar_produto_por_nome_mei(
            db=db,
            estabelecimento_id=identidade[
                "estabelecimento_id"
            ],
            nome=nome,
        )

    except ValueError as erro:
        _erro_validacao(erro)

    if produto is None:
        raise HTTPException(
            status_code=404,
            detail="Produto nao encontrado.",
        )

    return _produto_resposta(produto)


# ============================================================
# CADASTRAR PRODUTO NA LOJA AUTENTICADA
# ============================================================

@router.post("", status_code=201)
def cadastrar_produto_autenticado(
    entrada: ProdutoMEIEntrada,
    identidade: dict = Depends(exigir_mei_escrita),
    db: Session = Depends(get_db),
):
    try:
        produto = criar_produto_mei(
            db=db,
            estabelecimento_id=identidade[
                "estabelecimento_id"
            ],
            nome=entrada.nome,
            preco=entrada.preco,
            quantidade=entrada.quantidade,
            descricao=entrada.descricao,
            categoria=entrada.categoria,
        )

    except ValueError as erro:
        _erro_validacao(erro)

    return _produto_resposta(produto)


# ============================================================
# ATUALIZAR ESTOQUE DA LOJA AUTENTICADA
# ============================================================

@router.patch("/{produto_id}/estoque")
def atualizar_estoque_autenticado(
    produto_id: int,
    entrada: EstoqueMEIEntrada,
    identidade: dict = Depends(exigir_mei_escrita),
    db: Session = Depends(get_db),
):
    try:
        produto = atualizar_estoque_mei(
            db=db,
            estabelecimento_id=identidade[
                "estabelecimento_id"
            ],
            produto_id=produto_id,
            nova_quantidade=entrada.nova_quantidade,
        )

    except ValueError as erro:
        _erro_validacao(erro)

    return _produto_resposta(produto)


# Configuracao do estoque minimo do MEI autenticado.
@router.patch("/{produto_id}/estoque-minimo")
def atualizar_estoque_minimo_autenticado(
    produto_id: int,
    entrada: EstoqueMinimoMEIEntrada,
    identidade: dict = Depends(exigir_mei_escrita),
    db: Session = Depends(get_db),
):
    if produto_id < 1:
        raise HTTPException(
            status_code=422,
            detail="Produto invalido."
        )

    produto = db.query(Produto).filter(
        Produto.id == produto_id,
        Produto.estabelecimento_id ==
            identidade["estabelecimento_id"],
    ).first()

    if produto is None:
        raise HTTPException(
            status_code=404,
            detail="Produto nao encontrado."
        )

    produto.estoque_minimo = entrada.estoque_minimo

    try:
        db.commit()
        db.refresh(produto)
    except Exception:
        db.rollback()
        raise

    return _produto_resposta(produto)
