from pathlib import Path
from functools import lru_cache

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings
from langchain_chroma import Chroma
from langchain.tools import tool


# ============================================================
# RUTAS
# ============================================================

BASE_DIR = Path(__file__).resolve().parents[1]

DOCUMENTOS_DIR = BASE_DIR / "documentos_negocio"
CHROMA_DIR = BASE_DIR / "chroma_db"

RUTA_NEGOCIO = DOCUMENTOS_DIR / "negocio.txt"


# ============================================================
# CREAR RETRIEVER
# ============================================================

@lru_cache(maxsize=1)
def obtener_retriever():
    """
    Carga el documento del negocio, crea los embeddings
    y devuelve el retriever de Chroma.

    El resultado se guarda en caché para no reconstruir
    el retriever cada vez que se utiliza.
    """

    with open(RUTA_NEGOCIO, "r", encoding="utf-8") as archivo:
        texto_negocio = archivo.read()

    documento = Document(
        page_content=texto_negocio
    )

    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=500,
        chunk_overlap=50,
    )

    documentos = text_splitter.split_documents(
        [documento]
    )

    embeddings = OpenAIEmbeddings()

    vectorstore = Chroma(
        collection_name="studio_alba",
        embedding_function=embeddings,
        persist_directory=str(CHROMA_DIR),
    )

    # Si la colección está vacía, añadimos los documentos.
    if vectorstore._collection.count() == 0:
        vectorstore.add_documents(documentos)

    return vectorstore.as_retriever()


# ============================================================
# TOOL DEL RAG
# ============================================================

@tool
def buscar_informacion_negocio(pregunta: str) -> str:
    """
    Busca información general y pública sobre Studio Alba
    utilizando los documentos del negocio.
    """

    retriever = obtener_retriever()

    documentos = retriever.invoke(pregunta)

    if not documentos:
        return "No se ha encontrado información relevante."

    return "\n\n".join(
        documento.page_content
        for documento in documentos
    )