import logging
import os
import secrets

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from database.models import get_db
from schemas.pedido import EntradaUsuario, RespostaAgente
from security.lojas_publicas_routes import _resolver_loja
from security.limite_atendimento_ia import limitador_atendimento_ia
from security.atendimento_multiintencao import (
    atender_multiintencao,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/lojas",
    tags=["Atendimento IA Experimental"],
)

ACOES_PERMITIDAS = frozenset({
    "consulta_catalogo",
    "solicitar_esclarecimento",
    "compra_pendente_confirmacao",
})


@router.post(
    "/{slug}/atendimento-experimental",
    response_model=RespostaAgente,
)
def atendimento_experimental(
    slug: str,
    entrada: EntradaUsuario,
    request: Request,
    db: Session = Depends(get_db),
):
    # Desativada por padrao.
    # Nunca habilitar publicamente antes de aplicar
    # controles de acesso e limite de chamadas.
    if os.getenv(
        "MEI_ATENDIMENTO_IA_EXPERIMENTAL"
    ) != "1":
        raise HTTPException(
            status_code=404,
            detail="Rota nao disponivel.",
        )

    chave_configurada = os.getenv(
        "MEI_ATENDIMENTO_IA_EXPERIMENTAL_KEY", ""
    )

    if len(chave_configurada) < 32:
        raise HTTPException(
            status_code=404,
            detail="Rota nao disponivel.",
        )

    chave_recebida = request.headers.get(
        "X-MEI-Experimental-Key", ""
    )

    if not secrets.compare_digest(
        chave_recebida.encode("utf-8"),
        chave_configurada.encode("utf-8"),
    ):
        raise HTTPException(
            status_code=403,
            detail="Acesso experimental negado.",
        )

    ip = (
        request.client.host
        if request.client is not None
        else "origem-desconhecida"
    )

    espera = limitador_atendimento_ia.consumir(ip)

    if espera is not None:
        raise HTTPException(
            status_code=429,
            detail="Limite experimental atingido.",
            headers={"Retry-After": str(espera)},
        )

    # A loja deve ser resolvida pelo servidor.
    # O cliente nao escolhe estabelecimento_id.
    loja = _resolver_loja(db, slug)

    try:
        resultado = atender_multiintencao(
            db,
            loja.id,
            entrada.mensagem,
        )
    except Exception:
        logger.exception(
            "Falha no atendimento experimental"
        )
        raise HTTPException(
            status_code=503,
            detail="Atendimento experimental indisponivel.",
        )

    # Este endpoint nunca confirma compras.
    if (
        not isinstance(resultado, dict)
        or resultado.get("sucesso") is not True
        or resultado.get("acao_executada")
        not in ACOES_PERMITIDAS
        or not isinstance(
            resultado.get("resposta"), str
        )
        or not resultado["resposta"].strip()
        or not isinstance(
            resultado.get("dados"), dict
        )
        or resultado["dados"].get(
            "compra_registrada"
        ) is not False
    ):
        logger.error(
            "Resultado experimental rejeitado"
        )
        raise HTTPException(
            status_code=503,
            detail="Resultado experimental invalido.",
        )

    return RespostaAgente(**resultado)
