"""In-memory vector store implementation."""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

from .base import (
    VectorStore,
    Document,
    SearchResult,
    EmbeddingProvider,
    VectorStoreError,
)


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Calculate cosine similarity between two vectors."""
    dot_product = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot_product / (norm_a * norm_b)


def euclidean_distance(a: list[float], b: list[float]) -> float:
    """Calculate Euclidean distance between two vectors."""
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)))


class MemoryVectorStore(VectorStore):
    """In-memory vector store for development and small datasets.

    Stores documents and embeddings in memory with optional persistence to disk.
    Good for prototyping and small-scale applications (< 100k documents).

    Features:
        - No external dependencies
        - Optional persistence to JSON
        - Cosine similarity search
        - Metadata filtering
    """

    def __init__(
        self,
        embedding_provider: EmbeddingProvider,
        collection_name: str = "default",
        persist_path: str | Path | None = None,
    ):
        """Initialize in-memory vector store.

        Args:
            embedding_provider: Provider for generating embeddings
            collection_name: Name of the collection
            persist_path: Optional path for persistence
        """
        super().__init__(embedding_provider, collection_name)
        self._documents: dict[str, Document] = {}
        self._embeddings: dict[str, list[float]] = {}
        self._persist_path = Path(persist_path) if persist_path else None

        # Load from disk if path exists
        if self._persist_path and self._persist_path.exists():
            self._load()

    def add(self, documents: list[Document]) -> list[str]:
        """Add documents to the store."""
        if not documents:
            return []

        ids = []

        # Get texts that need embedding
        texts_to_embed = []
        docs_needing_embedding = []

        for doc in documents:
            if doc.embedding is None:
                texts_to_embed.append(doc.content)
                docs_needing_embedding.append(doc)

        # Batch embed texts without embeddings
        if texts_to_embed:
            embeddings = self.embedding_provider.embed_batch(texts_to_embed)
            for doc, embedding in zip(docs_needing_embedding, embeddings):
                doc.embedding = embedding

        # Store documents and embeddings
        for doc in documents:
            self._documents[doc.id] = doc
            self._embeddings[doc.id] = doc.embedding
            ids.append(doc.id)

        # Persist if configured
        if self._persist_path:
            self._save()

        return ids

    def search(
        self,
        query: str,
        k: int = 5,
        filter: dict[str, Any] | None = None,
    ) -> list[SearchResult]:
        """Search for similar documents."""
        if not self._documents:
            return []

        # Get query embedding
        query_embedding = self.embedding_provider.embed(query)

        # Calculate similarities
        results = []
        for doc_id, doc_embedding in self._embeddings.items():
            doc = self._documents[doc_id]

            # Apply metadata filter
            if filter and not self._matches_filter(doc.metadata, filter):
                continue

            similarity = cosine_similarity(query_embedding, doc_embedding)
            distance = euclidean_distance(query_embedding, doc_embedding)

            results.append(
                SearchResult(
                    document=doc,
                    score=similarity,
                    distance=distance,
                )
            )

        # Sort by similarity (descending) and return top k
        results.sort(key=lambda x: x.score, reverse=True)
        return results[:k]

    def delete(self, ids: list[str]) -> int:
        """Delete documents by ID."""
        deleted = 0
        for doc_id in ids:
            if doc_id in self._documents:
                del self._documents[doc_id]
                del self._embeddings[doc_id]
                deleted += 1

        if deleted > 0 and self._persist_path:
            self._save()

        return deleted

    def get(self, ids: list[str]) -> list[Document]:
        """Get documents by ID."""
        return [self._documents[doc_id] for doc_id in ids if doc_id in self._documents]

    def count(self) -> int:
        """Get the number of documents."""
        return len(self._documents)

    def clear(self) -> int:
        """Clear all documents."""
        count = len(self._documents)
        self._documents.clear()
        self._embeddings.clear()

        if self._persist_path:
            self._save()

        return count

    def _matches_filter(self, metadata: dict, filter: dict) -> bool:
        """Check if metadata matches filter criteria."""
        for key, value in filter.items():
            if key not in metadata:
                return False

            if isinstance(value, dict):
                # Handle operators
                for op, op_value in value.items():
                    meta_value = metadata[key]
                    if op == "$eq" and meta_value != op_value:
                        return False
                    elif op == "$ne" and meta_value == op_value:
                        return False
                    elif op == "$gt" and not (meta_value > op_value):
                        return False
                    elif op == "$gte" and not (meta_value >= op_value):
                        return False
                    elif op == "$lt" and not (meta_value < op_value):
                        return False
                    elif op == "$lte" and not (meta_value <= op_value):
                        return False
                    elif op == "$in" and meta_value not in op_value:
                        return False
                    elif op == "$nin" and meta_value in op_value:
                        return False
            else:
                # Direct equality
                if metadata[key] != value:
                    return False

        return True

    def persist(self) -> None:
        """Persist to disk."""
        if self._persist_path:
            self._save()

    def _save(self) -> None:
        """Save to disk."""
        if not self._persist_path:
            return

        data = {
            "collection_name": self.collection_name,
            "documents": {
                doc_id: {
                    "id": doc.id,
                    "content": doc.content,
                    "metadata": doc.metadata,
                }
                for doc_id, doc in self._documents.items()
            },
            "embeddings": self._embeddings,
        }

        self._persist_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self._persist_path, "w") as f:
            json.dump(data, f)

    def _load(self) -> None:
        """Load from disk."""
        if not self._persist_path or not self._persist_path.exists():
            return

        try:
            with open(self._persist_path) as f:
                data = json.load(f)

            for doc_id, doc_data in data.get("documents", {}).items():
                self._documents[doc_id] = Document(
                    id=doc_data["id"],
                    content=doc_data["content"],
                    metadata=doc_data.get("metadata", {}),
                )

            self._embeddings = data.get("embeddings", {})

        except Exception as e:
            raise VectorStoreError(f"Failed to load from {self._persist_path}: {e}")

    def get_stats(self) -> dict:
        """Get store statistics."""
        return {
            "collection_name": self.collection_name,
            "document_count": len(self._documents),
            "embedding_dimension": self.embedding_provider.dimension,
            "embedding_model": self.embedding_provider.model_name,
            "persist_path": str(self._persist_path) if self._persist_path else None,
        }
