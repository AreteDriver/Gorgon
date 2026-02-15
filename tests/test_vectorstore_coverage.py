"""Coverage tests for ChromaVectorStore and embedding providers.

Covers:
- ChromaVectorStore: __init__ (local/persistent/http), add, search, delete,
  get, count, clear, get_stats, _convert_filter, update_metadata,
  ChromaEmbeddingFunction.__call__
- OpenAIEmbeddings: init, properties, embed, embed_batch, async variants,
  dimension reduction
- SentenceTransformerEmbeddings: async method fallbacks
- CohereEmbeddings: embed, embed_batch
- VoyageEmbeddings: embed, embed_batch
- get_embeddings factory: all provider selections

All external dependencies (chromadb, openai, sentence_transformers, cohere,
voyageai) are mocked at the sys.modules level.
"""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Shared mock infrastructure
# ---------------------------------------------------------------------------

# Build mock modules for external deps BEFORE importing the target modules.
# Each mock module needs the classes/functions that the source code imports.


def _make_mock_chromadb():
    """Create a mock chromadb module with Settings."""
    mock = MagicMock()
    mock.config.Settings = MagicMock(return_value=MagicMock())
    return mock


def _make_mock_openai():
    """Create a mock openai module."""
    mock = MagicMock()
    return mock


def _make_mock_sentence_transformers():
    """Create a mock sentence_transformers module."""
    mock = MagicMock()
    return mock


def _make_mock_cohere():
    """Create a mock cohere module."""
    mock = MagicMock()
    return mock


def _make_mock_voyageai():
    """Create a mock voyageai module."""
    mock = MagicMock()
    return mock


# ---------------------------------------------------------------------------
# Import base types (always available, no external deps)
# ---------------------------------------------------------------------------

from test_ai.vectorstore.base import (  # noqa: E402
    Document,
    EmbeddingProvider,
    SearchResult,
    VectorStoreError,
)


# ---------------------------------------------------------------------------
# Helper: FakeEmbeddingProvider
# ---------------------------------------------------------------------------


class FakeEmbeddingProvider(EmbeddingProvider):
    """Deterministic embedding provider for Chroma tests."""

    def __init__(self, dim: int = 4):
        self._dim = dim

    @property
    def dimension(self) -> int:
        return self._dim

    @property
    def model_name(self) -> str:
        return "fake-model"

    def embed(self, text: str) -> list[float]:
        return [0.1] * self._dim

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        return [self.embed(t) for t in texts]


# ===========================================================================
# ChromaVectorStore tests
# ===========================================================================


class TestChromaVectorStoreInit:
    """Test ChromaVectorStore __init__ in all three client modes."""

    def test_import_error_when_chromadb_missing(self):
        """Raises VectorStoreError when chromadb is not installed."""
        with patch.dict("sys.modules", {"chromadb": None, "chromadb.config": None}):
            # Need to reload to pick up the patched sys.modules
            from test_ai.vectorstore import chroma_store

            with pytest.raises(VectorStoreError, match="chromadb"):
                chroma_store.ChromaVectorStore(
                    embedding_provider=FakeEmbeddingProvider()
                )

    def test_in_memory_client(self):
        """Default init creates an in-memory client."""
        mock_chromadb = _make_mock_chromadb()
        mock_collection = MagicMock()
        mock_chromadb.Client.return_value.get_or_create_collection.return_value = (
            mock_collection
        )

        with patch.dict(
            "sys.modules",
            {"chromadb": mock_chromadb, "chromadb.config": mock_chromadb.config},
        ):
            from test_ai.vectorstore.chroma_store import ChromaVectorStore

            provider = FakeEmbeddingProvider()
            store = ChromaVectorStore(embedding_provider=provider)

            mock_chromadb.Client.assert_called_once()
            assert store._collection is mock_collection

    def test_persistent_client(self, tmp_path):
        """Init with persist_directory creates PersistentClient."""
        mock_chromadb = _make_mock_chromadb()
        mock_collection = MagicMock()
        mock_chromadb.PersistentClient.return_value.get_or_create_collection.return_value = mock_collection

        with patch.dict(
            "sys.modules",
            {"chromadb": mock_chromadb, "chromadb.config": mock_chromadb.config},
        ):
            from test_ai.vectorstore.chroma_store import ChromaVectorStore

            provider = FakeEmbeddingProvider()
            store = ChromaVectorStore(
                embedding_provider=provider,
                persist_directory=str(tmp_path / "chroma"),
            )

            mock_chromadb.PersistentClient.assert_called_once()
            assert store._collection is mock_collection

    def test_http_client(self):
        """Init with host and port creates HttpClient."""
        mock_chromadb = _make_mock_chromadb()
        mock_collection = MagicMock()
        mock_chromadb.HttpClient.return_value.get_or_create_collection.return_value = (
            mock_collection
        )

        with patch.dict(
            "sys.modules",
            {"chromadb": mock_chromadb, "chromadb.config": mock_chromadb.config},
        ):
            from test_ai.vectorstore.chroma_store import ChromaVectorStore

            provider = FakeEmbeddingProvider()
            store = ChromaVectorStore(
                embedding_provider=provider,
                host="localhost",
                port=8000,
            )

            mock_chromadb.HttpClient.assert_called_once_with(
                host="localhost", port=8000
            )
            assert store._collection is mock_collection

    def test_custom_collection_name(self):
        """Init with custom collection name."""
        mock_chromadb = _make_mock_chromadb()
        mock_collection = MagicMock()
        mock_chromadb.Client.return_value.get_or_create_collection.return_value = (
            mock_collection
        )

        with patch.dict(
            "sys.modules",
            {"chromadb": mock_chromadb, "chromadb.config": mock_chromadb.config},
        ):
            from test_ai.vectorstore.chroma_store import ChromaVectorStore

            provider = FakeEmbeddingProvider()
            store = ChromaVectorStore(
                embedding_provider=provider, collection_name="my_coll"
            )

            call_kwargs = (
                mock_chromadb.Client.return_value.get_or_create_collection.call_args
            )
            assert call_kwargs[1]["name"] == "my_coll"
            assert store.collection_name == "my_coll"


