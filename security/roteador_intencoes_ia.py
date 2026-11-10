import math

from agents.classificador_intencao import LIMIAR_CONFIANCA


def decidir_encaminhamento(classificacao: dict) -> dict:
    """
    Decide somente o destino logico da mensagem.

    Nao consulta banco, nao cria pedidos,
    nao executa compras e nao altera estoque.
    """

    padrao = {
        "destino": "solicitar_esclarecimento",
        "autoriza_compra": False,
        "motivo": "classificacao_nao_confiavel",
    }

    if not isinstance(classificacao, dict):
        return padrao.copy()

    intencao = classificacao.get("intencao")
    origem = classificacao.get("origem")
    confianca = classificacao.get("confianca")

    if origem != "agente":
        return {
            **padrao,
            "motivo": "origem_nao_aprovada",
        }

    if (
        isinstance(confianca, bool)
        or not isinstance(confianca, (int, float))
        or not math.isfinite(confianca)
        or not 0 <= confianca <= 1
        or confianca < LIMIAR_CONFIANCA
    ):
        return {
            **padrao,
            "motivo": "confianca_insuficiente",
        }

    if intencao == "consulta_catalogo":
        return {
            "destino": "consulta_catalogo",
            "autoriza_compra": False,
            "motivo": "consulta_identificada",
        }

    if intencao == "compra":
        return {
            "destino": "compra_pendente_confirmacao",
            "autoriza_compra": False,
            "motivo": "confirmacao_necessaria",
        }

    if intencao == "esclarecimento":
        return {
            "destino": "solicitar_esclarecimento",
            "autoriza_compra": False,
            "motivo": "informacoes_insuficientes",
        }

    return {
        **padrao,
        "motivo": "intencao_desconhecida",
    }
