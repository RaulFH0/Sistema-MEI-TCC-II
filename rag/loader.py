import chromadb
from sentence_transformers import SentenceTransformer
from pathlib import Path

# ============================================================
# CONFIGURAÇÃO DO BANCO VETORIAL
# ============================================================
CHROMA_PATH = "./chroma_db"
COLLECTION_NAME = "conhecimento_mei"
MODEL_NAME = "all-MiniLM-L6-v2"  # modelo leve e rápido

def carregar_base_conhecimento():
    """
    Lê os arquivos da pasta data/conhecimento e
    indexa no ChromaDB para busca semântica.
    """
    print("Inicializando base de conhecimento...")

    # Inicializa o ChromaDB
    client = chromadb.PersistentClient(path=CHROMA_PATH)

    # Cria ou recupera a coleção
    collection = client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"}
    )

    # Se já tem documentos, não recarrega
    if collection.count() > 0:
        print(f"Base já carregada com {collection.count()} documentos.")
        return collection

    # Carrega o modelo de embeddings
    modelo = SentenceTransformer(MODEL_NAME)

    # Lê todos os arquivos da pasta conhecimento
    pasta = Path("./data/conhecimento")
    documentos = []
    ids = []
    metadados = []

    for i, arquivo in enumerate(pasta.glob("*.txt")):
        texto = arquivo.read_text(encoding="utf-8")

        # Divide em chunks de ~200 caracteres para melhor recuperação
        chunks = dividir_em_chunks(texto, tamanho=300, sobreposicao=50)

        for j, chunk in enumerate(chunks):
            documentos.append(chunk)
            ids.append(f"{arquivo.stem}_{j}")
            metadados.append({"fonte": arquivo.name, "chunk": j})

    # Gera embeddings e indexa
    embeddings = modelo.encode(documentos).tolist()
    collection.add(
        documents=documentos,
        embeddings=embeddings,
        ids=ids,
        metadatas=metadados
    )

    print(f"Base carregada com {len(documentos)} chunks de {pasta}.")
    return collection


def dividir_em_chunks(texto: str, tamanho: int = 300, sobreposicao: int = 50):
    """Divide texto em chunks com sobreposição."""
    chunks = []
    inicio = 0
    while inicio < len(texto):
        fim = inicio + tamanho
        chunk = texto[inicio:fim]
        if chunk.strip():
            chunks.append(chunk)
        inicio += tamanho - sobreposicao
    return chunks