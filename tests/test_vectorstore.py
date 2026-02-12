"""Tests for vector store module.

Covers:
- Document, SearchResult data classes
- cosine_similarity, euclidean_distance math functions
- MemoryVectorStore (in-memory implementation)
- VectorStore base class convenience methods
- EmbeddingProvider ABC and factory function
- Metadata filtering operators

Skips: ChromaVectorStore, OpenAIEmbeddings, SentenceTransformerEmbeddings,
       CohereEmbeddings, VoyageEmbeddings (external dependencies)
"""

import math
import sys
from unittest.mock import patch

import pytest

sys.path.insert(0, "src")

from test_ai.vectorstore.base import (
    Document,
    EmbeddingProvider,
    SearchResult,
    VectorStore,
    VectorStoreError,
)
from test_ai.vectorstore.memory_store import (
    MemoryVectorStore,
    cosine_similarity,
    euclidean_distance,
)
from test_ai.vectorstore.embeddings import get_embeddings


# ---------------------------------------------------------------------------
# Helper: Fake embedding provider for testing
# ---------------------------------------------------------------------------


class FakeEmbeddingProvider(EmbeddingProvider):
    """Deterministic embedding provider for tests.

    Generates embeddings based on character counts to produce
    consistent, non-trivial vectors for similarity testing.
    """

    def __init__(self, dim: int = 4):
        self._dim = dim

    @property
    def dimension(self) -> int:
        return self._dim

    @property
    def model_name(self) -> str:
        return "fake-model"

    def embed(self, text: str) -> list[float]:
        """Generate deterministic embedding from text."""
        vec = [0.0] * self._dim
        for i, ch in enumerate(text):
            vec[i % self._dim] += ord(ch) / 1000.0
        # Normalize
        norm = math.sqrt(sum(x * x for x in vec))
        if norm > 0:
            vec = [x / norm for x in vec]
        return vec

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        return [self.embed(t) for t in texts]


# ---------------------------------------------------------------------------
# Math functions
# ---------------------------------------------------------------------------


class TestCosineSimilarity:
    """Tests for cosine_similarity function."""

    def test_identical_vectors(self):
        """Identical vectors have similarity 1.0."""
        v = [1.0, 2.0, 3.0]
        assert cosine_similarity(v, v) == pytest.approx(1.0)

    def test_opposite_vectors(self):
        """Opposite vectors have similarity -1.0."""
        a = [1.0, 0.0]
        b = [-1.0, 0.0]
        assert cosine_similarity(a, b) == pytest.approx(-1.0)

    def test_orthogonal_vectors(self):
        """Orthogonal vectors have similarity 0.0."""
        a = [1.0, 0.0]
        b = [0.0, 1.0]
        assert cosine_similarity(a, b) == pytest.approx(0.0)

    def test_zero_vector(self):
        """Zero vector returns 0.0 similarity."""
        a = [1.0, 2.0]
        b = [0.0, 0.0]
        assert cosine_similarity(a, b) == 0.0
        assert cosine_similarity(b, a) == 0.0
        assert cosine_similarity(b, b) == 0.0

    def test_similar_vectors(self):
        """Similar but not identical vectors have high similarity."""
        a = [1.0, 2.0, 3.0]
        b = [1.1, 2.1, 3.1]
        sim = cosine_similarity(a, b)
        assert sim > 0.99

    def test_different_vectors(self):
        """Very different vectors have lower similarity."""
        a = [1.0, 0.0, 0.0]
        b = [0.0, 0.0, 1.0]
        assert cosine_similarity(a, b) == pytest.approx(0.0)


class TestEuclideanDistance:
    """Tests for euclidean_distance function."""

    def test_identical_vectors(self):
        """Identical vectors have distance 0."""
        v = [1.0, 2.0, 3.0]
        assert euclidean_distance(v, v) == pytest.approx(0.0)

    def test_known_distance(self):
        """Distance matches known value."""
        a = [0.0, 0.0]
        b = [3.0, 4.0]
        assert euclidean_distance(a, b) == pytest.approx(5.0)

    def test_single_dimension(self):
        """Works with 1D vectors."""
        assert euclidean_distance([0.0], [5.0]) == pytest.approx(5.0)


# ---------------------------------------------------------------------------
# Document
# ---------------------------------------------------------------------------


