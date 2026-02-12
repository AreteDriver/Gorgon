"""Tests for knowledge graph module.

Covers:
- Entity, Relation, Triple data classes
- GraphQuery matching logic
- MemoryKnowledgeGraph in-memory implementation
- SimpleEntityExtractor, CodeEntityExtractor
- LLMEntityExtractor (with mocked provider)
"""

import json
import sys
from datetime import datetime
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, "src")

from test_ai.knowledge.base import (
    Entity,
    EntityType,
    GraphQuery,
    Relation,
    Triple,
)
from test_ai.knowledge.extractors import (
    CodeEntityExtractor,
    LLMEntityExtractor,
    SimpleEntityExtractor,
)
from test_ai.knowledge.memory_graph import MemoryKnowledgeGraph


# ---------------------------------------------------------------------------
# Entity
# ---------------------------------------------------------------------------


class TestEntity:
    """Tests for Entity dataclass."""

    def test_create_with_defaults(self):
        """Entity created with default type and auto-generated id."""
        entity = Entity(name="Python")
        assert entity.name == "Python"
        assert entity.type == EntityType.CONCEPT
        assert entity.id  # auto-generated
        assert isinstance(entity.created_at, datetime)
        assert entity.properties == {}
        assert entity.embedding is None

    def test_create_with_all_fields(self):
        """Entity created with explicit values."""
        entity = Entity(
            name="Alice",
            type=EntityType.PERSON,
            properties={"age": 30},
            id="custom-id",
            embedding=[0.1, 0.2],
        )
        assert entity.name == "Alice"
        assert entity.type == EntityType.PERSON
        assert entity.properties == {"age": 30}
        assert entity.id == "custom-id"
        assert entity.embedding == [0.1, 0.2]

    def test_string_type(self):
        """Entity can use string type."""
        entity = Entity(name="Widget", type="custom_type")
        assert entity.type == "custom_type"

    def test_hash_by_id(self):
        """Entities hash by their id."""
        e1 = Entity(name="A", id="id-1")
        e2 = Entity(name="B", id="id-1")
        assert hash(e1) == hash(e2)

    def test_equality_by_id(self):
        """Entities are equal when ids match."""
        e1 = Entity(name="A", id="same")
        e2 = Entity(name="B", id="same")
        assert e1 == e2

    def test_inequality(self):
        """Entities with different ids are not equal."""
        e1 = Entity(name="A", id="id-1")
        e2 = Entity(name="A", id="id-2")
        assert e1 != e2

    def test_not_equal_to_non_entity(self):
        """Entity is not equal to non-Entity objects."""
        e = Entity(name="A", id="id-1")
        assert e != "id-1"
        assert e != 42
        assert e != None  # noqa: E711

    def test_to_dict(self):
        """Entity converts to dictionary."""
        entity = Entity(name="Alice", type=EntityType.PERSON, id="eid")
        d = entity.to_dict()
        assert d["id"] == "eid"
        assert d["name"] == "Alice"
        assert d["type"] == "person"
        assert "created_at" in d

    def test_to_dict_string_type(self):
        """Entity with string type converts correctly."""
        entity = Entity(name="X", type="custom", id="eid")
        d = entity.to_dict()
        assert d["type"] == "custom"

    def test_from_dict_with_known_type(self):
        """Entity.from_dict maps known types to EntityType enum."""
        data = {
            "id": "abc",
            "name": "Bob",
            "type": "person",
            "properties": {"role": "dev"},
            "created_at": "2024-01-01T00:00:00",
        }
        entity = Entity.from_dict(data)
        assert entity.id == "abc"
        assert entity.name == "Bob"
        assert entity.type == EntityType.PERSON
        assert entity.properties == {"role": "dev"}

    def test_from_dict_with_unknown_type(self):
        """Entity.from_dict keeps unknown types as strings."""
        data = {"name": "X", "type": "alien"}
        entity = Entity.from_dict(data)
        assert entity.type == "alien"

    def test_from_dict_without_optional_fields(self):
        """Entity.from_dict works with minimal data."""
        data = {"name": "Minimal"}
        entity = Entity.from_dict(data)
        assert entity.name == "Minimal"
        assert entity.type == EntityType.CONCEPT  # default
        assert entity.properties == {}
        assert entity.id  # auto-generated

    def test_from_dict_without_created_at(self):
        """Entity.from_dict generates created_at when missing."""
        data = {"name": "Test"}
        entity = Entity.from_dict(data)
        assert isinstance(entity.created_at, datetime)

    def test_entities_in_set(self):
        """Entities can be stored in sets (uses __hash__)."""
        e1 = Entity(name="A", id="id-1")
        e2 = Entity(name="B", id="id-2")
        e3 = Entity(name="C", id="id-1")  # same id as e1
        s = {e1, e2, e3}
        assert len(s) == 2


# ---------------------------------------------------------------------------
# Relation
# ---------------------------------------------------------------------------


