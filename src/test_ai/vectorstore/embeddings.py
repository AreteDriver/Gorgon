"""Embedding providers for vector stores."""

from __future__ import annotations

from typing import Any

from .base import EmbeddingProvider, VectorStoreError


class OpenAIEmbeddings(EmbeddingProvider):
    """OpenAI embeddings provider.

    Uses OpenAI's text-embedding models for high-quality embeddings.
    """

    MODELS = {
        "text-embedding-3-small": 1536,
        "text-embedding-3-large": 3072,
        "text-embedding-ada-002": 1536,
    }

    def __init__(
        self,
        model: str = "text-embedding-3-small",
        api_key: str | None = None,
        dimensions: int | None = None,
    ):
        """Initialize OpenAI embeddings.

        Args:
            model: Model name to use
            api_key: OpenAI API key (uses env var if not provided)
            dimensions: Optional dimension reduction (for v3 models)
        """
        try:
            from openai import OpenAI
        except ImportError:
            raise VectorStoreError("openai package not installed")

        self._model = model
        self._dimensions = dimensions

        # Determine actual dimension
        if dimensions:
            self._dim = dimensions
        else:
            self._dim = self.MODELS.get(model, 1536)

        if api_key:
            self._client = OpenAI(api_key=api_key)
        else:
            self._client = OpenAI()

    @property
    def dimension(self) -> int:
        return self._dim

    @property
    def model_name(self) -> str:
        return self._model

    def embed(self, text: str) -> list[float]:
        """Generate embedding for a single text."""
        kwargs: dict[str, Any] = {
            "model": self._model,
            "input": text,
        }
        if self._dimensions and "text-embedding-3" in self._model:
            kwargs["dimensions"] = self._dimensions

        response = self._client.embeddings.create(**kwargs)
        return response.data[0].embedding

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for multiple texts."""
        kwargs: dict[str, Any] = {
            "model": self._model,
            "input": texts,
        }
        if self._dimensions and "text-embedding-3" in self._model:
            kwargs["dimensions"] = self._dimensions

        response = self._client.embeddings.create(**kwargs)
        # Sort by index to ensure order is preserved
        sorted_data = sorted(response.data, key=lambda x: x.index)
        return [d.embedding for d in sorted_data]

    async def embed_async(self, text: str) -> list[float]:
        """Generate embedding asynchronously."""
        try:
            from openai import AsyncOpenAI
        except ImportError:
            return await super().embed_async(text)

        client = AsyncOpenAI()
        kwargs: dict[str, Any] = {
            "model": self._model,
            "input": text,
        }
        if self._dimensions and "text-embedding-3" in self._model:
            kwargs["dimensions"] = self._dimensions

        response = await client.embeddings.create(**kwargs)
        return response.data[0].embedding

    async def embed_batch_async(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings asynchronously."""
        try:
            from openai import AsyncOpenAI
        except ImportError:
            return await super().embed_batch_async(texts)

        client = AsyncOpenAI()
        kwargs: dict[str, Any] = {
            "model": self._model,
            "input": texts,
        }
        if self._dimensions and "text-embedding-3" in self._model:
            kwargs["dimensions"] = self._dimensions

        response = await client.embeddings.create(**kwargs)
        sorted_data = sorted(response.data, key=lambda x: x.index)
        return [d.embedding for d in sorted_data]


