"""Vector Store Integration for RAG.

Provides a unified interface for vector databases to enable
Retrieval-Augmented Generation (RAG) workflows.
"""

from .base import (
    VectorStore,
    Document,
    SearchResult,
    EmbeddingProvider,
    VectorStoreError,
)
from .memory_store import MemoryVectorStore
from .chroma_store import ChromaVectorStore
from .embeddings import (
    OpenAIEmbeddings,
    SentenceTransformerEmbeddings,
    get_embeddings,
)

__all__ = [
    # Base classes
    "VectorStore",
    "Document",
    "SearchResult",
    "EmbeddingProvider",
    "VectorStoreError",
    # Implementations
    "MemoryVectorStore",
    "ChromaVectorStore",
    # Embeddings
    "OpenAIEmbeddings",
    "SentenceTransformerEmbeddings",
    "get_embeddings",
]
