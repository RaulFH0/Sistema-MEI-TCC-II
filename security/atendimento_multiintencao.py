import time

from agents.classificador_intencao import classificar_intencao
from security.consulta_catalogo_ia import consultar_catalogo
from security.consulta_produto_ia import (
    consultar_produto_especifico,
)
from security.resposta_intencoes_ia import responder_intencao


def atender_multiintencao(
    db,
    estabelecimento_id: int,
    mensagem: str,
    *,
    classificador=None,
) -> dict:
    """
    Integra classificacao, roteamento e consultas.

    Nao executa pedidos e nao modifica estoque.
    O estabelecimento e definido pelo servidor,
    nunca por dados gerados pelo modelo.
    """

    if (
        type(estabelecimento_id) is not int
        or estabelecimento_id < 1
    ):
        raise ValueError("Estabelecimento invalido")

    if (
        not isinstance(mensagem, str)
        or not mensagem.strip()
        or len(mensagem) > 4000
    ):
        raise ValueError("Mensagem invalida")

    inicio = time.perf_counter()

    if classificador is None:
        classificador = classificar_intencao

    try:
        classificacao = classificador(mensagem)
        if not isinstance(classificacao, dict):
            raise ValueError("Classificacao invalida")
    except Exception:
        classificacao = {
            "intencao": "esclarecimento",
            "confianca": 0.0,
            "origem": "falha_classificacao",
            "tempo_ms": 0.0,
        }

    def consultar(texto: str):
        # Primeira tentativa: catalogo geral.
        resultado = consultar_catalogo(
            db,
            estabelecimento_id,
            texto,
        )

        if resultado is not None:
            return resultado

        # Segunda tentativa: produto especifico.
        return consultar_produto_especifico(
            db,
            estabelecimento_id,
            texto,
        )

    resposta = responder_intencao(
        mensagem,
        classificacao,
        consultar,
    )

    dados = dict(resposta.get("dados") or {})

    dados.update({
        "tempo_ms": round(
            (time.perf_counter() - inicio) * 1000,
            2,
        ),
        "intencao_identificada": classificacao.get(
            "intencao",
            "esclarecimento",
        ),
        "origem_classificacao": classificacao.get(
            "origem",
            "falha_classificacao",
        ),
        "compra_registrada": False,
    })

    return {
        **resposta,
        "dados": dados,
    }
