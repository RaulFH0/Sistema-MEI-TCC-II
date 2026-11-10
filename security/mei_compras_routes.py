from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session, selectinload

from database.models import Compra, get_db
from schemas.pedido import CompraHistoricoResponse
from security.mei_routes import exigir_mei


router = APIRouter(
    prefix="/mei/compras",
    tags=["Compras MEI"],
)


@router.get("", response_model=list[CompraHistoricoResponse])
def listar_compras_mei(
    limite: int = Query(default=50, ge=1, le=100),
    identidade: dict = Depends(exigir_mei),
    db: Session = Depends(get_db),
):
    estabelecimento_id = identidade["estabelecimento_id"]

    compras = (
        db.query(Compra)
        .filter(
            Compra.estabelecimento_id == estabelecimento_id
        )
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
                    key=lambda item: item.id,
                )
            ],
        }
        for compra in compras
    ]