# Fixture that provides a ready-to-use ChromaVectorStore with mocks
@pytest.fixture
def chroma_fixture():
    """Create a ChromaVectorStore with fully mocked chromadb."""
    mock_chromadb = _make_mock_chromadb()
    mock_collection = MagicMock()
    mock_client = MagicMock()
    mock_client.get_or_create_collection.return_value = mock_collection
    mock_chromadb.Client.return_value = mock_client

    with patch.dict(
        "sys.modules",
        {"chromadb": mock_chromadb, "chromadb.config": mock_chromadb.config},
    ):
        from test_ai.vectorstore.chroma_store import ChromaVectorStore

        provider = FakeEmbeddingProvider()
        store = ChromaVectorStore(embedding_provider=provider)
        yield store, mock_collection, mock_client


class TestChromaVectorStoreAdd:
    """Test ChromaVectorStore.add()."""

    def test_add_empty_list(self, chroma_fixture):
        """Adding empty list returns empty without calling collection."""
        store, mock_coll, _ = chroma_fixture
        result = store.add([])
        assert result == []
        mock_coll.add.assert_not_called()

    def test_add_documents(self, chroma_fixture):
        """Add documents calls collection.add with cleaned metadata."""
        store, mock_coll, _ = chroma_fixture
        docs = [
            Document(content="Hello world", id="d1", metadata={"source": "test"}),
            Document(content="Goodbye", id="d2", metadata={"count": 42}),
        ]
        ids = store.add(docs)
        assert ids == ["d1", "d2"]
        mock_coll.add.assert_called_once()
        call_kwargs = mock_coll.add.call_args[1]
        assert call_kwargs["ids"] == ["d1", "d2"]
        assert call_kwargs["documents"] == ["Hello world", "Goodbye"]

    def test_add_cleans_none_metadata(self, chroma_fixture):
        """None values in metadata are stripped."""
        store, mock_coll, _ = chroma_fixture
        docs = [
            Document(
                content="Test",
                id="d1",
                metadata={"key": "value", "none_key": None},
            ),
        ]
        store.add(docs)
        call_kwargs = mock_coll.add.call_args[1]
        # None should be removed
        assert call_kwargs["metadatas"] == [{"key": "value"}]

    def test_add_cleans_nested_dict_metadata(self, chroma_fixture):
        """Nested dicts in metadata are stripped."""
        store, mock_coll, _ = chroma_fixture
        docs = [
            Document(
                content="Test",
                id="d1",
                metadata={"flat": "ok", "nested": {"a": 1}},
            ),
        ]
        store.add(docs)
        call_kwargs = mock_coll.add.call_args[1]
        assert call_kwargs["metadatas"] == [{"flat": "ok"}]

    def test_add_keeps_primitive_list_metadata(self, chroma_fixture):
        """Lists of primitives are preserved in metadata."""
        store, mock_coll, _ = chroma_fixture
        docs = [
            Document(
                content="Test",
                id="d1",
                metadata={"tags": ["a", "b"], "nums": [1, 2]},
            ),
        ]
        store.add(docs)
        call_kwargs = mock_coll.add.call_args[1]
        assert call_kwargs["metadatas"] == [{"tags": ["a", "b"], "nums": [1, 2]}]

    def test_add_strips_mixed_list_metadata(self, chroma_fixture):
        """Lists with non-primitive items are stripped."""
        store, mock_coll, _ = chroma_fixture
        docs = [
            Document(
                content="Test",
                id="d1",
                metadata={"mixed": [1, {"nested": True}]},
            ),
        ]
        store.add(docs)
        call_kwargs = mock_coll.add.call_args[1]
        # mixed list contains a dict, so it should be stripped
        assert call_kwargs["metadatas"] == [{}]


class TestChromaVectorStoreSearch:
    """Test ChromaVectorStore.search()."""

    def test_search_basic(self, chroma_fixture):
        """Search returns SearchResult objects."""
        store, mock_coll, _ = chroma_fixture
        mock_coll.query.return_value = {
            "ids": [["d1", "d2"]],
            "documents": [["Hello", "World"]],
            "metadatas": [[{"source": "a"}, {"source": "b"}]],
            "distances": [[0.1, 0.3]],
        }
        results = store.search("test query", k=2)
        assert len(results) == 2
        assert isinstance(results[0], SearchResult)
        assert results[0].document.id == "d1"
        assert results[0].document.content == "Hello"
        assert results[0].document.metadata == {"source": "a"}
        assert results[0].score == pytest.approx(0.9)
        assert results[0].distance == pytest.approx(0.1)

    def test_search_empty_results(self, chroma_fixture):
        """Search with no matches returns empty list."""
        store, mock_coll, _ = chroma_fixture
        mock_coll.query.return_value = {
            "ids": [[]],
            "documents": [[]],
            "metadatas": [[]],
            "distances": [[]],
        }
        results = store.search("nothing")
        assert results == []

    def test_search_no_ids_key(self, chroma_fixture):
        """Search with None ids returns empty list."""
        store, mock_coll, _ = chroma_fixture
        mock_coll.query.return_value = {
            "ids": None,
            "documents": None,
            "metadatas": None,
            "distances": None,
        }
        results = store.search("nothing")
        assert results == []

    def test_search_with_filter(self, chroma_fixture):
        """Search passes converted filter to query."""
        store, mock_coll, _ = chroma_fixture
        mock_coll.query.return_value = {
            "ids": [["d1"]],
            "documents": [["Hello"]],
            "metadatas": [[{"source": "a"}]],
            "distances": [[0.1]],
        }
        store.search("test", filter={"source": "a"})
        call_kwargs = mock_coll.query.call_args[1]
        assert call_kwargs["where"] == {"source": {"$eq": "a"}}

    def test_search_no_documents_key(self, chroma_fixture):
        """Search handles missing documents gracefully."""
        store, mock_coll, _ = chroma_fixture
        mock_coll.query.return_value = {
            "ids": [["d1"]],
            "documents": None,
            "metadatas": None,
            "distances": None,
        }
        results = store.search("test")
        assert len(results) == 1
        assert results[0].document.content == ""
        assert results[0].document.metadata == {}
        assert results[0].distance == 0

    def test_search_without_filter(self, chroma_fixture):
        """Search without filter passes where=None."""
        store, mock_coll, _ = chroma_fixture
        mock_coll.query.return_value = {
            "ids": [[]],
            "documents": [[]],
            "metadatas": [[]],
            "distances": [[]],
        }
        store.search("test")
        call_kwargs = mock_coll.query.call_args[1]
        assert call_kwargs["where"] is None