class TestRelation:
    """Tests for Relation dataclass."""

    def test_create_basic(self):
        """Relation created with name."""
        r = Relation(name="works_at")
        assert r.name == "works_at"
        assert r.properties == {}
        assert r.inverse is None

    def test_create_with_inverse(self):
        """Relation created with inverse."""
        r = Relation(name="works_at", inverse="employs")
        assert r.inverse == "employs"

    def test_hash_by_name(self):
        """Relations hash by name."""
        r1 = Relation(name="works_at")
        r2 = Relation(name="works_at", properties={"weight": 1})
        assert hash(r1) == hash(r2)

    def test_equality(self):
        """Relations are equal when names match."""
        assert Relation(name="x") == Relation(name="x")
        assert Relation(name="x") != Relation(name="y")

    def test_not_equal_to_non_relation(self):
        """Relation is not equal to non-Relation objects."""
        r = Relation(name="x")
        assert r != "x"


# ---------------------------------------------------------------------------
# Triple
# ---------------------------------------------------------------------------


class TestTriple:
    """Tests for Triple dataclass."""

    @pytest.fixture
    def triple(self):
        """Create a sample triple."""
        s = Entity(name="Alice", type=EntityType.PERSON, id="s1")
        o = Entity(name="Acme", type=EntityType.ORGANIZATION, id="o1")
        return Triple(subject=s, relation="works_at", object=o, id="t1")

    def test_relation_name_from_string(self, triple):
        """relation_name returns string when relation is a string."""
        assert triple.relation_name == "works_at"

    def test_relation_name_from_relation_object(self):
        """relation_name extracts name from Relation object."""
        s = Entity(name="A", id="s")
        o = Entity(name="B", id="o")
        r = Relation(name="located_in")
        t = Triple(subject=s, relation=r, object=o)
        assert t.relation_name == "located_in"

    def test_to_dict(self, triple):
        """Triple converts to dictionary."""
        d = triple.to_dict()
        assert d["id"] == "t1"
        assert d["relation"] == "works_at"
        assert d["subject"]["name"] == "Alice"
        assert d["object"]["name"] == "Acme"
        assert "created_at" in d
        assert "properties" in d

    def test_str_representation(self, triple):
        """Triple has readable string representation."""
        s = str(triple)
        assert "Alice" in s
        assert "works_at" in s
        assert "Acme" in s


# ---------------------------------------------------------------------------
# GraphQuery
# ---------------------------------------------------------------------------


class TestGraphQuery:
    """Tests for GraphQuery matching logic."""

    @pytest.fixture
    def sample_triple(self):
        """A triple for query testing."""
        s = Entity(name="Alice", type=EntityType.PERSON, id="s1")
        o = Entity(name="Acme", type=EntityType.ORGANIZATION, id="o1")
        return Triple(subject=s, relation="works_at", object=o, id="t1")

    def test_empty_query_matches_all(self, sample_triple):
        """Query with no constraints matches everything."""
        q = GraphQuery()
        assert q.matches_triple(sample_triple) is True

    def test_match_subject_by_name(self, sample_triple):
        """Query matches subject by string name (case-insensitive)."""
        assert GraphQuery(subject="alice").matches_triple(sample_triple) is True
        assert GraphQuery(subject="ALICE").matches_triple(sample_triple) is True
        assert GraphQuery(subject="Bob").matches_triple(sample_triple) is False

    def test_match_subject_by_entity(self, sample_triple):
        """Query matches subject by Entity object (by id)."""
        assert (
            GraphQuery(subject=Entity(name="X", id="s1")).matches_triple(sample_triple)
            is True
        )
        assert (
            GraphQuery(subject=Entity(name="X", id="other")).matches_triple(
                sample_triple
            )
            is False
        )

    def test_match_object_by_name(self, sample_triple):
        """Query matches object by string name."""
        assert GraphQuery(object="Acme").matches_triple(sample_triple) is True
        assert GraphQuery(object="Other").matches_triple(sample_triple) is False

    def test_match_object_by_entity(self, sample_triple):
        """Query matches object by Entity object."""
        assert (
            GraphQuery(object=Entity(name="X", id="o1")).matches_triple(sample_triple)
            is True
        )
        assert (
            GraphQuery(object=Entity(name="X", id="wrong")).matches_triple(
                sample_triple
            )
            is False
        )

    def test_match_relation_by_string(self, sample_triple):
        """Query matches relation by string (case-insensitive)."""
        assert GraphQuery(relation="works_at").matches_triple(sample_triple) is True
        assert GraphQuery(relation="WORKS_AT").matches_triple(sample_triple) is True
        assert GraphQuery(relation="located_in").matches_triple(sample_triple) is False

    def test_match_relation_by_relation_object(self, sample_triple):
        """Query matches relation by Relation object."""
        r = Relation(name="works_at")
        assert GraphQuery(relation=r).matches_triple(sample_triple) is True

    def test_match_subject_type_enum(self, sample_triple):
        """Query matches subject type with EntityType enum."""
        assert (
            GraphQuery(subject_type=EntityType.PERSON).matches_triple(sample_triple)
            is True
        )
        assert (
            GraphQuery(subject_type=EntityType.LOCATION).matches_triple(sample_triple)
            is False
        )

    def test_match_subject_type_string(self, sample_triple):
        """Query matches subject type with string."""
        assert GraphQuery(subject_type="person").matches_triple(sample_triple) is True
        assert (
            GraphQuery(subject_type="location").matches_triple(sample_triple) is False
        )

    def test_match_object_type_enum(self, sample_triple):
        """Query matches object type with EntityType enum."""
        assert (
            GraphQuery(object_type=EntityType.ORGANIZATION).matches_triple(
                sample_triple
            )
            is True
        )
        assert (
            GraphQuery(object_type=EntityType.PERSON).matches_triple(sample_triple)
            is False
        )

    def test_match_object_type_string(self, sample_triple):
        """Query matches object type with string."""
        assert (
            GraphQuery(object_type="organization").matches_triple(sample_triple) is True
        )

    def test_match_subject_type_with_string_typed_entity(self):
        """Query matches when entity has a string type (not enum)."""
        s = Entity(name="Widget", type="custom_type", id="s")
        o = Entity(name="System", id="o")
        t = Triple(subject=s, relation="part_of", object=o)
        assert GraphQuery(subject_type="custom_type").matches_triple(t) is True
        assert GraphQuery(subject_type="other").matches_triple(t) is False

    def test_combined_filters(self, sample_triple):
        """Query with multiple filters requires all to match."""
        q = GraphQuery(subject="alice", relation="works_at", object="acme")
        assert q.matches_triple(sample_triple) is True

        q = GraphQuery(subject="alice", relation="located_in")
        assert q.matches_triple(sample_triple) is False