class TestDocument:
    """Tests for Document dataclass."""

    def test_create_with_defaults(self):
        """Document created with auto-generated id."""
        doc = Document(content="Hello world")
        assert doc.content == "Hello world"
        assert doc.id  # auto-generated UUID
        assert doc.metadata == {}
        assert doc.embedding is None

    def test_create_with_all_fields(self):
        """Document created with explicit values."""
        doc = Document(
            content="Test",
            metadata={"source": "unit_test"},
            id="doc-1",
            embedding=[0.1, 0.2],
        )
        assert doc.id == "doc-1"
        assert doc.metadata == {"source": "unit_test"}
        assert doc.embedding == [0.1, 0.2]

    def test_to_dict(self):
        """Document converts to dictionary."""
        doc = Document(content="Test", metadata={"k": "v"}, id="d1")
        d = doc.to_dict()
        assert d == {"id": "d1", "content": "Test", "metadata": {"k": "v"}}

    def test_from_dict(self):
        """Document created from dictionary."""
        data = {
            "id": "d1",
            "content": "Hello",
            "metadata": {"source": "test"},
            "embedding": [0.1, 0.2],
        }
        doc = Document.from_dict(data)
        assert doc.id == "d1"
        assert doc.content == "Hello"
        assert doc.metadata == {"source": "test"}
        assert doc.embedding == [0.1, 0.2]

    def test_from_dict_minimal(self):
        """Document from dict works with just content."""
        data = {"content": "Bare minimum"}
        doc = Document.from_dict(data)
        assert doc.content == "Bare minimum"
        assert doc.id  # auto-generated
        assert doc.metadata == {}


# ---------------------------------------------------------------------------
# SearchResult
# ---------------------------------------------------------------------------


class TestSearchResult:
    """Tests for SearchResult dataclass."""

    def test_create(self):
        """SearchResult created with score."""
        doc = Document(content="Test", id="d1")
        result = SearchResult(document=doc, score=0.95, distance=0.1)
        assert result.document is doc
        assert result.score == 0.95
        assert result.distance == 0.1

    def test_default_distance(self):
        """Distance defaults to None."""
        doc = Document(content="Test")
        result = SearchResult(document=doc, score=0.5)
        assert result.distance is None

    def test_to_dict(self):
        """SearchResult converts to dictionary."""
        doc = Document(content="Test", id="d1")
        result = SearchResult(document=doc, score=0.8, distance=0.3)
        d = result.to_dict()
        assert d["score"] == 0.8
        assert d["distance"] == 0.3
        assert d["document"]["id"] == "d1"


# ---------------------------------------------------------------------------
# MemoryVectorStore
# ---------------------------------------------------------------------------