class TestChromaVectorStoreDelete:
    """Test ChromaVectorStore.delete()."""

    def test_delete_existing(self, chroma_fixture):
        """Delete existing documents returns count."""
        store, mock_coll, _ = chroma_fixture
        mock_coll.get.return_value = {"ids": ["d1", "d2"]}
        count = store.delete(["d1", "d2"])
        assert count == 2
        mock_coll.delete.assert_called_once_with(ids=["d1", "d2"])

    def test_delete_nonexistent(self, chroma_fixture):
        """Delete nonexistent documents returns 0."""
        store, mock_coll, _ = chroma_fixture
        mock_coll.get.return_value = {"ids": []}
        count = store.delete(["nonexistent"])
        assert count == 0
        mock_coll.delete.assert_not_called()

    def test_delete_none_ids(self, chroma_fixture):
        """Delete with None ids from collection returns 0."""
        store, mock_coll, _ = chroma_fixture
        mock_coll.get.return_value = {"ids": None}
        count = store.delete(["d1"])
        assert count == 0
        mock_coll.delete.assert_not_called()


class TestChromaVectorStoreGet:
    """Test ChromaVectorStore.get()."""

    def test_get_existing(self, chroma_fixture):
        """Get existing documents returns Document objects."""
        store, mock_coll, _ = chroma_fixture
        mock_coll.get.return_value = {
            "ids": ["d1", "d2"],
            "documents": ["Hello", "World"],
            "metadatas": [{"k": "v1"}, {"k": "v2"}],
        }
        docs = store.get(["d1", "d2"])
        assert len(docs) == 2
        assert docs[0].id == "d1"
        assert docs[0].content == "Hello"
        assert docs[0].metadata == {"k": "v1"}
        assert docs[1].id == "d2"

    def test_get_empty_ids(self, chroma_fixture):
        """Get with no matching IDs returns empty list."""
        store, mock_coll, _ = chroma_fixture
        mock_coll.get.return_value = {
            "ids": [],
            "documents": [],
            "metadatas": [],
        }
        docs = store.get(["nonexistent"])
        assert docs == []

    def test_get_no_documents_key(self, chroma_fixture):
        """Get handles missing documents field gracefully."""
        store, mock_coll, _ = chroma_fixture
        mock_coll.get.return_value = {
            "ids": ["d1"],
            "documents": None,
            "metadatas": None,
        }
        docs = store.get(["d1"])
        assert len(docs) == 1
        assert docs[0].content == ""
        assert docs[0].metadata == {}


class TestChromaVectorStoreCountClear:
    """Test ChromaVectorStore.count() and clear()."""

    def test_count(self, chroma_fixture):
        """Count delegates to collection.count()."""
        store, mock_coll, _ = chroma_fixture
        mock_coll.count.return_value = 42
        assert store.count() == 42
        mock_coll.count.assert_called_once()

    def test_clear(self, chroma_fixture):
        """Clear deletes and recreates collection."""
        store, mock_coll, mock_client = chroma_fixture
        mock_coll.count.return_value = 5
        new_coll = MagicMock()
        mock_client.get_or_create_collection.return_value = new_coll

        count = store.clear()
        assert count == 5
        mock_client.delete_collection.assert_called_once_with("default")
        # After clear, collection should be the new one
        assert store._collection is new_coll


class TestChromaVectorStoreConvertFilter:
    """Test ChromaVectorStore._convert_filter()."""

    def test_direct_equality(self, chroma_fixture):
        """Direct value becomes $eq operator."""
        store, _, _ = chroma_fixture
        result = store._convert_filter({"key": "value"})
        assert result == {"key": {"$eq": "value"}}

    def test_operator_passthrough(self, chroma_fixture):
        """Known operators are passed through."""
        store, _, _ = chroma_fixture
        for op in ["$eq", "$ne", "$gt", "$gte", "$lt", "$lte", "$in", "$nin"]:
            result = store._convert_filter({"field": {op: 42}})
            assert result == {"field": {op: 42}}

    def test_unknown_operator_ignored(self, chroma_fixture):
        """Unknown operator is silently ignored."""
        store, _, _ = chroma_fixture
        result = store._convert_filter({"field": {"$unknown": 42}})
        assert result == {}

    def test_multiple_fields(self, chroma_fixture):
        """Multiple filter fields are all converted."""
        store, _, _ = chroma_fixture
        result = store._convert_filter({"a": 1, "b": {"$gt": 5}})
        assert result == {"a": {"$eq": 1}, "b": {"$gt": 5}}

    def test_numeric_equality(self, chroma_fixture):
        """Numeric direct equality."""
        store, _, _ = chroma_fixture
        result = store._convert_filter({"count": 10})
        assert result == {"count": {"$eq": 10}}


class TestChromaVectorStoreUpdateMetadata:
    """Test ChromaVectorStore.update_metadata()."""

    def test_update_existing_document(self, chroma_fixture):
        """Update metadata on existing document returns True."""
        store, mock_coll, _ = chroma_fixture
        mock_coll.get.return_value = {
            "ids": ["d1"],
            "metadatas": [{"existing": "value"}],
        }
        result = store.update_metadata("d1", {"new_key": "new_value"})
        assert result is True
        # Verify update was called with merged metadata
        call_args = mock_coll.update.call_args[1]
        assert call_args["ids"] == ["d1"]
        merged = call_args["metadatas"][0]
        assert merged["existing"] == "value"
        assert merged["new_key"] == "new_value"

    def test_update_nonexistent_document(self, chroma_fixture):
        """Update metadata on nonexistent document returns False."""
        store, mock_coll, _ = chroma_fixture
        mock_coll.get.return_value = {"ids": [], "metadatas": []}
        result = store.update_metadata("nonexistent", {"key": "value"})
        assert result is False
        mock_coll.update.assert_not_called()

    def test_update_cleans_metadata(self, chroma_fixture):
        """Update strips None and nested dict values."""
        store, mock_coll, _ = chroma_fixture
        mock_coll.get.return_value = {
            "ids": ["d1"],
            "metadatas": [{"existing": "value"}],
        }
        result = store.update_metadata(
            "d1", {"keep": "yes", "drop_none": None, "drop_dict": {"a": 1}}
        )
        assert result is True
        merged = mock_coll.update.call_args[1]["metadatas"][0]
        assert "keep" in merged
        assert "drop_none" not in merged
        assert "drop_dict" not in merged

    def test_update_exception_returns_false(self, chroma_fixture):
        """Exception during update returns False."""
        store, mock_coll, _ = chroma_fixture
        mock_coll.get.side_effect = RuntimeError("DB error")
        result = store.update_metadata("d1", {"key": "value"})
        assert result is False

    def test_update_no_existing_metadatas(self, chroma_fixture):
        """Update when metadatas is None/empty list."""
        store, mock_coll, _ = chroma_fixture
        mock_coll.get.return_value = {
            "ids": ["d1"],
            "metadatas": None,
        }
        result = store.update_metadata("d1", {"key": "value"})
        assert result is True
        merged = mock_coll.update.call_args[1]["metadatas"][0]
        assert merged == {"key": "value"}


