from datetime import date, datetime, time, timedelta
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from database.models import Compra, ItemCompra, get_db
from security.mei_routes import exigir_mei


router = APIRouter(
    prefix="/mei/dashboard",
    tags=["Dashboard MEI"],
)


class EvolucaoDiaria(BaseModel):
    data: date
    pedidos: int
    valor_centavos: int


class DashboardResposta(BaseModel):
    periodo: str
    inicio: date
    fim: date
    pedidos_confirmados: int
    valor_total_centavos: int
    ticket_medio_centavos: int
    unidades_vendidas: int
    evolucao_diaria: list[EvolucaoDiaria]


def resolver_periodo(
    periodo: str,
    inicio: date | None,
    fim: date | None,
) -> tuple[date, date]:
    hoje = datetime.now().date()

    if periodo == "personalizado":
        if inicio is None or fim is None:
            raise HTTPException(
                422,
                "Informe inicio e fim do periodo.",
            )

        if inicio > fim:
            raise HTTPException(
                422,
                "Data inicial posterior a data final.",
            )

        if (fim - inicio).days > 366:
            raise HTTPException(
                422,
                "Intervalo maximo de 367 dias.",
            )

        return inicio, fim

    if inicio is not None or fim is not None:
        raise HTTPException(
            422,
            "Datas manuais exigem periodo personalizado.",
        )

    dias = {"hoje": 1, "7d": 7, "30d": 30}[periodo]

    return hoje - timedelta(days=dias - 1), hoje


@router.get("", response_model=DashboardResposta)
def consultar_dashboard(
    periodo: Literal[
        "hoje", "7d", "30d", "personalizado"
    ] = Query(default="30d"),
    inicio: date | None = None,
    fim: date | None = None,
    identidade: dict = Depends(exigir_mei),
    db: Session = Depends(get_db),
):
    data_inicial, data_final = resolver_periodo(
        periodo,
        inicio,
        fim,
    )

    comeco = datetime.combine(data_inicial, time.min)
    termino = datetime.combine(
        data_final + timedelta(days=1),
        time.min,
    )

    filtros = (
        Compra.estabelecimento_id
        == identidade["estabelecimento_id"],
        Compra.status == "confirmado",
        Compra.criado_em >= comeco,
        Compra.criado_em < termino,
    )

    quantidade, valor = (
        db.query(
            func.count(Compra.id),
            func.coalesce(func.sum(Compra.valor_total), 0),
        )
        .filter(*filtros)
        .one()
    )

    unidades = (
        db.query(
            func.coalesce(func.sum(ItemCompra.quantidade), 0)
        )
        .join(
            Compra,
            ItemCompra.compra_id == Compra.id,
        )
        .filter(*filtros)
        .scalar()
    )

    dia = func.date(Compra.criado_em)

    linhas = (
        db.query(
            dia.label("data"),
            func.count(Compra.id),
            func.coalesce(func.sum(Compra.valor_total), 0),
        )
        .filter(*filtros)
        .group_by(dia)
        .order_by(dia)
        .all()
    )

    total = int(valor)
    pedidos = int(quantidade)

    # Arredondamento para centavos, sem usar float.
    ticket = (
        (total * 2 + pedidos) // (2 * pedidos)
        if pedidos
        else 0
    )

    return {
        "periodo": periodo,
        "inicio": data_inicial,
        "fim": data_final,
        "pedidos_confirmados": pedidos,
        "valor_total_centavos": total,
        "ticket_medio_centavos": ticket,
        "unidades_vendidas": int(unidades),
        "evolucao_diaria": [
            {
                "data": data,
                "pedidos": int(qtd),
                "valor_centavos": int(total_dia),
            }
            for data, qtd, total_dia in linhas
        ],
    }