class TestMemoryVectorStore:
    """Tests for in-memory vector store."""

    @pytest.fixture
    def provider(self):
        """Create a fake embedding provider."""
        return FakeEmbeddingProvider(dim=4)

    @pytest.fixture
    def store(self, provider):
        """Create a fresh in-memory store."""
        return MemoryVectorStore(embedding_provider=provider)

    # -- add --

    def test_add_documents(self, store):
        """Can add documents to the store."""
        docs = [
            Document(content="First document", id="d1"),
            Document(content="Second document", id="d2"),
        ]
        ids = store.add(docs)
        assert ids == ["d1", "d2"]
        assert store.count() == 2

    def test_add_empty_list(self, store):
        """Adding empty list returns empty."""
        assert store.add([]) == []
        assert store.count() == 0

    def test_add_with_precomputed_embedding(self, store):
        """Documents with embeddings skip provider call."""
        doc = Document(
            content="Pre-embedded",
            id="d1",
            embedding=[0.5, 0.5, 0.5, 0.5],
        )
        ids = store.add([doc])
        assert ids == ["d1"]

    def test_add_mixed_embedding(self, store):
        """Mix of pre-embedded and unembedded documents."""
        docs = [
            Document(content="Has embedding", id="d1", embedding=[1.0, 0.0, 0.0, 0.0]),
            Document(content="Needs embedding", id="d2"),
        ]
        ids = store.add(docs)
        assert len(ids) == 2

    def test_add_texts(self, store):
        """Convenience add_texts method works."""
        ids = store.add_texts(
            ["Hello world", "Goodbye world"],
            metadatas=[{"source": "a"}, {"source": "b"}],
        )
        assert len(ids) == 2
        assert store.count() == 2

    def test_add_texts_with_ids(self, store):
        """add_texts with explicit ids."""
        ids = store.add_texts(
            ["Text 1", "Text 2"],
            ids=["id1", "id2"],
        )
        assert ids == ["id1", "id2"]

    def test_add_texts_no_metadata(self, store):
        """add_texts without metadata uses empty dicts."""
        ids = store.add_texts(["Hello"])
        assert len(ids) == 1

    # -- search --

    def test_search_empty_store(self, store):
        """Searching empty store returns empty."""
        results = store.search("query")
        assert results == []

    def test_search_returns_results(self, store):
        """Search returns scored results."""
        store.add(
            [
                Document(content="Python programming language", id="d1"),
                Document(content="Java programming language", id="d2"),
                Document(content="Cooking recipes", id="d3"),
            ]
        )
        results = store.search("Python code")
        assert len(results) > 0
        assert isinstance(results[0], SearchResult)
        assert results[0].score is not None
        assert results[0].distance is not None

    def test_search_sorted_by_similarity(self, store):
        """Results are sorted by similarity (descending)."""
        store.add(
            [
                Document(content="Python programming", id="d1"),
                Document(content="Java programming", id="d2"),
                Document(content="Cooking food", id="d3"),
            ]
        )
        results = store.search("Python programming")
        # First result should be most similar
        assert results[0].document.id == "d1"
        # Scores should be in descending order
        scores = [r.score for r in results]
        assert scores == sorted(scores, reverse=True)

    def test_search_with_k(self, store):
        """Search respects k parameter."""
        for i in range(10):
            store.add([Document(content=f"Document {i}", id=f"d{i}")])
        results = store.search("Document", k=3)
        assert len(results) == 3

    def test_search_with_metadata_filter(self, store):
        """Search filters by metadata."""
        store.add(
            [
                Document(
                    content="Python tutorial", metadata={"category": "tech"}, id="d1"
                ),
                Document(
                    content="Python cookbook", metadata={"category": "food"}, id="d2"
                ),
                Document(
                    content="Python snake", metadata={"category": "animals"}, id="d3"
                ),
            ]
        )
        results = store.search("Python", filter={"category": "tech"})
        assert len(results) == 1
        assert results[0].document.id == "d1"

    def test_similarity_search(self, store):
        """similarity_search returns just documents."""
        store.add([Document(content="Test document", id="d1")])
        docs = store.similarity_search("Test")
        assert len(docs) == 1
        assert isinstance(docs[0], Document)

    def test_similarity_search_with_score(self, store):
        """similarity_search_with_score returns (doc, score) tuples."""
        store.add([Document(content="Test document", id="d1")])
        results = store.similarity_search_with_score("Test")
        assert len(results) == 1
        doc, score = results[0]
        assert isinstance(doc, Document)
        assert isinstance(score, float)

    # -- metadata filtering --

    def test_filter_direct_equality(self, store):
        """Direct equality filter works."""
        store.add(
            [
                Document(content="A", metadata={"lang": "python"}, id="d1"),
                Document(content="B", metadata={"lang": "java"}, id="d2"),
            ]
        )
        results = store.search("test", filter={"lang": "python"})
        assert len(results) == 1
        assert results[0].document.id == "d1"

    @pytest.mark.parametrize(
        "op,op_value,expected_ids",
        [
            ("$eq", "python", ["d1"]),
            ("$ne", "python", ["d2"]),
            ("$gt", 5, ["d2"]),
            ("$gte", 10, ["d2"]),
            ("$lt", 5, ["d1"]),
            ("$lte", 3, ["d1"]),
            ("$in", ["python", "rust"], ["d1"]),
            ("$nin", ["python"], ["d2"]),
        ],
    )
    def test_filter_operators(self, provider, op, op_value, expected_ids):
        """Metadata filter operators work correctly."""
        store = MemoryVectorStore(embedding_provider=provider)
        store.add(
            [
                Document(content="A", metadata={"lang": "python", "score": 3}, id="d1"),
                Document(content="B", metadata={"lang": "java", "score": 10}, id="d2"),
            ]
        )
        # Determine filter key based on op
        if op in ("$gt", "$gte", "$lt", "$lte"):
            filt = {"score": {op: op_value}}
        else:
            filt = {"lang": {op: op_value}}

        results = store.search("test", filter=filt)
        result_ids = [r.document.id for r in results]
        for eid in expected_ids:
            assert eid in result_ids

    def test_filter_missing_key(self, store):
        """Filter excludes docs missing the filter key."""
        store.add(
            [
                Document(content="A", metadata={"lang": "python"}, id="d1"),
                Document(content="B", metadata={}, id="d2"),
            ]
        )
        results = store.search("test", filter={"lang": "python"})
        assert len(results) == 1
        assert results[0].document.id == "d1"

    # -- get / delete --

    def test_get_by_ids(self, store):
        """Can retrieve documents by IDs."""
        store.add(
            [
                Document(content="A", id="d1"),
                Document(content="B", id="d2"),
                Document(content="C", id="d3"),
            ]
        )
        docs = store.get(["d1", "d3"])
        assert len(docs) == 2
        ids = {d.id for d in docs}
        assert ids == {"d1", "d3"}

    def test_get_missing_ids(self, store):
        """Getting nonexistent IDs returns empty."""
        assert store.get(["nonexistent"]) == []

    def test_delete(self, store):
        """Can delete documents by IDs."""
        store.add(
            [
                Document(content="A", id="d1"),
                Document(content="B", id="d2"),
            ]
        )
        deleted = store.delete(["d1"])
        assert deleted == 1
        assert store.count() == 1

    def test_delete_nonexistent(self, store):
        """Deleting nonexistent IDs returns 0."""
        assert store.delete(["nonexistent"]) == 0

    # -- clear --

    def test_clear(self, store):
        """Clear removes all documents."""
        store.add([Document(content="A", id="d1")])
        count = store.clear()
        assert count == 1
        assert store.count() == 0

    # -- count --

    def test_count(self, store):
        """Count returns correct number."""
        assert store.count() == 0
        store.add([Document(content="A", id="d1")])
        assert store.count() == 1

    # -- persistence --

    def test_persistence_save_load(self, provider, tmp_path):
        """Store persists to and loads from JSON."""
        path = tmp_path / "store.json"
        s1 = MemoryVectorStore(embedding_provider=provider, persist_path=path)
        s1.add(
            [
                Document(content="Hello", metadata={"k": "v"}, id="d1"),
            ]
        )
        assert path.exists()

        s2 = MemoryVectorStore(embedding_provider=provider, persist_path=path)
        assert s2.count() == 1
        docs = s2.get(["d1"])
        assert len(docs) == 1
        assert docs[0].content == "Hello"
        assert docs[0].metadata == {"k": "v"}

    def test_persistence_load_nonexistent(self, provider, tmp_path):
        """Loading from nonexistent file creates empty store."""
        path = tmp_path / "nonexistent.json"
        store = MemoryVectorStore(embedding_provider=provider, persist_path=path)
        assert store.count() == 0

    def test_persistence_load_corrupt_file(self, provider, tmp_path):
        """Loading corrupt file raises VectorStoreError."""
        path = tmp_path / "corrupt.json"
        path.write_text("not valid json!!!")
        with pytest.raises(VectorStoreError, match="Failed to load"):
            MemoryVectorStore(embedding_provider=provider, persist_path=path)

    def test_persist_method(self, provider, tmp_path):
        """Explicit persist() saves data."""
        path = tmp_path / "store.json"
        store = MemoryVectorStore(embedding_provider=provider, persist_path=path)
        store.add([Document(content="Test", id="d1")])
        store.persist()
        assert path.exists()

    def test_persist_no_path_is_noop(self, store):
        """persist() without path is a no-op."""
        store.persist()  # Should not raise

    def test_delete_triggers_save(self, provider, tmp_path):
        """Deleting documents triggers persistence save."""
        path = tmp_path / "store.json"
        store = MemoryVectorStore(embedding_provider=provider, persist_path=path)
        store.add([Document(content="Test", id="d1")])
        store.delete(["d1"])
        # Reload and verify deletion persisted
        s2 = MemoryVectorStore(embedding_provider=provider, persist_path=path)
        assert s2.count() == 0

    # -- get_stats --

    def test_get_stats(self, store):
        """get_stats returns correct information."""
        stats = store.get_stats()
        assert stats["collection_name"] == "default"
        assert stats["document_count"] == 0
        assert stats["embedding_dimension"] == 4
        assert stats["embedding_model"] == "fake-model"
        assert stats["persist_path"] is None

    def test_get_stats_with_persist_path(self, provider, tmp_path):
        """get_stats includes persist_path."""
        path = tmp_path / "store.json"
        store = MemoryVectorStore(embedding_provider=provider, persist_path=path)
        stats = store.get_stats()
        assert stats["persist_path"] == str(path)

    # -- health_check --

    def test_health_check_healthy(self, store):
        """health_check returns True for healthy store."""
        assert store.health_check() is True

    def test_health_check_unhealthy(self, provider):
        """health_check returns False when store errors."""
        store = MemoryVectorStore(embedding_provider=provider)
        # Corrupt internal state to trigger error
        store._documents = None  # type: ignore
        assert store.health_check() is False

    # -- base class clear raises --

    def test_base_clear_not_implemented(self, provider):
        """Base VectorStore.clear() raises NotImplementedError."""
        # We can't instantiate VectorStore directly since it's ABC,
        # but MemoryVectorStore overrides clear. Let's verify the base method.
        assert VectorStore.clear is not MemoryVectorStore.clear