class TestChromaVectorStoreGetStats:
    """Test ChromaVectorStore.get_stats()."""

    def test_get_stats(self, chroma_fixture):
        """get_stats returns correct dict."""
        store, mock_coll, _ = chroma_fixture
        mock_coll.count.return_value = 10
        stats = store.get_stats()
        assert stats["collection_name"] == "default"
        assert stats["document_count"] == 10
        assert stats["embedding_dimension"] == 4
        assert stats["embedding_model"] == "fake-model"


class TestChromaEmbeddingFunction:
    """Test ChromaEmbeddingFunction wrapper."""

    def test_call(self):
        """__call__ delegates to provider.embed_batch."""
        from test_ai.vectorstore.chroma_store import ChromaEmbeddingFunction

        provider = FakeEmbeddingProvider(dim=3)
        func = ChromaEmbeddingFunction(provider)
        result = func(["hello", "world"])
        assert len(result) == 2
        assert all(len(r) == 3 for r in result)


# ===========================================================================
# OpenAIEmbeddings tests
# ===========================================================================


class TestOpenAIEmbeddings:
    """Test OpenAIEmbeddings with mocked openai."""

    def _make_store(self, mock_openai, **kwargs):
        """Helper to create OpenAIEmbeddings with mock."""
        with patch.dict("sys.modules", {"openai": mock_openai}):
            from test_ai.vectorstore.embeddings import OpenAIEmbeddings

            return OpenAIEmbeddings(**kwargs)

    def test_import_error(self):
        """Raises VectorStoreError when openai not installed."""
        with patch.dict("sys.modules", {"openai": None}):
            from test_ai.vectorstore.embeddings import OpenAIEmbeddings

            with pytest.raises(VectorStoreError, match="openai"):
                OpenAIEmbeddings()

    def test_init_default(self):
        """Init with defaults uses text-embedding-3-small."""
        mock_openai = _make_mock_openai()
        emb = self._make_store(mock_openai)
        assert emb.model_name == "text-embedding-3-small"
        assert emb.dimension == 1536
        # Called OpenAI() without api_key
        mock_openai.OpenAI.assert_called_once_with()

    def test_init_with_api_key(self):
        """Init with api_key passes it to OpenAI client."""
        mock_openai = _make_mock_openai()
        self._make_store(mock_openai, api_key="sk-test")
        mock_openai.OpenAI.assert_called_once_with(api_key="sk-test")

    def test_init_with_dimensions(self):
        """Init with dimensions sets custom dimension."""
        mock_openai = _make_mock_openai()
        emb = self._make_store(mock_openai, dimensions=256)
        assert emb.dimension == 256

    def test_init_unknown_model(self):
        """Unknown model defaults to 1536 dimension."""
        mock_openai = _make_mock_openai()
        emb = self._make_store(mock_openai, model="custom-model")
        assert emb.dimension == 1536

    def test_init_large_model(self):
        """text-embedding-3-large has 3072 dimensions."""
        mock_openai = _make_mock_openai()
        emb = self._make_store(mock_openai, model="text-embedding-3-large")
        assert emb.dimension == 3072

    def test_embed(self):
        """embed() calls client.embeddings.create and returns embedding."""
        mock_openai = _make_mock_openai()
        mock_embedding = MagicMock()
        mock_embedding.embedding = [0.1, 0.2, 0.3]
        mock_response = MagicMock()
        mock_response.data = [mock_embedding]
        mock_openai.OpenAI.return_value.embeddings.create.return_value = mock_response

        emb = self._make_store(mock_openai)
        result = emb.embed("hello")
        assert result == [0.1, 0.2, 0.3]

    def test_embed_with_dimension_reduction(self):
        """embed() passes dimensions kwarg for v3 models."""
        mock_openai = _make_mock_openai()
        mock_embedding = MagicMock()
        mock_embedding.embedding = [0.1, 0.2]
        mock_response = MagicMock()
        mock_response.data = [mock_embedding]
        mock_openai.OpenAI.return_value.embeddings.create.return_value = mock_response

        emb = self._make_store(
            mock_openai, model="text-embedding-3-small", dimensions=256
        )
        emb.embed("hello")

        call_kwargs = mock_openai.OpenAI.return_value.embeddings.create.call_args[1]
        assert call_kwargs["dimensions"] == 256

    def test_embed_no_dimension_reduction_for_non_v3(self):
        """embed() does NOT pass dimensions for non-v3 models."""
        mock_openai = _make_mock_openai()
        mock_embedding = MagicMock()
        mock_embedding.embedding = [0.1, 0.2]
        mock_response = MagicMock()
        mock_response.data = [mock_embedding]
        mock_openai.OpenAI.return_value.embeddings.create.return_value = mock_response

        emb = self._make_store(
            mock_openai, model="text-embedding-ada-002", dimensions=256
        )
        emb.embed("hello")

        call_kwargs = mock_openai.OpenAI.return_value.embeddings.create.call_args[1]
        assert "dimensions" not in call_kwargs

    def test_embed_batch(self):
        """embed_batch() returns sorted embeddings."""
        mock_openai = _make_mock_openai()
        emb1 = MagicMock()
        emb1.index = 0
        emb1.embedding = [0.1, 0.2]
        emb2 = MagicMock()
        emb2.index = 1
        emb2.embedding = [0.3, 0.4]
        mock_response = MagicMock()
        # Return in reverse order to test sorting
        mock_response.data = [emb2, emb1]
        mock_openai.OpenAI.return_value.embeddings.create.return_value = mock_response

        emb = self._make_store(mock_openai)
        result = emb.embed_batch(["hello", "world"])
        # Should be sorted by index
        assert result == [[0.1, 0.2], [0.3, 0.4]]

    def test_embed_batch_with_dimension_reduction(self):
        """embed_batch() passes dimensions kwarg for v3 models."""
        mock_openai = _make_mock_openai()
        emb1 = MagicMock()
        emb1.index = 0
        emb1.embedding = [0.1]
        mock_response = MagicMock()
        mock_response.data = [emb1]
        mock_openai.OpenAI.return_value.embeddings.create.return_value = mock_response

        emb = self._make_store(
            mock_openai, model="text-embedding-3-large", dimensions=512
        )
        emb.embed_batch(["hello"])

        call_kwargs = mock_openai.OpenAI.return_value.embeddings.create.call_args[1]
        assert call_kwargs["dimensions"] == 512

    def test_embed_async(self):
        """embed_async() uses AsyncOpenAI client."""
        mock_openai = _make_mock_openai()

        # Set up the sync client for __init__
        mock_openai.OpenAI.return_value = MagicMock()

        # Set up async client
        mock_embedding = MagicMock()
        mock_embedding.embedding = [0.5, 0.6]
        mock_async_response = MagicMock()
        mock_async_response.data = [mock_embedding]

        async_client = MagicMock()
        mock_openai.AsyncOpenAI.return_value = async_client

        # Make embeddings.create an async function
        async def mock_create(**kwargs):
            return mock_async_response

        async_client.embeddings.create = mock_create

        with patch.dict("sys.modules", {"openai": mock_openai}):
            from test_ai.vectorstore.embeddings import OpenAIEmbeddings

            emb = OpenAIEmbeddings()
            result = asyncio.run(emb.embed_async("hello"))
            assert result == [0.5, 0.6]

    def test_embed_async_import_error_fallback(self):
        """embed_async() falls back to sync when AsyncOpenAI unavailable."""
        mock_openai = _make_mock_openai()

        # Set up the sync embed
        mock_embedding = MagicMock()
        mock_embedding.embedding = [0.1, 0.2]
        mock_response = MagicMock()
        mock_response.data = [mock_embedding]
        mock_openai.OpenAI.return_value.embeddings.create.return_value = mock_response

        with patch.dict("sys.modules", {"openai": mock_openai}):
            from test_ai.vectorstore.embeddings import OpenAIEmbeddings

            emb = OpenAIEmbeddings()

            # Patch the import inside embed_async to raise ImportError
            # The code does `from openai import AsyncOpenAI` -- we intercept
            # builtins.__import__ to make that specific import fail.
            real_import = (
                __builtins__["__import__"]
                if isinstance(__builtins__, dict)
                else __builtins__.__import__
            )

            def failing_import(name, *args, **kwargs):
                if name == "openai":
                    raise ImportError("No AsyncOpenAI")
                return real_import(name, *args, **kwargs)

            with patch("builtins.__import__", side_effect=failing_import):
                result = asyncio.run(emb.embed_async("hello"))

            # Fallback uses super().embed_async() -> run_in_executor -> sync embed()
            assert result == [0.1, 0.2]

    def test_embed_batch_async_import_error_fallback(self):
        """embed_batch_async() falls back to sync when AsyncOpenAI unavailable."""
        mock_openai = _make_mock_openai()

        emb1 = MagicMock()
        emb1.index = 0
        emb1.embedding = [0.1, 0.2]
        mock_response = MagicMock()
        mock_response.data = [emb1]
        mock_openai.OpenAI.return_value.embeddings.create.return_value = mock_response

        with patch.dict("sys.modules", {"openai": mock_openai}):
            from test_ai.vectorstore.embeddings import OpenAIEmbeddings

            emb = OpenAIEmbeddings()

            real_import = (
                __builtins__["__import__"]
                if isinstance(__builtins__, dict)
                else __builtins__.__import__
            )

            def failing_import(name, *args, **kwargs):
                if name == "openai":
                    raise ImportError("No AsyncOpenAI")
                return real_import(name, *args, **kwargs)

            with patch("builtins.__import__", side_effect=failing_import):
                result = asyncio.run(emb.embed_batch_async(["hello"]))

            # Fallback uses super().embed_batch_async() -> run_in_executor -> sync embed_batch()
            assert result == [[0.1, 0.2]]

    def test_embed_batch_async(self):
        """embed_batch_async() uses AsyncOpenAI client."""
        mock_openai = _make_mock_openai()
        mock_openai.OpenAI.return_value = MagicMock()

        emb1 = MagicMock()
        emb1.index = 0
        emb1.embedding = [0.1]
        emb2 = MagicMock()
        emb2.index = 1
        emb2.embedding = [0.2]
        mock_async_response = MagicMock()
        mock_async_response.data = [emb1, emb2]

        async_client = MagicMock()
        mock_openai.AsyncOpenAI.return_value = async_client

        async def mock_create(**kwargs):
            return mock_async_response

        async_client.embeddings.create = mock_create

        with patch.dict("sys.modules", {"openai": mock_openai}):
            from test_ai.vectorstore.embeddings import OpenAIEmbeddings

            emb = OpenAIEmbeddings()
            result = asyncio.run(emb.embed_batch_async(["hello", "world"]))
            assert result == [[0.1], [0.2]]

    def test_embed_batch_async_with_dimensions(self):
        """embed_batch_async() passes dimensions for v3 models."""
        mock_openai = _make_mock_openai()
        mock_openai.OpenAI.return_value = MagicMock()

        emb1 = MagicMock()
        emb1.index = 0
        emb1.embedding = [0.1]
        mock_async_response = MagicMock()
        mock_async_response.data = [emb1]

        async_client = MagicMock()
        mock_openai.AsyncOpenAI.return_value = async_client
        captured_kwargs = {}

        async def mock_create(**kwargs):
            captured_kwargs.update(kwargs)
            return mock_async_response

        async_client.embeddings.create = mock_create

        with patch.dict("sys.modules", {"openai": mock_openai}):
            from test_ai.vectorstore.embeddings import OpenAIEmbeddings

            emb = OpenAIEmbeddings(model="text-embedding-3-small", dimensions=128)
            asyncio.run(emb.embed_batch_async(["hello"]))
            assert captured_kwargs["dimensions"] == 128

    def test_embed_async_with_dimensions(self):
        """embed_async() passes dimensions for v3 models."""
        mock_openai = _make_mock_openai()
        mock_openai.OpenAI.return_value = MagicMock()

        mock_embedding = MagicMock()
        mock_embedding.embedding = [0.5]
        mock_async_response = MagicMock()
        mock_async_response.data = [mock_embedding]

        async_client = MagicMock()
        mock_openai.AsyncOpenAI.return_value = async_client
        captured_kwargs = {}

        async def mock_create(**kwargs):
            captured_kwargs.update(kwargs)
            return mock_async_response

        async_client.embeddings.create = mock_create

        with patch.dict("sys.modules", {"openai": mock_openai}):
            from test_ai.vectorstore.embeddings import OpenAIEmbeddings

            emb = OpenAIEmbeddings(model="text-embedding-3-large", dimensions=512)
            asyncio.run(emb.embed_async("hello"))
            assert captured_kwargs["dimensions"] == 512

    def test_embed_async_no_dimensions_for_non_v3(self):
        """embed_async() does NOT pass dimensions for non-v3 models."""
        mock_openai = _make_mock_openai()
        mock_openai.OpenAI.return_value = MagicMock()

        mock_embedding = MagicMock()
        mock_embedding.embedding = [0.5]
        mock_async_response = MagicMock()
        mock_async_response.data = [mock_embedding]

        async_client = MagicMock()
        mock_openai.AsyncOpenAI.return_value = async_client
        captured_kwargs = {}

        async def mock_create(**kwargs):
            captured_kwargs.update(kwargs)
            return mock_async_response

        async_client.embeddings.create = mock_create

        with patch.dict("sys.modules", {"openai": mock_openai}):
            from test_ai.vectorstore.embeddings import OpenAIEmbeddings

            # dimensions is set but model is ada-002 (not v3)
            emb = OpenAIEmbeddings(model="text-embedding-ada-002", dimensions=512)
            asyncio.run(emb.embed_async("hello"))
            assert "dimensions" not in captured_kwargs

    def test_embed_batch_async_no_dimensions_for_non_v3(self):
        """embed_batch_async() does NOT pass dimensions for non-v3 models."""
        mock_openai = _make_mock_openai()
        mock_openai.OpenAI.return_value = MagicMock()

        emb1 = MagicMock()
        emb1.index = 0
        emb1.embedding = [0.1]
        mock_async_response = MagicMock()
        mock_async_response.data = [emb1]

        async_client = MagicMock()
        mock_openai.AsyncOpenAI.return_value = async_client
        captured_kwargs = {}

        async def mock_create(**kwargs):
            captured_kwargs.update(kwargs)
            return mock_async_response

        async_client.embeddings.create = mock_create

        with patch.dict("sys.modules", {"openai": mock_openai}):
            from test_ai.vectorstore.embeddings import OpenAIEmbeddings

            emb = OpenAIEmbeddings(model="text-embedding-ada-002", dimensions=512)
            asyncio.run(emb.embed_batch_async(["hello"]))
            assert "dimensions" not in captured_kwargs


