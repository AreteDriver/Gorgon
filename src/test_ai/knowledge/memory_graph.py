"""In-memory knowledge graph implementation."""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from .base import (
    Entity,
    EntityType,
    Relation,
    Triple,
    GraphQuery,
    KnowledgeGraph,
)


class MemoryKnowledgeGraph(KnowledgeGraph):
    """In-memory knowledge graph for development and small datasets.

    Stores entities and triples in memory with optional persistence.

    Features:
        - Fast in-memory operations
        - Index by entity name and type
        - Index by relation type
        - JSON persistence
        - Path queries
    """

    def __init__(self, persist_path: str | Path | None = None):
        """Initialize in-memory knowledge graph.

        Args:
            persist_path: Optional path for JSON persistence
        """
        self._entities: dict[str, Entity] = {}
        self._triples: dict[str, Triple] = {}

        # Indexes
        self._entity_by_name: dict[str, str] = {}  # name -> id
        self._entity_by_type: dict[str, set[str]] = defaultdict(set)  # type -> ids
        self._triples_by_subject: dict[str, set[str]] = defaultdict(set)  # entity_id -> triple_ids
        self._triples_by_object: dict[str, set[str]] = defaultdict(set)  # entity_id -> triple_ids
        self._triples_by_relation: dict[str, set[str]] = defaultdict(set)  # relation -> triple_ids

        self._persist_path = Path(persist_path) if persist_path else None

        # Load from disk if exists
        if self._persist_path and self._persist_path.exists():
            self._load()

    def add_entity(self, entity: Entity) -> str:
        """Add an entity to the graph."""
        self._entities[entity.id] = entity

        # Update indexes
        name_key = entity.name.lower()
        self._entity_by_name[name_key] = entity.id

        type_key = (
            entity.type.value if isinstance(entity.type, EntityType) else entity.type
        )
        self._entity_by_type[type_key].add(entity.id)

        self._save_if_needed()
        return entity.id

    def add_triple(self, triple: Triple) -> str:
        """Add a triple to the graph."""
        # Ensure entities exist
        if triple.subject.id not in self._entities:
            self.add_entity(triple.subject)
        if triple.object.id not in self._entities:
            self.add_entity(triple.object)

        self._triples[triple.id] = triple

        # Update indexes
        self._triples_by_subject[triple.subject.id].add(triple.id)
        self._triples_by_object[triple.object.id].add(triple.id)
        self._triples_by_relation[triple.relation_name.lower()].add(triple.id)

        self._save_if_needed()
        return triple.id

    def get_entity(self, entity_id: str) -> Entity | None:
        """Get an entity by ID."""
        return self._entities.get(entity_id)

    def get_entity_by_name(self, name: str) -> Entity | None:
        """Get an entity by name."""
        entity_id = self._entity_by_name.get(name.lower())
        if entity_id:
            return self._entities.get(entity_id)
        return None

    def get_entities_by_type(self, entity_type: EntityType | str) -> list[Entity]:
        """Get all entities of a specific type."""
        type_key = (
            entity_type.value if isinstance(entity_type, EntityType) else entity_type
        )
        entity_ids = self._entity_by_type.get(type_key, set())
        return [self._entities[eid] for eid in entity_ids if eid in self._entities]

    def query(self, query: GraphQuery) -> list[Triple]:
        """Query the graph for matching triples."""
        # Start with candidate triples based on indexes
        candidate_ids: set[str] | None = None

        # Use subject index
        if query.subject is not None:
            if isinstance(query.subject, Entity):
                subject_ids = self._triples_by_subject.get(query.subject.id, set())
            else:
                entity = self.get_entity_by_name(query.subject)
                if entity:
                    subject_ids = self._triples_by_subject.get(entity.id, set())
                else:
                    subject_ids = set()
            candidate_ids = subject_ids

        # Use object index
        if query.object is not None:
            if isinstance(query.object, Entity):
                object_ids = self._triples_by_object.get(query.object.id, set())
            else:
                entity = self.get_entity_by_name(query.object)
                if entity:
                    object_ids = self._triples_by_object.get(entity.id, set())
                else:
                    object_ids = set()
            if candidate_ids is None:
                candidate_ids = object_ids
            else:
                candidate_ids = candidate_ids & object_ids

        # Use relation index
        if query.relation is not None:
            relation_name = (
                query.relation.name
                if isinstance(query.relation, Relation)
                else query.relation
            )
            relation_ids = self._triples_by_relation.get(relation_name.lower(), set())
            if candidate_ids is None:
                candidate_ids = relation_ids
            else:
                candidate_ids = candidate_ids & relation_ids

        # If no index constraints, search all
        if candidate_ids is None:
            candidate_ids = set(self._triples.keys())

        # Filter candidates
        results = []
        for triple_id in candidate_ids:
            triple = self._triples.get(triple_id)
            if triple and query.matches_triple(triple):
                results.append(triple)
                if len(results) >= query.limit:
                    break

        return results

    def delete_entity(self, entity_id: str) -> bool:
        """Delete an entity and its relations."""
        entity = self._entities.get(entity_id)
        if not entity:
            return False

        # Delete related triples
        triple_ids = (
            self._triples_by_subject.get(entity_id, set())
            | self._triples_by_object.get(entity_id, set())
        )
        for triple_id in list(triple_ids):
            self.delete_triple(triple_id)

        # Remove from indexes
        name_key = entity.name.lower()
        self._entity_by_name.pop(name_key, None)

        type_key = (
            entity.type.value if isinstance(entity.type, EntityType) else entity.type
        )
        self._entity_by_type[type_key].discard(entity_id)

        # Remove entity
        del self._entities[entity_id]

        self._save_if_needed()
        return True

    def delete_triple(self, triple_id: str) -> bool:
        """Delete a triple."""
        triple = self._triples.get(triple_id)
        if not triple:
            return False

        # Remove from indexes
        self._triples_by_subject[triple.subject.id].discard(triple_id)
        self._triples_by_object[triple.object.id].discard(triple_id)
        self._triples_by_relation[triple.relation_name.lower()].discard(triple_id)

        # Remove triple
        del self._triples[triple_id]

        self._save_if_needed()
        return True

    def count_entities(self) -> int:
        """Get entity count."""
        return len(self._entities)

    def count_triples(self) -> int:
        """Get triple count."""
        return len(self._triples)

    def clear(self) -> None:
        """Clear all data."""
        self._entities.clear()
        self._triples.clear()
        self._entity_by_name.clear()
        self._entity_by_type.clear()
        self._triples_by_subject.clear()
        self._triples_by_object.clear()
        self._triples_by_relation.clear()
        self._save_if_needed()

    def find_path(
        self,
        start: str | Entity,
        end: str | Entity,
        max_hops: int = 5,
    ) -> list[Triple] | None:
        """Find a path between two entities.

        Args:
            start: Starting entity
            end: Target entity
            max_hops: Maximum path length

        Returns:
            List of triples forming the path, or None if no path found
        """
        # Get entity objects
        if isinstance(start, str):
            start_entity = self.get_entity_by_name(start)
            if not start_entity:
                return None
        else:
            start_entity = start

        if isinstance(end, str):
            end_entity = self.get_entity_by_name(end)
            if not end_entity:
                return None
        else:
            end_entity = end

        if start_entity.id == end_entity.id:
            return []

        # BFS for shortest path
        from collections import deque

        queue = deque([(start_entity, [])])
        visited = {start_entity.id}

        while queue:
            current, path = queue.popleft()

            if len(path) >= max_hops:
                continue

            # Get all relations
            for triple in self.get_relations(current):
                # Determine next entity
                if triple.subject.id == current.id:
                    next_entity = triple.object
                else:
                    next_entity = triple.subject

                if next_entity.id == end_entity.id:
                    return path + [triple]

                if next_entity.id not in visited:
                    visited.add(next_entity.id)
                    queue.append((next_entity, path + [triple]))

        return None

    def get_subgraph(
        self,
        center: str | Entity,
        hops: int = 2,
    ) -> "MemoryKnowledgeGraph":
        """Extract a subgraph around an entity.

        Args:
            center: Center entity
            hops: Number of hops to include

        Returns:
            New knowledge graph with subgraph
        """
        if isinstance(center, str):
            center_entity = self.get_entity_by_name(center)
            if not center_entity:
                return MemoryKnowledgeGraph()
        else:
            center_entity = center

        subgraph = MemoryKnowledgeGraph()

        # Get neighbors
        entities = self.get_neighbors(center_entity, hops)
        entities.add(center_entity)

        # Add entities
        for entity in entities:
            subgraph.add_entity(entity)

        # Add triples between included entities
        for entity in entities:
            for triple in self.get_relations(entity):
                if triple.subject in entities and triple.object in entities:
                    if triple.id not in subgraph._triples:
                        subgraph.add_triple(triple)

        return subgraph

    def merge_from(self, other: "MemoryKnowledgeGraph") -> tuple[int, int]:
        """Merge another knowledge graph into this one.

        Args:
            other: Knowledge graph to merge

        Returns:
            Tuple of (entities_added, triples_added)
        """
        entities_added = 0
        triples_added = 0

        # Merge entities
        for entity in other._entities.values():
            if entity.id not in self._entities:
                self.add_entity(entity)
                entities_added += 1

        # Merge triples
        for triple in other._triples.values():
            if triple.id not in self._triples:
                self.add_triple(triple)
                triples_added += 1

        return entities_added, triples_added

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "entities": [e.to_dict() for e in self._entities.values()],
            "triples": [t.to_dict() for t in self._triples.values()],
        }

    def _save_if_needed(self) -> None:
        """Save to disk if persistence is configured."""
        if self._persist_path:
            self._save()

    def _save(self) -> None:
        """Save to disk."""
        if not self._persist_path:
            return

        data = self.to_dict()
        self._persist_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self._persist_path, "w") as f:
            json.dump(data, f, indent=2, default=str)

    def _load(self) -> None:
        """Load from disk."""
        if not self._persist_path or not self._persist_path.exists():
            return

        with open(self._persist_path) as f:
            data = json.load(f)

        # Load entities first
        entity_map = {}
        for entity_data in data.get("entities", []):
            entity = Entity.from_dict(entity_data)
            self.add_entity(entity)
            entity_map[entity.id] = entity

        # Load triples
        for triple_data in data.get("triples", []):
            subject = entity_map.get(triple_data["subject"]["id"])
            obj = entity_map.get(triple_data["object"]["id"])

            if subject and obj:
                triple = Triple(
                    id=triple_data["id"],
                    subject=subject,
                    relation=triple_data["relation"],
                    object=obj,
                    properties=triple_data.get("properties", {}),
                )
                self.add_triple(triple)

    def get_stats(self) -> dict:
        """Get graph statistics."""
        type_counts = {}
        for type_key, entity_ids in self._entity_by_type.items():
            type_counts[type_key] = len(entity_ids)

        relation_counts = {}
        for relation, triple_ids in self._triples_by_relation.items():
            relation_counts[relation] = len(triple_ids)

        return {
            "entity_count": len(self._entities),
            "triple_count": len(self._triples),
            "entity_types": type_counts,
            "relation_types": relation_counts,
        }
