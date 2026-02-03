"""Knowledge Graph Module.

Provides knowledge representation and reasoning capabilities
for AI agents through graph-based data structures.
"""

from .base import (
    Entity,
    Relation,
    Triple,
    KnowledgeGraph,
    GraphQuery,
)
from .memory_graph import MemoryKnowledgeGraph
from .extractors import (
    EntityExtractor,
    LLMEntityExtractor,
    RelationExtractor,
)

__all__ = [
    # Base classes
    "Entity",
    "Relation",
    "Triple",
    "KnowledgeGraph",
    "GraphQuery",
    # Implementations
    "MemoryKnowledgeGraph",
    # Extractors
    "EntityExtractor",
    "LLMEntityExtractor",
    "RelationExtractor",
]