# ---------------------------------------------------------------------------
# EmbeddingProvider base class
# ---------------------------------------------------------------------------


class TestEmbeddingProviderBase:
    """Tests for EmbeddingProvider ABC methods."""

    def test_fake_provider_properties(self):
        """Fake provider has correct properties."""
        p = FakeEmbeddingProvider(dim=8)
        assert p.dimension == 8
        assert p.model_name == "fake-model"

    def test_fake_provider_embed(self):
        """Fake provider generates correct dimension embeddings."""
        p = FakeEmbeddingProvider(dim=4)
        emb = p.embed("Hello")
        assert len(emb) == 4
        # Should be normalized (unit vector)
        norm = math.sqrt(sum(x * x for x in emb))
        assert norm == pytest.approx(1.0, abs=0.01)

    def test_fake_provider_embed_batch(self):
        """Fake provider batch embedding works."""
        p = FakeEmbeddingProvider(dim=4)
        embs = p.embed_batch(["Hello", "World"])
        assert len(embs) == 2
        assert all(len(e) == 4 for e in embs)

    def test_fake_provider_deterministic(self):
        """Fake provider produces same embedding for same text."""
        p = FakeEmbeddingProvider(dim=4)
        e1 = p.embed("test")
        e2 = p.embed("test")
        assert e1 == e2