# ---------------------------------------------------------------------------
# MemoryKnowledgeGraph
# ---------------------------------------------------------------------------


class TestMemoryKnowledgeGraph:
    """Tests for in-memory knowledge graph."""

    @pytest.fixture
    def graph(self):
        """Create a fresh in-memory graph."""
        return MemoryKnowledgeGraph()

    @pytest.fixture
    def populated_graph(self):
        """Create a graph with sample data."""
        g = MemoryKnowledgeGraph()
        g.add(
            "Alice",
            "works_at",
            "Acme",
            subject_type=EntityType.PERSON,
            object_type=EntityType.ORGANIZATION,
        )
        g.add(
            "Bob",
            "works_at",
            "Acme",
            subject_type=EntityType.PERSON,
            object_type=EntityType.ORGANIZATION,
        )
        g.add("Acme", "located_in", "NYC", object_type=EntityType.LOCATION)
        return g

    # -- add / get entities --

    def test_add_entity(self, graph):
        """Can add an entity."""
        e = Entity(name="Python", type=EntityType.CONCEPT, id="e1")
        eid = graph.add_entity(e)
        assert eid == "e1"
        assert graph.count_entities() == 1

    def test_get_entity_by_id(self, graph):
        """Can retrieve entity by id."""
        e = Entity(name="Python", id="e1")
        graph.add_entity(e)
        assert graph.get_entity("e1") is e

    def test_get_entity_not_found(self, graph):
        """Returns None for unknown id."""
        assert graph.get_entity("nonexistent") is None

    def test_get_entity_by_name(self, graph):
        """Can retrieve entity by name (case-insensitive)."""
        e = Entity(name="Python", id="e1")
        graph.add_entity(e)
        assert graph.get_entity_by_name("python") is e
        assert graph.get_entity_by_name("PYTHON") is e

    def test_get_entity_by_name_not_found(self, graph):
        """Returns None for unknown name."""
        assert graph.get_entity_by_name("nonexistent") is None

    def test_get_entities_by_type(self, populated_graph):
        """Can filter entities by type."""
        people = populated_graph.get_entities_by_type(EntityType.PERSON)
        assert len(people) == 2
        names = {p.name for p in people}
        assert names == {"Alice", "Bob"}

    def test_get_entities_by_type_string(self, populated_graph):
        """Can filter entities by string type."""
        locs = populated_graph.get_entities_by_type("location")
        assert len(locs) == 1

    def test_get_entities_by_type_empty(self, graph):
        """Returns empty list when no entities of that type."""
        result = graph.get_entities_by_type(EntityType.EVENT)
        assert result == []

    # -- add / get triples --

    def test_add_triple(self, graph):
        """Can add a triple."""
        s = Entity(name="A", id="s1")
        o = Entity(name="B", id="o1")
        t = Triple(subject=s, relation="knows", object=o, id="t1")
        tid = graph.add_triple(t)
        assert tid == "t1"
        assert graph.count_triples() == 1

    def test_add_triple_auto_adds_entities(self, graph):
        """Adding a triple auto-adds its entities."""
        s = Entity(name="A", id="s1")
        o = Entity(name="B", id="o1")
        t = Triple(subject=s, relation="knows", object=o)
        graph.add_triple(t)
        assert graph.count_entities() == 2
        assert graph.get_entity("s1") is not None

    def test_add_triple_does_not_duplicate_entities(self, graph):
        """Adding triple doesn't duplicate existing entities."""
        s = Entity(name="A", id="s1")
        o = Entity(name="B", id="o1")
        graph.add_entity(s)
        graph.add_entity(o)
        t = Triple(subject=s, relation="knows", object=o)
        graph.add_triple(t)
        assert graph.count_entities() == 2

    # -- convenience add --

    def test_convenience_add_strings(self, graph):
        """Convenience add creates entities from strings."""
        triple = graph.add("Alice", "knows", "Bob")
        assert triple.subject.name == "Alice"
        assert triple.object.name == "Bob"
        assert graph.count_entities() == 2
        assert graph.count_triples() == 1

    def test_convenience_add_with_entity_objects(self, graph):
        """Convenience add accepts Entity objects."""
        alice = Entity(name="Alice", id="a1")
        bob = Entity(name="Bob", id="b1")
        triple = graph.add(alice, "knows", bob)
        assert triple.subject.id == "a1"
        assert triple.object.id == "b1"

    def test_convenience_add_reuses_existing_entities(self, graph):
        """Convenience add reuses existing entities by name."""
        graph.add("Alice", "knows", "Bob")
        graph.add("Alice", "works_with", "Bob")
        assert graph.count_entities() == 2  # not 4

    def test_convenience_add_with_types(self, graph):
        """Convenience add applies entity types."""
        graph.add(
            "Alice",
            "works_at",
            "Acme",
            subject_type=EntityType.PERSON,
            object_type=EntityType.ORGANIZATION,
        )
        alice = graph.get_entity_by_name("Alice")
        assert alice.type == EntityType.PERSON

    def test_convenience_add_with_properties(self, graph):
        """Convenience add passes properties to triple."""
        triple = graph.add("A", "r", "B", confidence=0.9, source="test")
        assert triple.properties["confidence"] == 0.9
        assert triple.properties["source"] == "test"

    # -- query --

    def test_query_all(self, populated_graph):
        """Empty query returns all triples."""
        results = populated_graph.query(GraphQuery())
        assert len(results) == 3

    def test_query_by_subject_string(self, populated_graph):
        """Query by subject name."""
        results = populated_graph.query(GraphQuery(subject="Alice"))
        assert len(results) == 1
        assert results[0].subject.name == "Alice"

    def test_query_by_subject_entity(self, populated_graph):
        """Query by subject Entity object."""
        alice = populated_graph.get_entity_by_name("Alice")
        results = populated_graph.query(GraphQuery(subject=alice))
        assert len(results) == 1

    def test_query_by_object_string(self, populated_graph):
        """Query by object name."""
        results = populated_graph.query(GraphQuery(object="Acme"))
        assert len(results) == 2  # Alice and Bob work at Acme

    def test_query_by_object_entity(self, populated_graph):
        """Query by object Entity object."""
        acme = populated_graph.get_entity_by_name("Acme")
        results = populated_graph.query(GraphQuery(object=acme))
        assert len(results) == 2

    def test_query_by_relation_string(self, populated_graph):
        """Query by relation name."""
        results = populated_graph.query(GraphQuery(relation="works_at"))
        assert len(results) == 2

    def test_query_by_relation_object(self, populated_graph):
        """Query by Relation object."""
        r = Relation(name="works_at")
        results = populated_graph.query(GraphQuery(relation=r))
        assert len(results) == 2

    def test_query_with_limit(self, populated_graph):
        """Query respects limit."""
        results = populated_graph.query(GraphQuery(limit=1))
        assert len(results) == 1

    def test_query_no_results(self, populated_graph):
        """Query returns empty when nothing matches."""
        results = populated_graph.query(GraphQuery(subject="Unknown"))
        assert results == []

    def test_query_combined_subject_and_relation(self, populated_graph):
        """Query with subject + relation uses index intersection."""
        results = populated_graph.query(
            GraphQuery(subject="Alice", relation="works_at")
        )
        assert len(results) == 1

    def test_query_combined_subject_and_object(self, populated_graph):
        """Query with subject + object uses index intersection."""
        results = populated_graph.query(GraphQuery(subject="Alice", object="Acme"))
        assert len(results) == 1

    # -- delete --

    def test_delete_entity(self, graph):
        """Deleting entity removes it and its triples."""
        graph.add("A", "knows", "B")
        a = graph.get_entity_by_name("A")
        assert graph.delete_entity(a.id) is True
        assert graph.count_entities() == 1  # B remains
        assert graph.count_triples() == 0

    def test_delete_entity_not_found(self, graph):
        """Deleting nonexistent entity returns False."""
        assert graph.delete_entity("nonexistent") is False

    def test_delete_triple(self, graph):
        """Can delete a specific triple."""
        triple = graph.add("A", "knows", "B")
        assert graph.delete_triple(triple.id) is True
        assert graph.count_triples() == 0
        # Entities remain
        assert graph.count_entities() == 2

    def test_delete_triple_not_found(self, graph):
        """Deleting nonexistent triple returns False."""
        assert graph.delete_triple("nonexistent") is False

    # -- clear --

    def test_clear(self, populated_graph):
        """Clear removes all data."""
        populated_graph.clear()
        assert populated_graph.count_entities() == 0
        assert populated_graph.count_triples() == 0

    # -- get_relations --

    def test_get_relations(self, populated_graph):
        """Get all relations for an entity."""
        relations = populated_graph.get_relations("Acme")
        # Acme is object of 2 "works_at" + subject of 1 "located_in"
        assert len(relations) == 3

    def test_get_relations_by_entity_object(self, populated_graph):
        """Get relations using Entity object."""
        acme = populated_graph.get_entity_by_name("Acme")
        relations = populated_graph.get_relations(acme)
        assert len(relations) == 3

    def test_get_relations_not_found(self, graph):
        """Get relations for unknown entity returns empty."""
        assert graph.get_relations("Unknown") == []

    # -- get_neighbors --

    def test_get_neighbors(self, populated_graph):
        """Get neighboring entities within 1 hop."""
        neighbors = populated_graph.get_neighbors("Acme", hops=1)
        names = {n.name for n in neighbors}
        assert "Alice" in names
        assert "Bob" in names
        assert "NYC" in names
        assert "Acme" not in names  # starting entity excluded

    def test_get_neighbors_multi_hop(self, populated_graph):
        """Get neighbors within 2 hops."""
        neighbors = populated_graph.get_neighbors("Alice", hops=2)
        names = {n.name for n in neighbors}
        # Alice -> Acme -> {Bob, NYC}
        assert "Acme" in names
        assert "Bob" in names
        assert "NYC" in names

    def test_get_neighbors_not_found(self, graph):
        """Get neighbors for unknown entity returns empty."""
        assert graph.get_neighbors("Unknown") == set()

    # -- to_context --

    def test_to_context(self, populated_graph):
        """Convert entity knowledge to text context."""
        ctx = populated_graph.to_context("Alice")
        assert "Alice" in ctx
        assert "works_at" in ctx

    def test_to_context_with_properties(self, graph):
        """Context includes entity properties."""
        e = Entity(name="Alice", properties={"role": "engineer"}, id="a1")
        graph.add_entity(e)
        ctx = graph.to_context(e)
        assert "role" in ctx
        assert "engineer" in ctx

    def test_to_context_not_found(self, graph):
        """Context for unknown entity returns helpful message."""
        ctx = graph.to_context("Unknown")
        assert "No information found" in ctx

    def test_to_context_limits_relations(self, graph):
        """Context respects max_relations."""
        for i in range(20):
            graph.add("Alice", f"rel_{i}", f"Target_{i}")
        ctx = graph.to_context("Alice", max_relations=5)
        # Should not include all 20
        assert ctx.count("rel_") <= 5

    def test_to_context_entity_as_object(self, graph):
        """Context shows relations where entity is the object."""
        graph.add("Bob", "knows", "Alice")
        ctx = graph.to_context("Alice")
        assert "Bob" in ctx

    # -- find_path --

    def test_find_path_direct(self, populated_graph):
        """Find direct path between connected entities."""
        path = populated_graph.find_path("Alice", "Acme")
        assert path is not None
        assert len(path) == 1
        assert path[0].relation_name == "works_at"

    def test_find_path_indirect(self, populated_graph):
        """Find indirect path through intermediate entities."""
        path = populated_graph.find_path("Alice", "NYC")
        assert path is not None
        assert len(path) == 2

    def test_find_path_same_entity(self, populated_graph):
        """Path from entity to itself is empty."""
        path = populated_graph.find_path("Alice", "Alice")
        assert path == []

    def test_find_path_not_found(self, graph):
        """Returns None when no path exists."""
        graph.add("A", "knows", "B")
        graph.add("C", "knows", "D")
        assert graph.find_path("A", "D") is None

    def test_find_path_unknown_start(self, graph):
        """Returns None for unknown start entity."""
        assert graph.find_path("Unknown", "B") is None

    def test_find_path_unknown_end(self, graph):
        """Returns None for unknown end entity."""
        graph.add("A", "knows", "B")
        assert graph.find_path("A", "Unknown") is None

    def test_find_path_with_entity_objects(self, populated_graph):
        """find_path works with Entity objects."""
        alice = populated_graph.get_entity_by_name("Alice")
        acme = populated_graph.get_entity_by_name("Acme")
        path = populated_graph.find_path(alice, acme)
        assert path is not None
        assert len(path) == 1

    def test_find_path_respects_max_hops(self, graph):
        """find_path stops at max_hops."""
        # Chain: A -> B -> C -> D
        graph.add("A", "next", "B")
        graph.add("B", "next", "C")
        graph.add("C", "next", "D")
        assert graph.find_path("A", "D", max_hops=2) is None
        assert graph.find_path("A", "D", max_hops=3) is not None

    # -- get_subgraph --

    def test_get_subgraph(self, populated_graph):
        """Extract subgraph around an entity."""
        sub = populated_graph.get_subgraph("Acme", hops=1)
        assert sub.count_entities() >= 3
        assert sub.count_triples() >= 1

    def test_get_subgraph_unknown(self, graph):
        """Subgraph for unknown entity returns empty graph."""
        sub = graph.get_subgraph("Unknown")
        assert sub.count_entities() == 0

    def test_get_subgraph_entity_object(self, populated_graph):
        """get_subgraph works with Entity object."""
        acme = populated_graph.get_entity_by_name("Acme")
        sub = populated_graph.get_subgraph(acme, hops=1)
        assert sub.count_entities() >= 3

    # -- merge_from --

    def test_merge_from(self, graph):
        """Merge another graph into this one."""
        other = MemoryKnowledgeGraph()
        other.add("X", "knows", "Y")
        graph.add("A", "knows", "B")

        entities_added, triples_added = graph.merge_from(other)
        assert entities_added == 2
        assert triples_added == 1
        assert graph.count_entities() == 4

    def test_merge_from_no_duplicates(self, graph):
        """Merge doesn't duplicate existing entities/triples."""
        graph.add("A", "knows", "B")
        other = MemoryKnowledgeGraph()
        # Add same entities with same IDs
        a = graph.get_entity_by_name("A")
        b = graph.get_entity_by_name("B")
        other.add_entity(a)
        other.add_entity(b)

        entities_added, triples_added = graph.merge_from(other)
        assert entities_added == 0

    # -- persistence --

    def test_persistence_save_load(self, tmp_path):
        """Graph persists to and loads from JSON."""
        path = tmp_path / "graph.json"
        g1 = MemoryKnowledgeGraph(persist_path=path)
        g1.add("Alice", "knows", "Bob")
        assert path.exists()

        g2 = MemoryKnowledgeGraph(persist_path=path)
        assert g2.count_entities() == 2
        assert g2.count_triples() == 1

    def test_persistence_load_nonexistent(self, tmp_path):
        """Loading from nonexistent file creates empty graph."""
        path = tmp_path / "nonexistent.json"
        g = MemoryKnowledgeGraph(persist_path=path)
        assert g.count_entities() == 0

    def test_no_persistence_path(self, graph):
        """Graph works without persistence path."""
        graph.add("A", "knows", "B")
        assert graph.count_entities() == 2

    # -- to_dict --

    def test_to_dict(self, populated_graph):
        """Graph converts to dictionary."""
        d = populated_graph.to_dict()
        assert "entities" in d
        assert "triples" in d
        assert len(d["entities"]) == populated_graph.count_entities()
        assert len(d["triples"]) == populated_graph.count_triples()

    # -- get_stats --

    def test_get_stats(self, populated_graph):
        """Graph stats report counts correctly."""
        stats = populated_graph.get_stats()
        assert stats["entity_count"] == populated_graph.count_entities()
        assert stats["triple_count"] == 3
        assert "entity_types" in stats
        assert "relation_types" in stats
        assert "person" in stats["entity_types"]
        assert "works_at" in stats["relation_types"]