# ===========================================================================
# SentenceTransformerEmbeddings tests
# ===========================================================================


class TestSentenceTransformerEmbeddings:
    """Test SentenceTransformerEmbeddings with mocked sentence_transformers."""

    def test_import_error(self):
        """Raises VectorStoreError when not installed."""
        with patch.dict("sys.modules", {"sentence_transformers": None}):
            from test_ai.vectorstore.embeddings import SentenceTransformerEmbeddings

            with pytest.raises(VectorStoreError, match="sentence-transformers"):
                SentenceTransformerEmbeddings()

    def test_init_default(self):
        """Init with default model."""
        mock_st = _make_mock_sentence_transformers()
        mock_model = MagicMock()
        mock_model.get_sentence_embedding_dimension.return_value = 384
        mock_st.SentenceTransformer.return_value = mock_model

        with patch.dict("sys.modules", {"sentence_transformers": mock_st}):
            from test_ai.vectorstore.embeddings import SentenceTransformerEmbeddings

            emb = SentenceTransformerEmbeddings()
            assert emb.model_name == "all-MiniLM-L6-v2"
            assert emb.dimension == 384  # from MODELS dict

    def test_init_known_model(self):
        """Known model uses dimension from MODELS dict."""
        mock_st = _make_mock_sentence_transformers()
        mock_model = MagicMock()
        mock_st.SentenceTransformer.return_value = mock_model

        with patch.dict("sys.modules", {"sentence_transformers": mock_st}):
            from test_ai.vectorstore.embeddings import SentenceTransformerEmbeddings

            emb = SentenceTransformerEmbeddings(model="all-mpnet-base-v2")
            assert emb.dimension == 768

    def test_init_unknown_model_uses_model_dimension(self):
        """Unknown model queries model for dimension."""
        mock_st = _make_mock_sentence_transformers()
        mock_model = MagicMock()
        mock_model.get_sentence_embedding_dimension.return_value = 512
        mock_st.SentenceTransformer.return_value = mock_model

        with patch.dict("sys.modules", {"sentence_transformers": mock_st}):
            from test_ai.vectorstore.embeddings import SentenceTransformerEmbeddings

            emb = SentenceTransformerEmbeddings(model="custom-model")
            assert emb.dimension == 512

    def test_init_with_device(self):
        """Init passes device to SentenceTransformer."""
        mock_st = _make_mock_sentence_transformers()
        mock_model = MagicMock()
        mock_model.get_sentence_embedding_dimension.return_value = 384
        mock_st.SentenceTransformer.return_value = mock_model

        with patch.dict("sys.modules", {"sentence_transformers": mock_st}):
            from test_ai.vectorstore.embeddings import SentenceTransformerEmbeddings

            SentenceTransformerEmbeddings(device="cuda")
            mock_st.SentenceTransformer.assert_called_once_with(
                "all-MiniLM-L6-v2", device="cuda"
            )

    def test_embed(self):
        """embed() returns tolist() of encode result."""
        mock_st = _make_mock_sentence_transformers()
        mock_model = MagicMock()
        mock_array = MagicMock()
        mock_array.tolist.return_value = [0.1, 0.2, 0.3]
        mock_model.encode.return_value = mock_array
        mock_st.SentenceTransformer.return_value = mock_model

        with patch.dict("sys.modules", {"sentence_transformers": mock_st}):
            from test_ai.vectorstore.embeddings import SentenceTransformerEmbeddings

            emb = SentenceTransformerEmbeddings()
            result = emb.embed("hello")
            assert result == [0.1, 0.2, 0.3]
            mock_model.encode.assert_called_once_with("hello", convert_to_numpy=True)

    def test_embed_batch(self):
        """embed_batch() encodes multiple texts."""
        mock_st = _make_mock_sentence_transformers()
        mock_model = MagicMock()

        arr1 = MagicMock()
        arr1.tolist.return_value = [0.1, 0.2]
        arr2 = MagicMock()
        arr2.tolist.return_value = [0.3, 0.4]
        mock_model.encode.return_value = [arr1, arr2]
        mock_st.SentenceTransformer.return_value = mock_model

        with patch.dict("sys.modules", {"sentence_transformers": mock_st}):
            from test_ai.vectorstore.embeddings import SentenceTransformerEmbeddings

            emb = SentenceTransformerEmbeddings()
            result = emb.embed_batch(["hello", "world"])
            assert result == [[0.1, 0.2], [0.3, 0.4]]

    def test_embed_async_fallback(self):
        """embed_async() uses base class fallback (run_in_executor)."""
        mock_st = _make_mock_sentence_transformers()
        mock_model = MagicMock()
        mock_array = MagicMock()
        mock_array.tolist.return_value = [0.1, 0.2]
        mock_model.encode.return_value = mock_array
        mock_st.SentenceTransformer.return_value = mock_model

        with patch.dict("sys.modules", {"sentence_transformers": mock_st}):
            from test_ai.vectorstore.embeddings import SentenceTransformerEmbeddings

            emb = SentenceTransformerEmbeddings()
            # SentenceTransformerEmbeddings doesn't override embed_async,
            # so it uses the base class which calls run_in_executor
            result = asyncio.run(emb.embed_async("hello"))
            assert result == [0.1, 0.2]

    def test_embed_batch_async_fallback(self):
        """embed_batch_async() uses base class fallback."""
        mock_st = _make_mock_sentence_transformers()
        mock_model = MagicMock()

        arr1 = MagicMock()
        arr1.tolist.return_value = [0.1, 0.2]
        mock_model.encode.return_value = [arr1]
        mock_st.SentenceTransformer.return_value = mock_model

        with patch.dict("sys.modules", {"sentence_transformers": mock_st}):
            from test_ai.vectorstore.embeddings import SentenceTransformerEmbeddings

            emb = SentenceTransformerEmbeddings()
            result = asyncio.run(emb.embed_batch_async(["hello"]))
            assert result == [[0.1, 0.2]]


