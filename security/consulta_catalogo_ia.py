import re
import unicodedata
from decimal import Decimal, InvalidOperation

from sqlalchemy.orm import Session

from database.models import Produto


def normalizar(texto: str) -> str:
    texto = unicodedata.normalize("NFKD", texto.lower())
    return "".join(
        caractere for caractere in texto
        if not unicodedata.combining(caractere)
    )


def pergunta_catalogo(mensagem: str) -> bool:
    texto = normalizar(mensagem)

    # Esta primeira versao reconhece apenas consultas
    # explicitamente informativas sobre o catalogo.
    # Mensagens com intencao de compra nao sao interceptadas.
    termos_compra = (
        "quero comprar",
        "gostaria de comprar",
        "vou comprar",
        "confirmar pedido",
        "fechar pedido",
        "adicionar ao carrinho",
        "fazer pedido",
        "realizar pedido",
    )

    if any(termo in texto for termo in termos_compra):
        return False

    consultas = (
        "quais produtos",
        "listar produtos",
        "liste os produtos",
        "mostre os produtos",
        "mostrar produtos",
        "produtos disponiveis",
        "catalogo de produtos",
        "o que tem na loja",
    )

    return any(termo in texto for termo in consultas)


def formatar_preco(valor) -> str:
    try:
        numero = Decimal(str(valor)).quantize(
            Decimal("0.01")
        )
    except (InvalidOperation, ValueError, TypeError):
        raise ValueError(
            "Preco invalido no catalogo."
        )

    if not numero.is_finite() or numero < 0:
        raise ValueError(
            "Preco invalido no catalogo."
        )

    return (
        "R$ " + f"{numero:.2f}".replace(".", ",")
    )


def consultar_catalogo(
    db: Session,
    estabelecimento_id: int,
    mensagem: str,
):
    if not pergunta_catalogo(mensagem):
        return None

    if (
        type(estabelecimento_id) is not int
        or estabelecimento_id < 1
    ):
        raise ValueError(
            "Estabelecimento invalido."
        )

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

    if not produtos:
        resposta = (
            "No momento, esta loja nao possui "
            "produtos disponiveis."
        )
    else:
        linhas = [
            "Produtos disponiveis nesta loja:"
        ]

        for produto in produtos:
            linhas.append(
                "- "
                + produto.nome
                + ": "
                + formatar_preco(produto.preco)
                + " ("
                + str(produto.quantidade)
                + " em estoque)"
            )

        resposta = "\n".join(linhas)

    return {
        "resposta": resposta,
        "acao_executada": "consulta_catalogo",
        "sucesso": True,
        "dados": {
            "tipo": "consulta",
            "quantidade_produtos": len(produtos),
        },
    }
