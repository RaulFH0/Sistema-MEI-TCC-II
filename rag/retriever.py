import chromadb
from sentence_transformers import SentenceTransformer
from rag.loader import CHROMA_PATH, COLLECTION_NAME, MODEL_NAME

# ============================================================
# BUSCA SEMÂNTICA
# ============================================================
_client = None
_collection = None
_modelo = None

def _inicializar():
    global _client, _collection, _modelo
    if _collection is None:
        _client = chromadb.PersistentClient(path=CHROMA_PATH)
        _collection = _client.get_or_create_collection(name=COLLECTION_NAME)
        _modelo = SentenceTransformer(MODEL_NAME)

def buscar_contexto(query: str, n_resultados: int = 3) -> str:
    """
    Busca os trechos mais relevantes da base de conhecimento
    para a query do usuário.
    Retorna uma string com o contexto encontrado.
    """
    _inicializar()

    # Gera embedding da query
    embedding_query = _modelo.encode([query]).tolist()

    # Busca os chunks mais similares
    resultados = _collection.query(
        query_embeddings=embedding_query,
        n_results=n_resultados
    )

    if not resultados["documents"] or not resultados["documents"][0]:
        return "Nenhuma informação relevante encontrada na base de conhecimento."

    # Monta o contexto
    contexto = "\n\n".join(resultados["documents"][0])
    return contexto