# ===========================================================================
# CohereEmbeddings tests
# ===========================================================================


class TestCohereEmbeddings:
    """Test CohereEmbeddings with mocked cohere."""

    def test_import_error(self):
        """Raises VectorStoreError when cohere not installed."""
        with patch.dict("sys.modules", {"cohere": None}):
            from test_ai.vectorstore.embeddings import CohereEmbeddings

            with pytest.raises(VectorStoreError, match="cohere"):
                CohereEmbeddings()

    def test_init_default(self):
        """Init with defaults."""
        mock_cohere = _make_mock_cohere()
        with patch.dict("sys.modules", {"cohere": mock_cohere}):
            from test_ai.vectorstore.embeddings import CohereEmbeddings

            emb = CohereEmbeddings()
            assert emb.model_name == "embed-english-v3.0"
            assert emb.dimension == 1024
            mock_cohere.Client.assert_called_once_with()

    def test_init_with_api_key(self):
        """Init with api_key passes it to Client."""
        mock_cohere = _make_mock_cohere()
        with patch.dict("sys.modules", {"cohere": mock_cohere}):
            from test_ai.vectorstore.embeddings import CohereEmbeddings

            CohereEmbeddings(api_key="test-key")
            mock_cohere.Client.assert_called_once_with("test-key")

    def test_init_unknown_model(self):
        """Unknown model defaults to 1024 dimensions."""
        mock_cohere = _make_mock_cohere()
        with patch.dict("sys.modules", {"cohere": mock_cohere}):
            from test_ai.vectorstore.embeddings import CohereEmbeddings

            emb = CohereEmbeddings(model="custom-model")
            assert emb.dimension == 1024

    def test_init_light_model(self):
        """Light model has 384 dimensions."""
        mock_cohere = _make_mock_cohere()
        with patch.dict("sys.modules", {"cohere": mock_cohere}):
            from test_ai.vectorstore.embeddings import CohereEmbeddings

            emb = CohereEmbeddings(model="embed-english-light-v3.0")
            assert emb.dimension == 384

    def test_embed(self):
        """embed() calls client.embed and returns first embedding."""
        mock_cohere = _make_mock_cohere()
        mock_response = MagicMock()
        mock_response.embeddings = [[0.1, 0.2, 0.3]]
        mock_cohere.Client.return_value.embed.return_value = mock_response

        with patch.dict("sys.modules", {"cohere": mock_cohere}):
            from test_ai.vectorstore.embeddings import CohereEmbeddings

            emb = CohereEmbeddings()
            result = emb.embed("hello")
            assert result == [0.1, 0.2, 0.3]
            mock_cohere.Client.return_value.embed.assert_called_once_with(
                texts=["hello"],
                model="embed-english-v3.0",
                input_type="search_document",
            )

    def test_embed_batch(self):
        """embed_batch() calls client.embed with multiple texts."""
        mock_cohere = _make_mock_cohere()
        mock_response = MagicMock()
        mock_response.embeddings = [[0.1, 0.2], [0.3, 0.4]]
        mock_cohere.Client.return_value.embed.return_value = mock_response

        with patch.dict("sys.modules", {"cohere": mock_cohere}):
            from test_ai.vectorstore.embeddings import CohereEmbeddings

            emb = CohereEmbeddings()
            result = emb.embed_batch(["hello", "world"])
            assert result == [[0.1, 0.2], [0.3, 0.4]]

    def test_custom_input_type(self):
        """Custom input_type is used in embed calls."""
        mock_cohere = _make_mock_cohere()
        mock_response = MagicMock()
        mock_response.embeddings = [[0.1]]
        mock_cohere.Client.return_value.embed.return_value = mock_response

        with patch.dict("sys.modules", {"cohere": mock_cohere}):
            from test_ai.vectorstore.embeddings import CohereEmbeddings

            emb = CohereEmbeddings(input_type="search_query")
            emb.embed("query")
            call_kwargs = mock_cohere.Client.return_value.embed.call_args[1]
            assert call_kwargs["input_type"] == "search_query"


