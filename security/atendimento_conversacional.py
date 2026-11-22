
import re
import unicodedata


def normalizar_mensagem(mensagem: str) -> str:
    texto = unicodedata.normalize(
        "NFKD",
        mensagem.strip().casefold()
    )

    texto = "".join(
        caractere for caractere in texto
        if not unicodedata.combining(caractere)
    )

    texto = re.sub(r"[^\w\s]", " ", texto)
    return " ".join(texto.split())


def responder_saudacao(mensagem: str) -> str | None:
    if not isinstance(mensagem, str):
        return None

    texto = normalizar_mensagem(mensagem)

    saudacoes = {
        "oi",
        "oii",
        "ola",
        "olaa",
        "opa",
        "bom dia",
        "boa tarde",
        "boa noite",
        "oi bom dia",
        "ola bom dia",
        "oi boa tarde",
        "ola boa tarde",
        "oi boa noite",
        "ola boa noite",
        "oi tudo bem",
        "ola tudo bem",
        "ola bom dia tudo bem",
    }

    if texto not in saudacoes:
        return None

    return (
        "Ola! Seja bem-vindo a nossa loja. "
        "Posso ajudar com precos e disponibilidade "
        "dos produtos. O que voce gostaria de saber?"
    )


def esclarecimento_triagem(dados) -> str | None:
    mensagem = (
        "Para continuar, informe o que deseja consultar "
        "ou, se quiser fazer um pedido, diga seu nome, "
        "os produtos e as quantidades desejadas."
    )

    if not isinstance(dados, dict):
        return mensagem

    if dados.get("erro"):
        return mensagem

    nome = dados.get("cliente_nome")
    itens = dados.get("itens")

    if not isinstance(nome, str) or not nome.strip():
        return mensagem

    if not isinstance(itens, list) or not itens:
        return mensagem

    return None