class SentenceTransformerEmbeddings(EmbeddingProvider):
    """Sentence Transformers embeddings (local, free).

    Uses the sentence-transformers library for local embedding generation.
    No API key required.
    """

    MODELS = {
        "all-MiniLM-L6-v2": 384,
        "all-mpnet-base-v2": 768,
        "paraphrase-MiniLM-L6-v2": 384,
        "multi-qa-MiniLM-L6-cos-v1": 384,
        "all-distilroberta-v1": 768,
        "multi-qa-mpnet-base-dot-v1": 768,
    }

    def __init__(
        self,
        model: str = "all-MiniLM-L6-v2",
        device: str | None = None,
    ):
        """Initialize Sentence Transformer embeddings.

        Args:
            model: Model name to use
            device: Device to use (cuda, cpu, etc.)
        """
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError:
            raise VectorStoreError(
                "sentence-transformers package not installed. "
                "Install with: pip install sentence-transformers"
            )

        self._model_name = model
        self._model = SentenceTransformer(model, device=device)
        self._dim = self.MODELS.get(
            model, self._model.get_sentence_embedding_dimension()
        )

    @property
    def dimension(self) -> int:
        return self._dim

    @property
    def model_name(self) -> str:
        return self._model_name

    def embed(self, text: str) -> list[float]:
        """Generate embedding for a single text."""
        embedding = self._model.encode(text, convert_to_numpy=True)
        return embedding.tolist()

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for multiple texts."""
        embeddings = self._model.encode(texts, convert_to_numpy=True)
        return [e.tolist() for e in embeddings]


class CohereEmbeddings(EmbeddingProvider):
    """Cohere embeddings provider."""

    MODELS = {
        "embed-english-v3.0": 1024,
        "embed-multilingual-v3.0": 1024,
        "embed-english-light-v3.0": 384,
        "embed-multilingual-light-v3.0": 384,
    }

    def __init__(
        self,
        model: str = "embed-english-v3.0",
        api_key: str | None = None,
        input_type: str = "search_document",
    ):
        """Initialize Cohere embeddings.

        Args:
            model: Model name to use
            api_key: Cohere API key
            input_type: Input type (search_document, search_query, classification, clustering)
        """
        try:
            import cohere
        except ImportError:
            raise VectorStoreError("cohere package not installed")

        self._model = model
        self._input_type = input_type
        self._dim = self.MODELS.get(model, 1024)

        if api_key:
            self._client = cohere.Client(api_key)
        else:
            self._client = cohere.Client()

    @property
    def dimension(self) -> int:
        return self._dim

    @property
    def model_name(self) -> str:
        return self._model

    def embed(self, text: str) -> list[float]:
        """Generate embedding for a single text."""
        response = self._client.embed(
            texts=[text],
            model=self._model,
            input_type=self._input_type,
        )
        return response.embeddings[0]

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for multiple texts."""
        response = self._client.embed(
            texts=texts,
            model=self._model,
            input_type=self._input_type,
        )
        return response.embeddings


class VoyageEmbeddings(EmbeddingProvider):
    """Voyage AI embeddings provider (high quality for code and retrieval)."""

    MODELS = {
        "voyage-3": 1024,
        "voyage-3-lite": 512,
        "voyage-code-3": 1024,
        "voyage-finance-2": 1024,
        "voyage-law-2": 1024,
    }

    def __init__(
        self,
        model: str = "voyage-3",
        api_key: str | None = None,
    ):
        """Initialize Voyage embeddings.

        Args:
            model: Model name to use
            api_key: Voyage API key
        """
        try:
            import voyageai
        except ImportError:
            raise VectorStoreError("voyageai package not installed")

        self._model = model
        self._dim = self.MODELS.get(model, 1024)

        if api_key:
            self._client = voyageai.Client(api_key=api_key)
        else:
            self._client = voyageai.Client()

    @property
    def dimension(self) -> int:
        return self._dim

    @property
    def model_name(self) -> str:
        return self._model

    def embed(self, text: str) -> list[float]:
        """Generate embedding for a single text."""
        result = self._client.embed([text], model=self._model)
        return result.embeddings[0]

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for multiple texts."""
        result = self._client.embed(texts, model=self._model)
        return result.embeddings


# Factory function
def get_embeddings(
    provider: str = "openai",
    model: str | None = None,
    **kwargs,
) -> EmbeddingProvider:
    """Get an embedding provider by name.

    Args:
        provider: Provider name (openai, sentence-transformers, cohere, voyage)
        model: Optional model override
        **kwargs: Provider-specific arguments

    Returns:
        EmbeddingProvider instance
    """
    providers = {
        "openai": (OpenAIEmbeddings, "text-embedding-3-small"),
        "sentence-transformers": (SentenceTransformerEmbeddings, "all-MiniLM-L6-v2"),
        "local": (SentenceTransformerEmbeddings, "all-MiniLM-L6-v2"),
        "cohere": (CohereEmbeddings, "embed-english-v3.0"),
        "voyage": (VoyageEmbeddings, "voyage-3"),
    }

    if provider not in providers:
        raise VectorStoreError(f"Unknown embedding provider: {provider}")

    cls, default_model = providers[provider]
    return cls(model=model or default_model, **kwargs)