# ===========================================================================
# VoyageEmbeddings tests
# ===========================================================================


class TestVoyageEmbeddings:
    """Test VoyageEmbeddings with mocked voyageai."""

    def test_import_error(self):
        """Raises VectorStoreError when voyageai not installed."""
        with patch.dict("sys.modules", {"voyageai": None}):
            from test_ai.vectorstore.embeddings import VoyageEmbeddings

            with pytest.raises(VectorStoreError, match="voyageai"):
                VoyageEmbeddings()

    def test_init_default(self):
        """Init with defaults."""
        mock_voyage = _make_mock_voyageai()
        with patch.dict("sys.modules", {"voyageai": mock_voyage}):
            from test_ai.vectorstore.embeddings import VoyageEmbeddings

            emb = VoyageEmbeddings()
            assert emb.model_name == "voyage-3"
            assert emb.dimension == 1024
            mock_voyage.Client.assert_called_once_with()

    def test_init_with_api_key(self):
        """Init with api_key passes it to Client."""
        mock_voyage = _make_mock_voyageai()
        with patch.dict("sys.modules", {"voyageai": mock_voyage}):
            from test_ai.vectorstore.embeddings import VoyageEmbeddings

            VoyageEmbeddings(api_key="voy-test")
            mock_voyage.Client.assert_called_once_with(api_key="voy-test")

    def test_init_lite_model(self):
        """voyage-3-lite has 512 dimensions."""
        mock_voyage = _make_mock_voyageai()
        with patch.dict("sys.modules", {"voyageai": mock_voyage}):
            from test_ai.vectorstore.embeddings import VoyageEmbeddings

            emb = VoyageEmbeddings(model="voyage-3-lite")
            assert emb.dimension == 512

    def test_init_unknown_model(self):
        """Unknown model defaults to 1024."""
        mock_voyage = _make_mock_voyageai()
        with patch.dict("sys.modules", {"voyageai": mock_voyage}):
            from test_ai.vectorstore.embeddings import VoyageEmbeddings

            emb = VoyageEmbeddings(model="custom-model")
            assert emb.dimension == 1024

    def test_embed(self):
        """embed() calls client.embed and returns first embedding."""
        mock_voyage = _make_mock_voyageai()
        mock_result = MagicMock()
        mock_result.embeddings = [[0.1, 0.2, 0.3]]
        mock_voyage.Client.return_value.embed.return_value = mock_result

        with patch.dict("sys.modules", {"voyageai": mock_voyage}):
            from test_ai.vectorstore.embeddings import VoyageEmbeddings

            emb = VoyageEmbeddings()
            result = emb.embed("hello")
            assert result == [0.1, 0.2, 0.3]
            mock_voyage.Client.return_value.embed.assert_called_once_with(
                ["hello"], model="voyage-3"
            )

    def test_embed_batch(self):
        """embed_batch() calls client.embed with texts list."""
        mock_voyage = _make_mock_voyageai()
        mock_result = MagicMock()
        mock_result.embeddings = [[0.1, 0.2], [0.3, 0.4]]
        mock_voyage.Client.return_value.embed.return_value = mock_result

        with patch.dict("sys.modules", {"voyageai": mock_voyage}):
            from test_ai.vectorstore.embeddings import VoyageEmbeddings

            emb = VoyageEmbeddings()
            result = emb.embed_batch(["hello", "world"])
            assert result == [[0.1, 0.2], [0.3, 0.4]]

    def test_code_model(self):
        """voyage-code-3 has correct dimensions."""
        mock_voyage = _make_mock_voyageai()
        with patch.dict("sys.modules", {"voyageai": mock_voyage}):
            from test_ai.vectorstore.embeddings import VoyageEmbeddings

            emb = VoyageEmbeddings(model="voyage-code-3")
            assert emb.dimension == 1024


