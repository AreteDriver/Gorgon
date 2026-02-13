"""Base classes for knowledge graph."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any
import uuid


class EntityType(Enum):
    """Common entity types."""

    PERSON = "person"
    ORGANIZATION = "organization"
    LOCATION = "location"
    CONCEPT = "concept"
    EVENT = "event"
    PRODUCT = "product"
    CODE = "code"
    FILE = "file"
    FUNCTION = "function"
    CLASS = "class"
    CUSTOM = "custom"


@dataclass
class Entity:
    """An entity (node) in the knowledge graph.

    Attributes:
        id: Unique entity identifier
        name: Entity name
        type: Entity type
        properties: Additional properties
        embedding: Optional embedding vector
        created_at: Creation timestamp
    """

    name: str
    type: EntityType | str = EntityType.CONCEPT
    properties: dict[str, Any] = field(default_factory=dict)
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:12])
    embedding: list[float] | None = None
    created_at: datetime = field(default_factory=datetime.now)

    def __hash__(self):
        return hash(self.id)

    def __eq__(self, other):
        if isinstance(other, Entity):
            return self.id == other.id
        return False

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "type": self.type.value if isinstance(self.type, EntityType) else self.type,
            "properties": self.properties,
            "created_at": self.created_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Entity":
        """Create from dictionary."""
        entity_type = data.get("type", "concept")
        try:
            entity_type = EntityType(entity_type)
        except ValueError:
            pass  # Graceful degradation: unrecognized entity type kept as string

        return cls(
            id=data.get("id", str(uuid.uuid4())[:12]),
            name=data["name"],
            type=entity_type,
            properties=data.get("properties", {}),
            created_at=datetime.fromisoformat(data["created_at"])
            if "created_at" in data
            else datetime.now(),
        )


@dataclass
class Relation:
    """A relation type in the knowledge graph.

    Attributes:
        name: Relation name (e.g., "works_at", "located_in")
        properties: Relation metadata
        inverse: Name of inverse relation
    """

    name: str
    properties: dict[str, Any] = field(default_factory=dict)
    inverse: str | None = None

    def __hash__(self):
        return hash(self.name)

    def __eq__(self, other):
        if isinstance(other, Relation):
            return self.name == other.name
        return False


@dataclass
class Triple:
    """A triple (edge) in the knowledge graph.

    Represents: subject --relation--> object

    Attributes:
        subject: Source entity
        relation: Relation type
        object: Target entity
        properties: Edge properties (confidence, source, etc.)
        id: Unique triple identifier
        created_at: Creation timestamp
    """

    subject: Entity
    relation: Relation | str
    object: Entity
    properties: dict[str, Any] = field(default_factory=dict)
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:12])
    created_at: datetime = field(default_factory=datetime.now)

    @property
    def relation_name(self) -> str:
        """Get relation name."""
        if isinstance(self.relation, Relation):
            return self.relation.name
        return self.relation

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "subject": self.subject.to_dict(),
            "relation": self.relation_name,
            "object": self.object.to_dict(),
            "properties": self.properties,
            "created_at": self.created_at.isoformat(),
        }

    def __str__(self) -> str:
        return f"({self.subject.name}) --[{self.relation_name}]--> ({self.object.name})"


@dataclass
class GraphQuery:
    """A query against the knowledge graph.

    Supports pattern matching on entities and relations.
    """

    subject: str | Entity | None = None
    relation: str | Relation | None = None
    object: str | Entity | None = None
    subject_type: EntityType | str | None = None
    object_type: EntityType | str | None = None
    limit: int = 100
    properties_filter: dict[str, Any] | None = None

    def matches_triple(self, triple: Triple) -> bool:
        """Check if a triple matches this query."""
        # Match subject
        if self.subject is not None:
            if isinstance(self.subject, Entity):
                if triple.subject.id != self.subject.id:
                    return False
            elif isinstance(self.subject, str):
                if triple.subject.name.lower() != self.subject.lower():
                    return False

        # Match relation
        if self.relation is not None:
            relation_name = (
                self.relation.name
                if isinstance(self.relation, Relation)
                else self.relation
            )
            if triple.relation_name.lower() != relation_name.lower():
                return False

        # Match object
        if self.object is not None:
            if isinstance(self.object, Entity):
                if triple.object.id != self.object.id:
                    return False
            elif isinstance(self.object, str):
                if triple.object.name.lower() != self.object.lower():
                    return False

        # Match subject type
        if self.subject_type is not None:
            subject_type = (
                self.subject_type.value
                if isinstance(self.subject_type, EntityType)
                else self.subject_type
            )
            triple_subject_type = (
                triple.subject.type.value
                if isinstance(triple.subject.type, EntityType)
                else triple.subject.type
            )
            if triple_subject_type != subject_type:
                return False

        # Match object type
        if self.object_type is not None:
            object_type = (
                self.object_type.value
                if isinstance(self.object_type, EntityType)
                else self.object_type
            )
            triple_object_type = (
                triple.object.type.value
                if isinstance(triple.object.type, EntityType)
                else triple.object.type
            )
            if triple_object_type != object_type:
                return False

        return True


class KnowledgeGraph(ABC):
    """Abstract base class for knowledge graphs.

    Provides a unified interface for storing and querying
    knowledge as entities and relations.
    """

    @abstractmethod
    def add_entity(self, entity: Entity) -> str:
        """Add an entity to the graph.

        Args:
            entity: Entity to add

        Returns:
            Entity ID
        """
        pass

    @abstractmethod
    def add_triple(self, triple: Triple) -> str:
        """Add a triple (relationship) to the graph.

        Args:
            triple: Triple to add

        Returns:
            Triple ID
        """
        pass

    @abstractmethod
    def get_entity(self, entity_id: str) -> Entity | None:
        """Get an entity by ID.

        Args:
            entity_id: Entity ID

        Returns:
            Entity or None if not found
        """
        pass

    @abstractmethod
    def get_entity_by_name(self, name: str) -> Entity | None:
        """Get an entity by name.

        Args:
            name: Entity name

        Returns:
            Entity or None if not found
        """
        pass

    @abstractmethod
    def query(self, query: GraphQuery) -> list[Triple]:
        """Query the graph for matching triples.

        Args:
            query: Query specification

        Returns:
            List of matching triples
        """
        pass

    @abstractmethod
    def delete_entity(self, entity_id: str) -> bool:
        """Delete an entity and its relations.

        Args:
            entity_id: Entity ID

        Returns:
            True if deleted
        """
        pass

    @abstractmethod
    def delete_triple(self, triple_id: str) -> bool:
        """Delete a triple.

        Args:
            triple_id: Triple ID

        Returns:
            True if deleted
        """
        pass

    @abstractmethod
    def count_entities(self) -> int:
        """Get entity count."""
        pass

    @abstractmethod
    def count_triples(self) -> int:
        """Get triple count."""
        pass

    # Convenience methods

    def add(
        self,
        subject: str | Entity,
        relation: str,
        obj: str | Entity,
        subject_type: EntityType | str = EntityType.CONCEPT,
        object_type: EntityType | str = EntityType.CONCEPT,
        **properties,
    ) -> Triple:
        """Convenience method to add a triple with auto-entity creation.

        Args:
            subject: Subject name or entity
            relation: Relation name
            obj: Object name or entity
            subject_type: Type for new subject entity
            object_type: Type for new object entity
            **properties: Triple properties

        Returns:
            Created triple
        """
        # Get or create subject
        if isinstance(subject, str):
            subject_entity = self.get_entity_by_name(subject)
            if not subject_entity:
                subject_entity = Entity(name=subject, type=subject_type)
                self.add_entity(subject_entity)
        else:
            subject_entity = subject
            if not self.get_entity(subject.id):
                self.add_entity(subject)

        # Get or create object
        if isinstance(obj, str):
            object_entity = self.get_entity_by_name(obj)
            if not object_entity:
                object_entity = Entity(name=obj, type=object_type)
                self.add_entity(object_entity)
        else:
            object_entity = obj
            if not self.get_entity(obj.id):
                self.add_entity(obj)

        # Create and add triple
        triple = Triple(
            subject=subject_entity,
            relation=relation,
            object=object_entity,
            properties=properties,
        )
        self.add_triple(triple)

        return triple

    def get_relations(self, entity: str | Entity) -> list[Triple]:
        """Get all relations for an entity.

        Args:
            entity: Entity name or object

        Returns:
            List of triples involving this entity
        """
        if isinstance(entity, str):
            entity_obj = self.get_entity_by_name(entity)
            if not entity_obj:
                return []
        else:
            entity_obj = entity

        # Query for triples where entity is subject or object
        as_subject = self.query(GraphQuery(subject=entity_obj))
        as_object = self.query(GraphQuery(object=entity_obj))

        # Combine and deduplicate
        seen = set()
        results = []
        for triple in as_subject + as_object:
            if triple.id not in seen:
                seen.add(triple.id)
                results.append(triple)

        return results

    def get_neighbors(self, entity: str | Entity, hops: int = 1) -> set[Entity]:
        """Get neighboring entities within N hops.

        Args:
            entity: Starting entity
            hops: Number of hops to traverse

        Returns:
            Set of neighboring entities
        """
        if isinstance(entity, str):
            entity_obj = self.get_entity_by_name(entity)
            if not entity_obj:
                return set()
        else:
            entity_obj = entity

        visited = {entity_obj}
        frontier = {entity_obj}

        for _ in range(hops):
            new_frontier = set()
            for e in frontier:
                relations = self.get_relations(e)
                for triple in relations:
                    if triple.subject not in visited:
                        new_frontier.add(triple.subject)
                        visited.add(triple.subject)
                    if triple.object not in visited:
                        new_frontier.add(triple.object)
                        visited.add(triple.object)
            frontier = new_frontier

        visited.discard(entity_obj)  # Remove starting entity
        return visited

    def to_context(
        self,
        entity: str | Entity,
        max_relations: int = 10,
    ) -> str:
        """Convert entity and relations to text context.

        Useful for injecting knowledge into prompts.

        Args:
            entity: Entity to describe
            max_relations: Maximum relations to include

        Returns:
            Text description of entity and relations
        """
        if isinstance(entity, str):
            entity_obj = self.get_entity_by_name(entity)
            if not entity_obj:
                return f"No information found about '{entity}'."
        else:
            entity_obj = entity

        lines = [f"Information about {entity_obj.name}:"]

        # Add properties
        if entity_obj.properties:
            for key, value in entity_obj.properties.items():
                lines.append(f"- {key}: {value}")

        # Add relations
        relations = self.get_relations(entity_obj)[:max_relations]
        if relations:
            lines.append("\nRelationships:")
            for triple in relations:
                if triple.subject.id == entity_obj.id:
                    lines.append(f"- {triple.relation_name} {triple.object.name}")
                else:
                    lines.append(
                        f"- {triple.subject.name} {triple.relation_name} (this)"
                    )

        return "\n".join(lines)