# ---------------------------------------------------------------------------
# SimpleEntityExtractor
# ---------------------------------------------------------------------------


class TestSimpleEntityExtractor:
    """Tests for rule-based entity extraction."""

    def test_default_patterns_extract_names(self):
        """Default patterns find capitalized multi-word names."""
        extractor = SimpleEntityExtractor()
        entities = extractor.extract_entities("John Smith works at Acme Corp.")
        names = {e.name for e in entities}
        assert "John Smith" in names

    def test_default_patterns_extract_orgs(self):
        """Default patterns find all-caps organizations."""
        extractor = SimpleEntityExtractor()
        entities = extractor.extract_entities("NASA launched the rocket.")
        names = {e.name for e in entities}
        assert "NASA" in names

    def test_default_patterns_extract_code(self):
        """Default patterns extract code definitions."""
        extractor = SimpleEntityExtractor()
        entities = extractor.extract_entities("def calculate_total(items):")
        names = {e.name for e in entities}
        assert "calculate_total" in names

    def test_gazetteer(self):
        """Gazetteer matches known entities."""
        gazetteer = {
            "Python": EntityType.CONCEPT,
            "Google": EntityType.ORGANIZATION,
        }
        extractor = SimpleEntityExtractor(gazetteer=gazetteer)
        entities = extractor.extract_entities("I use Python and Google Cloud.")
        names = {e.name for e in entities}
        assert "Python" in names
        assert "Google" in names

    def test_deduplication(self):
        """Same entity name not extracted twice."""
        extractor = SimpleEntityExtractor()
        text = "NASA is great. NASA launches rockets."
        entities = extractor.extract_entities(text)
        nasa_count = sum(1 for e in entities if e.name == "NASA")
        assert nasa_count == 1

    def test_custom_patterns(self):
        """Custom regex patterns work."""
        patterns = {r"\b\d{4}\b": EntityType.EVENT}  # 4-digit numbers as events
        extractor = SimpleEntityExtractor(patterns=patterns)
        entities = extractor.extract_entities("The event in 2024 was great.")
        names = {e.name for e in entities}
        assert "2024" in names

    def test_empty_text(self):
        """No entities from empty text."""
        extractor = SimpleEntityExtractor()
        assert extractor.extract_entities("") == []

    def test_gazetteer_case_insensitive(self):
        """Gazetteer matching is case-insensitive."""
        gazetteer = {"python": EntityType.CONCEPT}
        extractor = SimpleEntityExtractor(gazetteer=gazetteer)
        entities = extractor.extract_entities("I love PYTHON programming.")
        assert len(entities) >= 1
        names_lower = {e.name.lower() for e in entities}
        assert "python" in names_lower