# ===========================================================================
# get_embeddings factory tests
# ===========================================================================


class TestGetEmbeddingsFactory:
    """Test the get_embeddings() factory function with mocked providers."""

    def test_openai_provider(self):
        """Factory creates OpenAIEmbeddings for 'openai'."""
        mock_openai = _make_mock_openai()
        with patch.dict("sys.modules", {"openai": mock_openai}):
            from test_ai.vectorstore.embeddings import get_embeddings

            emb = get_embeddings(provider="openai")
            assert emb.model_name == "text-embedding-3-small"

    def test_openai_provider_custom_model(self):
        """Factory passes custom model to OpenAIEmbeddings."""
        mock_openai = _make_mock_openai()
        with patch.dict("sys.modules", {"openai": mock_openai}):
            from test_ai.vectorstore.embeddings import get_embeddings

            emb = get_embeddings(provider="openai", model="text-embedding-3-large")
            assert emb.model_name == "text-embedding-3-large"

    def test_sentence_transformers_provider(self):
        """Factory creates SentenceTransformerEmbeddings for 'sentence-transformers'."""
        mock_st = _make_mock_sentence_transformers()
        mock_model = MagicMock()
        mock_model.get_sentence_embedding_dimension.return_value = 384
        mock_st.SentenceTransformer.return_value = mock_model

        with patch.dict("sys.modules", {"sentence_transformers": mock_st}):
            from test_ai.vectorstore.embeddings import get_embeddings

            emb = get_embeddings(provider="sentence-transformers")
            assert emb.model_name == "all-MiniLM-L6-v2"

    def test_local_alias(self):
        """Factory 'local' is alias for sentence-transformers."""
        mock_st = _make_mock_sentence_transformers()
        mock_model = MagicMock()
        mock_model.get_sentence_embedding_dimension.return_value = 384
        mock_st.SentenceTransformer.return_value = mock_model

        with patch.dict("sys.modules", {"sentence_transformers": mock_st}):
            from test_ai.vectorstore.embeddings import get_embeddings

            emb = get_embeddings(provider="local")
            assert emb.model_name == "all-MiniLM-L6-v2"

    def test_cohere_provider(self):
        """Factory creates CohereEmbeddings for 'cohere'."""
        mock_cohere = _make_mock_cohere()
        with patch.dict("sys.modules", {"cohere": mock_cohere}):
            from test_ai.vectorstore.embeddings import get_embeddings

            emb = get_embeddings(provider="cohere")
            assert emb.model_name == "embed-english-v3.0"

    def test_voyage_provider(self):
        """Factory creates VoyageEmbeddings for 'voyage'."""
        mock_voyage = _make_mock_voyageai()
        with patch.dict("sys.modules", {"voyageai": mock_voyage}):
            from test_ai.vectorstore.embeddings import get_embeddings

            emb = get_embeddings(provider="voyage")
            assert emb.model_name == "voyage-3"

    def test_unknown_provider_raises(self):
        """Unknown provider raises VectorStoreError."""
        from test_ai.vectorstore.embeddings import get_embeddings

        with pytest.raises(VectorStoreError, match="Unknown embedding provider"):
            get_embeddings(provider="nonexistent")

    def test_kwargs_passthrough(self):
        """Extra kwargs are passed to provider constructor."""
        mock_openai = _make_mock_openai()
        with patch.dict("sys.modules", {"openai": mock_openai}):
            from test_ai.vectorstore.embeddings import get_embeddings

            get_embeddings(provider="openai", api_key="sk-test")
            mock_openai.OpenAI.assert_called_once_with(api_key="sk-test")
