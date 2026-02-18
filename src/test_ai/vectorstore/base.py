"""Base classes for vector store abstraction."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any
import uuid


class VectorStoreError(Exception):
    """Base exception for vector store errors."""

    pass


@dataclass
class Document:
    """A document with content and metadata for vector storage.

    Attributes:
        content: The text content of the document
        metadata: Additional metadata (source, timestamp, etc.)
        id: Unique document identifier (auto-generated if not provided)
        embedding: Pre-computed embedding vector (optional)
    """

    content: str
    metadata: dict[str, Any] = field(default_factory=dict)
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    embedding: list[float] | None = None

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "content": self.content,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Document":
        """Create from dictionary."""
        return cls(
            id=data.get("id", str(uuid.uuid4())),
            content=data["content"],
            metadata=data.get("metadata", {}),
            embedding=data.get("embedding"),
        )


@dataclass
class SearchResult:
    """A search result from vector similarity search.

    Attributes:
        document: The matched document
        score: Similarity score (higher is more similar)
        distance: Distance metric (lower is more similar)
    """

    document: Document
    score: float
    distance: float | None = None

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "document": self.document.to_dict(),
            "score": self.score,
            "distance": self.distance,
        }


class EmbeddingProvider(ABC):
    """Abstract base class for embedding providers."""

    @property
    @abstractmethod
    def dimension(self) -> int:
        """Return the embedding dimension."""
        pass

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Return the model name."""
        pass

    @abstractmethod
    def embed(self, text: str) -> list[float]:
        """Generate embedding for a single text.

        Args:
            text: Text to embed

        Returns:
            Embedding vector
        """
        pass

    @abstractmethod
    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for multiple texts.

        Args:
            texts: List of texts to embed

        Returns:
            List of embedding vectors
        """
        pass

    async def embed_async(self, text: str) -> list[float]:
        """Generate embedding asynchronously.

        Default implementation wraps sync method.
        """
        import asyncio

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.embed, text)

    async def embed_batch_async(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings asynchronously.

        Default implementation wraps sync method.
        """
        import asyncio

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.embed_batch, texts)


class VectorStore(ABC):
    """Abstract base class for vector stores.

    Provides a unified interface for vector databases to enable
    similarity search and RAG workflows.
    """

    def __init__(
        self,
        embedding_provider: EmbeddingProvider,
        collection_name: str = "default",
    ):
        """Initialize vector store.

        Args:
            embedding_provider: Provider for generating embeddings
            collection_name: Name of the collection/index
        """
        self.embedding_provider = embedding_provider
        self.collection_name = collection_name

    @abstractmethod
    def add(self, documents: list[Document]) -> list[str]:
        """Add documents to the vector store.

        Args:
            documents: Documents to add

        Returns:
            List of document IDs
        """
        pass

    @abstractmethod
    def search(
        self,
        query: str,
        k: int = 5,
        filter: dict[str, Any] | None = None,
    ) -> list[SearchResult]:
        """Search for similar documents.

        Args:
            query: Search query text
            k: Number of results to return
            filter: Optional metadata filter

        Returns:
            List of search results
        """
        pass

    @abstractmethod
    def delete(self, ids: list[str]) -> int:
        """Delete documents by ID.

        Args:
            ids: Document IDs to delete

        Returns:
            Number of documents deleted
        """
        pass

    @abstractmethod
    def get(self, ids: list[str]) -> list[Document]:
        """Get documents by ID.

        Args:
            ids: Document IDs to retrieve

        Returns:
            List of documents
        """
        pass

    @abstractmethod
    def count(self) -> int:
        """Get the number of documents in the store.

        Returns:
            Document count
        """
        pass

    def add_texts(
        self,
        texts: list[str],
        metadatas: list[dict[str, Any]] | None = None,
        ids: list[str] | None = None,
    ) -> list[str]:
        """Convenience method to add texts directly.

        Args:
            texts: Text content to add
            metadatas: Optional metadata for each text
            ids: Optional IDs for each text

        Returns:
            List of document IDs
        """
        documents = []
        for i, text in enumerate(texts):
            doc = Document(
                content=text,
                metadata=metadatas[i] if metadatas else {},
                id=ids[i] if ids else str(uuid.uuid4()),
            )
            documents.append(doc)
        return self.add(documents)

    def similarity_search(
        self,
        query: str,
        k: int = 5,
        filter: dict[str, Any] | None = None,
    ) -> list[Document]:
        """Search and return just the documents.

        Args:
            query: Search query text
            k: Number of results to return
            filter: Optional metadata filter

        Returns:
            List of similar documents
        """
        results = self.search(query, k=k, filter=filter)
        return [r.document for r in results]

    def similarity_search_with_score(
        self,
        query: str,
        k: int = 5,
        filter: dict[str, Any] | None = None,
    ) -> list[tuple[Document, float]]:
        """Search and return documents with scores.

        Args:
            query: Search query text
            k: Number of results to return
            filter: Optional metadata filter

        Returns:
            List of (document, score) tuples
        """
        results = self.search(query, k=k, filter=filter)
        return [(r.document, r.score) for r in results]

    async def add_async(self, documents: list[Document]) -> list[str]:
        """Add documents asynchronously.

        Default implementation wraps sync method.
        """
        import asyncio

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.add, documents)

    async def search_async(
        self,
        query: str,
        k: int = 5,
        filter: dict[str, Any] | None = None,
    ) -> list[SearchResult]:
        """Search asynchronously.

        Default implementation wraps sync method.
        """
        import asyncio

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, lambda: self.search(query, k=k, filter=filter)
        )

    @abstractmethod
    def clear(self) -> int:
        """Clear all documents from the store.

        Returns:
            Number of documents deleted
        """
        pass

    def persist(self) -> None:
        """Persist the store to disk (if applicable)."""
        pass

    def health_check(self) -> bool:
        """Check if the store is healthy.

        Returns:
            True if healthy
        """
        try:
            self.count()
            return True
        except VectorStoreError:
            return False