# ---------------------------------------------------------------------------
# CodeEntityExtractor
# ---------------------------------------------------------------------------


class TestCodeEntityExtractor:
    """Tests for code entity extraction."""

    def test_python_class(self):
        """Extracts Python class names."""
        extractor = CodeEntityExtractor(language="python")
        code = "class MyClass:\n    pass"
        entities = extractor.extract_entities(code)
        names = {e.name for e in entities}
        assert "MyClass" in names

    def test_python_function(self):
        """Extracts Python function names."""
        extractor = CodeEntityExtractor(language="python")
        code = "def my_function(x):\n    return x"
        entities = extractor.extract_entities(code)
        names = {e.name for e in entities}
        assert "my_function" in names

    def test_python_import(self):
        """Extracts Python imports."""
        extractor = CodeEntityExtractor(language="python")
        code = "from pathlib import Path\nimport json"
        entities = extractor.extract_entities(code)
        names = {e.name for e in entities}
        assert "Path" in names or "pathlib" in names
        assert "json" in names

    def test_python_variable(self):
        """Extracts Python variables."""
        extractor = CodeEntityExtractor(language="python")
        code = "MAX_RETRIES = 3"
        entities = extractor.extract_entities(code)
        names = {e.name for e in entities}
        assert "MAX_RETRIES" in names

    def test_javascript_class(self):
        """Extracts JavaScript class names."""
        extractor = CodeEntityExtractor(language="javascript")
        code = "class UserService {\n  constructor() {}\n}"
        entities = extractor.extract_entities(code)
        names = {e.name for e in entities}
        assert "UserService" in names

    def test_javascript_function(self):
        """Extracts JavaScript function names."""
        extractor = CodeEntityExtractor(language="javascript")
        code = "function processData(items) { return items; }"
        entities = extractor.extract_entities(code)
        names = {e.name for e in entities}
        assert "processData" in names

    def test_typescript_interface(self):
        """Extracts TypeScript interface names."""
        extractor = CodeEntityExtractor(language="typescript")
        code = "interface UserProfile { name: string; }"
        entities = extractor.extract_entities(code)
        names = {e.name for e in entities}
        assert "UserProfile" in names

    def test_typescript_type(self):
        """Extracts TypeScript type aliases."""
        extractor = CodeEntityExtractor(language="typescript")
        code = "type Result = Success | Failure;"
        entities = extractor.extract_entities(code)
        names = {e.name for e in entities}
        assert "Result" in names

    def test_unknown_language_falls_back_to_python(self):
        """Unknown language defaults to Python patterns."""
        extractor = CodeEntityExtractor(language="cobol")
        code = "def hello():\n    pass"
        entities = extractor.extract_entities(code)
        names = {e.name for e in entities}
        assert "hello" in names

    def test_entities_have_code_type(self):
        """All extracted entities are marked as CODE type."""
        extractor = CodeEntityExtractor()
        entities = extractor.extract_entities("class Foo:\n    pass")
        for e in entities:
            assert e.type == EntityType.CODE

    def test_entities_have_language_property(self):
        """Entities include language in properties."""
        extractor = CodeEntityExtractor(language="python")
        entities = extractor.extract_entities("class Foo:\n    pass")
        for e in entities:
            assert e.properties["language"] == "python"

    def test_deduplication(self):
        """Same name not extracted twice."""
        extractor = CodeEntityExtractor(language="python")
        code = "class Foo:\n    pass\nclass Foo:\n    pass"
        entities = extractor.extract_entities(code)
        foo_count = sum(1 for e in entities if e.name == "Foo")
        assert foo_count == 1

    def test_empty_code(self):
        """No entities from empty code."""
        extractor = CodeEntityExtractor()
        assert extractor.extract_entities("") == []


