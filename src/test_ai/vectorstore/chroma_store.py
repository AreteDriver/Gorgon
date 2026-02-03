"""ChromaDB vector store implementation."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .base import (
    VectorStore,
    Document,
    SearchResult,
    EmbeddingProvider,
    VectorStoreError,
)


class ChromaVectorStore(VectorStore):
    """ChromaDB vector store for production use.

    ChromaDB is a high-performance, open-source vector database that supports:
        - Persistent storage
        - Metadata filtering
        - Multiple distance metrics
        - Built-in embedding functions

    Requires: pip install chromadb
    """

    def __init__(
        self,
        embedding_provider: EmbeddingProvider,
        collection_name: str = "default",
        persist_directory: str | Path | None = None,
        host: str | None = None,
        port: int | None = None,
    ):
        """Initialize ChromaDB vector store.

        Args:
            embedding_provider: Provider for generating embeddings
            collection_name: Name of the collection
            persist_directory: Path for persistent storage (local mode)
            host: ChromaDB server host (client mode)
            port: ChromaDB server port (client mode)
        """
        super().__init__(embedding_provider, collection_name)

        try:
            import chromadb
            from chromadb.config import Settings
        except ImportError:
            raise VectorStoreError(
                "chromadb package not installed. Install with: pip install chromadb"
            )

        # Initialize client based on mode
        if host and port:
            # Client mode - connect to ChromaDB server
            self._client = chromadb.HttpClient(host=host, port=port)
        elif persist_directory:
            # Persistent local mode
            self._client = chromadb.PersistentClient(
                path=str(persist_directory),
                settings=Settings(anonymized_telemetry=False),
            )
        else:
            # In-memory mode
            self._client = chromadb.Client(
                settings=Settings(anonymized_telemetry=False),
            )

        # Create embedding function wrapper
        self._embedding_function = ChromaEmbeddingFunction(embedding_provider)

        # Get or create collection
        self._collection = self._client.get_or_create_collection(
            name=collection_name,
            embedding_function=self._embedding_function,
            metadata={"hnsw:space": "cosine"},
        )

    def add(self, documents: list[Document]) -> list[str]:
        """Add documents to the store."""
        if not documents:
            return []

        ids = [doc.id for doc in documents]
        contents = [doc.content for doc in documents]
        metadatas = [doc.metadata for doc in documents]

        # Clean metadata (ChromaDB doesn't support nested dicts or None values)
        clean_metadatas = []
        for meta in metadatas:
            clean_meta = {}
            for k, v in meta.items():
                if v is not None and not isinstance(v, (dict, list)):
                    clean_meta[k] = v
                elif isinstance(v, list) and all(
                    isinstance(i, (str, int, float, bool)) for i in v
                ):
                    clean_meta[k] = v
            clean_metadatas.append(clean_meta)

        # Add to collection (embeddings generated automatically)
        self._collection.add(
            ids=ids,
            documents=contents,
            metadatas=clean_metadatas,
        )

        return ids

    def search(
        self,
        query: str,
        k: int = 5,
        filter: dict[str, Any] | None = None,
    ) -> list[SearchResult]:
        """Search for similar documents."""
        # Convert filter to ChromaDB where clause
        where = self._convert_filter(filter) if filter else None

        results = self._collection.query(
            query_texts=[query],
            n_results=k,
            where=where,
            include=["documents", "metadatas", "distances"],
        )

        search_results = []
        if results["ids"] and results["ids"][0]:
            for i, doc_id in enumerate(results["ids"][0]):
                content = results["documents"][0][i] if results["documents"] else ""
                metadata = results["metadatas"][0][i] if results["metadatas"] else {}
                distance = results["distances"][0][i] if results["distances"] else 0

                # Convert distance to similarity score (cosine)
                # ChromaDB returns squared L2 distance for cosine, so:
                # similarity = 1 - distance for cosine space
                score = 1 - distance

                doc = Document(
                    id=doc_id,
                    content=content,
                    metadata=metadata,
                )
                search_results.append(
                    SearchResult(
                        document=doc,
                        score=score,
                        distance=distance,
                    )
                )

        return search_results

    def delete(self, ids: list[str]) -> int:
        """Delete documents by ID."""
        # Get existing IDs to count deletions
        existing = self._collection.get(ids=ids)
        count = len(existing["ids"]) if existing["ids"] else 0

        if count > 0:
            self._collection.delete(ids=ids)

        return count

    def get(self, ids: list[str]) -> list[Document]:
        """Get documents by ID."""
        results = self._collection.get(
            ids=ids,
            include=["documents", "metadatas"],
        )

        documents = []
        if results["ids"]:
            for i, doc_id in enumerate(results["ids"]):
                content = results["documents"][i] if results["documents"] else ""
                metadata = results["metadatas"][i] if results["metadatas"] else {}
                documents.append(
                    Document(
                        id=doc_id,
                        content=content,
                        metadata=metadata,
                    )
                )

        return documents

    def count(self) -> int:
        """Get the number of documents."""
        return self._collection.count()

    def clear(self) -> int:
        """Clear all documents."""
        count = self.count()
        # Delete and recreate collection
        self._client.delete_collection(self.collection_name)
        self._collection = self._client.get_or_create_collection(
            name=self.collection_name,
            embedding_function=self._embedding_function,
            metadata={"hnsw:space": "cosine"},
        )
        return count

    def _convert_filter(self, filter: dict[str, Any]) -> dict:
        """Convert filter to ChromaDB where clause format."""
        where = {}

        for key, value in filter.items():
            if isinstance(value, dict):
                # Handle operators
                for op, op_value in value.items():
                    chroma_op = {
                        "$eq": "$eq",
                        "$ne": "$ne",
                        "$gt": "$gt",
                        "$gte": "$gte",
                        "$lt": "$lt",
                        "$lte": "$lte",
                        "$in": "$in",
                        "$nin": "$nin",
                    }.get(op)
                    if chroma_op:
                        where[key] = {chroma_op: op_value}
            else:
                # Direct equality
                where[key] = {"$eq": value}

        return where

    def update_metadata(self, doc_id: str, metadata: dict[str, Any]) -> bool:
        """Update document metadata.

        Args:
            doc_id: Document ID
            metadata: New metadata to merge

        Returns:
            True if successful
        """
        try:
            # Get existing document
            existing = self._collection.get(ids=[doc_id], include=["metadatas"])
            if not existing["ids"]:
                return False

            # Merge metadata
            current_meta = existing["metadatas"][0] if existing["metadatas"] else {}
            updated_meta = {**current_meta, **metadata}

            # Clean metadata
            clean_meta = {}
            for k, v in updated_meta.items():
                if v is not None and not isinstance(v, (dict, list)):
                    clean_meta[k] = v

            self._collection.update(ids=[doc_id], metadatas=[clean_meta])
            return True
        except Exception:
            return False

    def get_stats(self) -> dict:
        """Get store statistics."""
        return {
            "collection_name": self.collection_name,
            "document_count": self.count(),
            "embedding_dimension": self.embedding_provider.dimension,
            "embedding_model": self.embedding_provider.model_name,
        }


class ChromaEmbeddingFunction:
    """Wrapper to make our EmbeddingProvider compatible with ChromaDB."""

    def __init__(self, provider: EmbeddingProvider):
        self._provider = provider

    def __call__(self, input: list[str]) -> list[list[float]]:
        """Generate embeddings for ChromaDB."""
        return self._provider.embed_batch(input)
