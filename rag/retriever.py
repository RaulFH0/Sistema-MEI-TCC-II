
import chromadb

from sentence_transformers import SentenceTransformer

from rag.loader import (
    CHROMA_PATH,
    COLLECTION_NAME,
    MODEL_NAME,
)


# ============================================================
# CONFIGURACAO RAG
# ============================================================

_client = None
_collection = None
_modelo = None

CONTEXTO_VAZIO = (
    "Nenhuma informacao relevante encontrada "
    "na base de conhecimento."
)


def _inicializar():
    global _client, _collection, _modelo

    if _collection is None:
        cliente = chromadb.PersistentClient(
            path=CHROMA_PATH
        )

        colecao = cliente.get_or_create_collection(
            name=COLLECTION_NAME
        )

        modelo = SentenceTransformer(
            MODEL_NAME
        )

        _client = cliente
        _collection = colecao
        _modelo = modelo


# ============================================================
# RECUPERACAO ISOLADA POR ESTABELECIMENTO
# ============================================================

def buscar_contexto(
    query: str,
    n_resultados: int = 3,
    *,
    estabelecimento_id: int = 1,
) -> str:
    """
    Recupera conhecimento exclusivo do estabelecimento.

    Regras:
    - Todas as lojas usam o filtro estabelecimento_id.
    - Documentos sem identificacao nao sao recuperados.
    - Uma loja nao recebe documentos de outra.
    - A Loja Inicial utiliza estabelecimento_id=1.

    O identificador deve ser validado pelo backend.
    Esta funcao nao realiza autenticacao.
    """

    # --------------------------------------------------------
    # VALIDACAO DOS PARAMETROS
    # --------------------------------------------------------

    if (
        type(estabelecimento_id) is not int
        or estabelecimento_id < 1
    ):
        raise ValueError(
            "Identificador do estabelecimento invalido."
        )

    if not isinstance(query, str) or not query.strip():
        raise ValueError(
            "Consulta RAG invalida."
        )

    if (
        type(n_resultados) is not int
        or n_resultados < 1
    ):
        raise ValueError(
            "Quantidade de resultados invalida."
        )

    # --------------------------------------------------------
    # INICIALIZACAO DA BASE VETORIAL
    # --------------------------------------------------------

    _inicializar()

    if _collection.count() == 0:
        return CONTEXTO_VAZIO

    filtro = {
        "estabelecimento_id": estabelecimento_id
    }

    # --------------------------------------------------------
    # VERIFICAR SE A LOJA POSSUI DOCUMENTOS
    # --------------------------------------------------------

    documentos_loja = _collection.get(
        where=filtro,
        include=["metadatas"],
    )

    quantidade_documentos = len(
        documentos_loja.get("ids", [])
    )

    if quantidade_documentos == 0:
        return CONTEXTO_VAZIO

    # --------------------------------------------------------
    # GERAR EMBEDDING DA CONSULTA
    # --------------------------------------------------------

    embedding_query = _modelo.encode(
        [query.strip()]
    ).tolist()

    # --------------------------------------------------------
    # BUSCA SEMANTICA COM ISOLAMENTO MULTI-MEI
    # --------------------------------------------------------

    resultados = _collection.query(
        query_embeddings=embedding_query,
        n_results=min(
            n_resultados,
            quantidade_documentos
        ),
        where=filtro,
    )

    documentos = resultados.get("documents") or []

    if not documentos or not documentos[0]:
        return CONTEXTO_VAZIO

    return "\n\n".join(
        documento
        for documento in documentos[0]
        if documento
    ) or CONTEXTO_VAZIO