# ---------------------------------------------------------------------------
# LLMEntityExtractor
# ---------------------------------------------------------------------------


class TestLLMEntityExtractor:
    """Tests for LLM-based extraction (provider mocked)."""

    @pytest.fixture
    def mock_provider(self):
        """Create a mock LLM provider."""
        provider = MagicMock()
        return provider

    @pytest.fixture
    def extractor(self, mock_provider):
        """Create LLM extractor with mocked provider."""
        return LLMEntityExtractor(provider=mock_provider)

    def _mock_response(self, provider, content):
        """Helper to set up mocked provider response."""
        response = MagicMock()
        response.content = content
        provider.complete.return_value = response

    def test_extract_entities(self, extractor, mock_provider):
        """Extracts entities from LLM JSON response."""
        self._mock_response(
            mock_provider,
            json.dumps(
                [
                    {
                        "name": "Alice",
                        "type": "person",
                        "properties": {"role": "engineer"},
                    },
                    {"name": "Acme", "type": "organization", "properties": {}},
                ]
            ),
        )
        entities = extractor.extract_entities("Alice works at Acme.")
        assert len(entities) == 2
        assert entities[0].name == "Alice"
        assert entities[0].type == EntityType.PERSON
        assert entities[1].name == "Acme"
        assert entities[1].type == EntityType.ORGANIZATION

    def test_extract_entities_unknown_type(self, extractor, mock_provider):
        """Unknown entity type kept as string."""
        self._mock_response(
            mock_provider,
            json.dumps([{"name": "Widget", "type": "gadget"}]),
        )
        entities = extractor.extract_entities("The Widget is useful.")
        assert len(entities) == 1
        assert entities[0].type == "gadget"

    def test_extract_entities_error_returns_empty(self, extractor, mock_provider):
        """Provider error returns empty list."""
        mock_provider.complete.side_effect = RuntimeError("API error")
        entities = extractor.extract_entities("Some text")
        assert entities == []

    def test_extract_entities_invalid_json(self, extractor, mock_provider):
        """Invalid JSON response returns empty list."""
        self._mock_response(mock_provider, "not json at all %%%")
        entities = extractor.extract_entities("Some text")
        assert entities == []

    def test_extract_entities_non_list_response(self, extractor, mock_provider):
        """Non-list JSON response returns empty list."""
        self._mock_response(mock_provider, json.dumps({"error": "nope"}))
        entities = extractor.extract_entities("Some text")
        assert entities == []

    def test_extract_entities_items_without_name(self, extractor, mock_provider):
        """Items without 'name' key are skipped."""
        self._mock_response(
            mock_provider,
            json.dumps(
                [
                    {"name": "Valid", "type": "concept"},
                    {"type": "concept"},  # no name
                    "not a dict",
                ]
            ),
        )
        entities = extractor.extract_entities("Test")
        assert len(entities) == 1
        assert entities[0].name == "Valid"

    def test_extract_relations(self, extractor, mock_provider):
        """Extracts relations from LLM JSON response."""
        # First call: entities, second call: relations
        responses = [
            MagicMock(
                content=json.dumps(
                    [
                        {"name": "Alice", "type": "person"},
                        {"name": "Acme", "type": "organization"},
                    ]
                )
            ),
            MagicMock(
                content=json.dumps(
                    [
                        {"subject": "Alice", "relation": "works_at", "object": "Acme"},
                    ]
                )
            ),
        ]
        mock_provider.complete.side_effect = responses

        triples = extractor.extract_relations("Alice works at Acme.")
        assert len(triples) == 1
        assert triples[0].subject.name == "Alice"
        assert triples[0].relation == "works_at"
        assert triples[0].object.name == "Acme"

    def test_extract_relations_with_provided_entities(self, extractor, mock_provider):
        """Uses provided entities instead of extracting them."""
        self._mock_response(
            mock_provider,
            json.dumps(
                [
                    {"subject": "Alice", "relation": "knows", "object": "Bob"},
                ]
            ),
        )
        entities = [
            Entity(name="Alice", type=EntityType.PERSON),
            Entity(name="Bob", type=EntityType.PERSON),
        ]
        triples = extractor.extract_relations("Alice knows Bob.", entities=entities)
        assert len(triples) == 1

    def test_extract_relations_empty_entities(self, extractor, mock_provider):
        """Returns empty when no entities found/provided."""
        self._mock_response(mock_provider, json.dumps([]))
        triples = extractor.extract_relations("text", entities=[])
        assert triples == []

    def test_extract_relations_creates_missing_entities(self, extractor, mock_provider):
        """Creates entities for names not in provided list."""
        self._mock_response(
            mock_provider,
            json.dumps(
                [
                    {"subject": "Alice", "relation": "knows", "object": "Charlie"},
                ]
            ),
        )
        entities = [Entity(name="Alice", type=EntityType.PERSON)]
        triples = extractor.extract_relations("Alice knows Charlie.", entities=entities)
        assert triples[0].object.name == "Charlie"

    def test_extract_relations_skips_incomplete_items(self, extractor, mock_provider):
        """Skips relation items with missing fields."""
        self._mock_response(
            mock_provider,
            json.dumps(
                [
                    {"subject": "A", "relation": "r", "object": "B"},  # valid
                    {"subject": "A", "relation": ""},  # missing object + empty relation
                    {"subject": "", "relation": "r", "object": "B"},  # empty subject
                    "not a dict",  # not a dict
                ]
            ),
        )
        entities = [Entity(name="A"), Entity(name="B")]
        triples = extractor.extract_relations("text", entities=entities)
        assert len(triples) == 1

    def test_extract_relations_error_returns_empty(self, extractor, mock_provider):
        """Provider error returns empty list."""
        mock_provider.complete.side_effect = [
            MagicMock(content=json.dumps([{"name": "A", "type": "concept"}])),
            RuntimeError("API error"),
        ]
        triples = extractor.extract_relations("text")
        assert triples == []

    def test_extract_knowledge(self, extractor, mock_provider):
        """extract_knowledge returns both entities and triples."""
        responses = [
            MagicMock(
                content=json.dumps(
                    [
                        {"name": "Alice", "type": "person"},
                        {"name": "Acme", "type": "organization"},
                    ]
                )
            ),
            MagicMock(
                content=json.dumps(
                    [
                        {"subject": "Alice", "relation": "works_at", "object": "Acme"},
                    ]
                )
            ),
        ]
        mock_provider.complete.side_effect = responses

        entities, triples = extractor.extract_knowledge("Alice works at Acme.")
        assert len(entities) == 2
        assert len(triples) == 1

    def test_custom_prompts(self, mock_provider):
        """Custom prompts are used instead of defaults."""
        custom_entity = "Custom entity prompt: {text}"
        custom_relation = "Custom relation prompt: {text} {entities}"
        extractor = LLMEntityExtractor(
            provider=mock_provider,
            entity_prompt=custom_entity,
            relation_prompt=custom_relation,
        )
        self._mock_response(
            mock_provider,
            json.dumps([{"name": "X", "type": "concept"}]),
        )
        extractor.extract_entities("test")
        # Verify the custom prompt was formatted and sent
        call_args = mock_provider.complete.call_args
        request = call_args[0][0]
        assert "Custom entity prompt" in request.prompt

    def test_parse_json_embedded_in_text(self, extractor, mock_provider):
        """Parser extracts JSON array embedded in surrounding text."""
        self._mock_response(
            mock_provider,
            'Here are the entities:\n[{"name": "Test", "type": "concept"}]\nDone.',
        )
        entities = extractor.extract_entities("test")
        assert len(entities) == 1

    def test_parse_json_object(self, extractor, mock_provider):
        """Parser extracts JSON object embedded in text."""
        result = extractor._parse_json_response('Result: {"key": "value"} end')
        assert result == {"key": "value"}

    def test_parse_json_returns_none_for_garbage(self, extractor):
        """Parser returns None for unparseable text."""
        assert extractor._parse_json_response("no json here at all") is None
