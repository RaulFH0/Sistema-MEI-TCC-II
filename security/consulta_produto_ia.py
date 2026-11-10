import re
import unicodedata

from sqlalchemy.orm import Session

from database.models import Produto
from security.consulta_catalogo_ia import formatar_preco


PALAVRAS_IGNORADAS = frozenset({
    "a", "as", "o", "os", "um", "uma", "uns", "umas",
    "de", "do", "da", "dos", "das", "e", "em",
    "na", "no", "nas", "nos", "para", "por",
    "qual", "quais", "quanto", "custa", "custam",
    "preco", "precos", "valor", "valores",
    "tem", "tenho", "loja", "produto", "produtos",
    "disponivel", "disponiveis", "estoque",
    "saber", "gostaria", "quero", "consultar",
    "me", "informe", "informar",
})


def _tokens(texto: str) -> set[str]:
    texto = unicodedata.normalize(
        "NFKD", texto.casefold()
    )

    texto = "".join(
        caractere for caractere in texto
        if not unicodedata.combining(caractere)
    )

    palavras = re.findall(r"[a-z0-9]+", texto)

    return {
        palavra
        for palavra in palavras
        if (
            len(palavra) >= 3
            and palavra not in PALAVRAS_IGNORADAS
        )
    }


def consultar_produto_especifico(
    db: Session,
    estabelecimento_id: int,
    mensagem: str,
) -> dict | None:
    """
    Consulta produtos disponiveis de uma unica loja.

    Somente leitura. Nao registra pedidos.
    Nao altera quantidades nem valores.
    """

    if (
        type(estabelecimento_id) is not int
        or estabelecimento_id < 1
    ):
        raise ValueError("Estabelecimento invalido")

    if not isinstance(mensagem, str):
        raise ValueError("Mensagem invalida")

    termos = _tokens(mensagem)

    if not termos:
        return None

    produtos = (
        db.query(Produto)
        .filter(
            Produto.estabelecimento_id
            == estabelecimento_id,
            Produto.quantidade > 0,
        )
        .order_by(Produto.nome, Produto.id)
        .all()
    )

    encontrados = []

    for produto in produtos:
        nome_tokens = _tokens(produto.nome)

        if nome_tokens and nome_tokens.intersection(termos):
            encontrados.append(produto)

    if not encontrados:
        return None

    linhas = ["Encontrei estes produtos na loja:"]

    for produto in encontrados:
        linhas.append(
            "- "
            + produto.nome
            + ": "
            + formatar_preco(produto.preco)
            + " ("
            + str(produto.quantidade)
            + " em estoque)"
        )

    return {
        "resposta": "\n".join(linhas),
        "acao_executada": "consulta_catalogo",
        "sucesso": True,
        "dados": {
            "tipo": "consulta",
            "quantidade_produtos": len(encontrados),
        },
    }