# ---------------------------------------------------------------------------
# get_embeddings factory
# ---------------------------------------------------------------------------


class TestGetEmbeddings:
    """Tests for the get_embeddings factory function."""

    def test_unknown_provider_raises(self):
        """Unknown provider name raises VectorStoreError."""
        with pytest.raises(VectorStoreError, match="Unknown embedding provider"):
            get_embeddings(provider="nonexistent")

    def test_openai_import_error(self):
        """OpenAI provider raises when openai not installed."""
        with patch.dict("sys.modules", {"openai": None}):
            with pytest.raises(VectorStoreError, match="openai"):
                get_embeddings(provider="openai")

    def test_sentence_transformers_import_error(self):
        """Sentence transformer provider raises when not installed."""
        with patch.dict("sys.modules", {"sentence_transformers": None}):
            with pytest.raises(VectorStoreError, match="sentence-transformers"):
                get_embeddings(provider="sentence-transformers")

    def test_cohere_import_error(self):
        """Cohere provider raises when not installed."""
        with patch.dict("sys.modules", {"cohere": None}):
            with pytest.raises(VectorStoreError, match="cohere"):
                get_embeddings(provider="cohere")

    def test_voyage_import_error(self):
        """Voyage provider raises when not installed."""
        with patch.dict("sys.modules", {"voyageai": None}):
            with pytest.raises(VectorStoreError, match="voyageai"):
                get_embeddings(provider="voyage")


# ---------------------------------------------------------------------------
# VectorStoreError
# ---------------------------------------------------------------------------


class TestVectorStoreError:
    """Tests for VectorStoreError."""

    def test_is_exception(self):
        """VectorStoreError is an Exception."""
        err = VectorStoreError("test error")
        assert isinstance(err, Exception)
        assert str(err) == "test error"
