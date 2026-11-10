from collections.abc import Callable

from security.roteador_intencoes_ia import (
    decidir_encaminhamento,
)


def responder_intencao(
    mensagem: str,
    classificacao: dict,
    consultar: Callable[[str], dict | None],
) -> dict:
    """
    Gera a resposta ao cliente sem registrar compras.

    O callback consultar deve executar somente
    leitura de dados do estabelecimento autorizado.

    A funcao nao invoca o orquestrador comercial.
    """

    decisao = decidir_encaminhamento(classificacao)
    destino = decisao["destino"]

    if destino == "consulta_catalogo":
        consulta = consultar(mensagem)

        if consulta is not None:
            if (
                not isinstance(consulta, dict)
                or consulta.get("sucesso") is not True
                or consulta.get("acao_executada")
                != "consulta_catalogo"
                or not isinstance(
                    consulta.get("resposta"), str
                )
                or not consulta["resposta"].strip()
            ):
                raise ValueError(
                    "Resposta de consulta invalida."
                )

            return consulta

        return {
            "resposta": (
                "Posso consultar os produtos da loja. "
                "Informe qual produto deseja conhecer "
                "ou solicite a lista de produtos."
            ),
            "acao_executada": "solicitar_esclarecimento",
            "sucesso": True,
            "dados": {
                "tipo": "esclarecimento",
                "compra_registrada": False,
            },
        }

    if destino == "compra_pendente_confirmacao":
        return {
            "resposta": (
                "Entendi que voce deseja comprar. "
                "Nenhuma compra foi registrada. "
                "Informe o produto e a quantidade "
                "desejada para preparar sua solicitacao. "
                "A confirmacao da compra sera feita "
                "em uma etapa separada."
            ),
            "acao_executada": (
                "compra_pendente_confirmacao"
            ),
            "sucesso": True,
            "dados": {
                "tipo": "intencao_compra",
                "compra_registrada": False,
            },
        }

    return {
        "resposta": (
            "Como posso ajudar? Voce pode perguntar "
            "sobre produtos e precos ou informar "
            "o que deseja comprar."
        ),
        "acao_executada": "solicitar_esclarecimento",
        "sucesso": True,
        "dados": {
            "tipo": "esclarecimento",
            "compra_registrada": False,
        },
    }
