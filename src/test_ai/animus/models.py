"""Animus-compatible data models.

These mirror the data structures defined in Animus's protocols/memory.py
so Gorgon can exchange data with Animus without conversion.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class MemoryType(str, Enum):
    """Memory types matching Animus MemoryType."""

    EPISODIC = "episodic"  # Conversations, events, decisions
    SEMANTIC = "semantic"  # Facts, knowledge, learnings
    PROCEDURAL = "procedural"  # Workflows, habits, patterns
    ACTIVE = "active"  # Current situation, live state


class MemorySource(str, Enum):
    """How the memory was acquired."""

    STATED = "stated"  # User explicitly told
    INFERRED = "inferred"  # Derived from context
    LEARNED = "learned"  # Pattern detected over time


@dataclass
class Memory:
    """A single memory entry, matching Animus Memory dataclass.

    This is the canonical exchange format between Gorgon and Animus.
    """

    content: str
    memory_type: MemoryType
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    updated_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    metadata: dict[str, Any] = field(default_factory=dict)
    tags: list[str] = field(default_factory=list)
    source: str = MemorySource.STATED.value
    confidence: float = 1.0
    subtype: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary for storage."""
        return {
            "id": self.id,
            "content": self.content,
            "memory_type": self.memory_type.value,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "metadata": self.metadata,
            "tags": self.tags,
            "source": self.source,
            "confidence": self.confidence,
            "subtype": self.subtype,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Memory:
        """Deserialize from dictionary."""
        return cls(
            id=data["id"],
            content=data["content"],
            memory_type=MemoryType(data["memory_type"]),
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"]),
            metadata=data.get("metadata", {}),
            tags=data.get("tags", []),
            source=data.get("source", MemorySource.STATED.value),
            confidence=data.get("confidence", 1.0),
            subtype=data.get("subtype"),
        )


@dataclass
class UserProfile:
    """Persistent user identity for Animus Core Layer.

    Maps to Animus's identity and preferences system.
    """

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    display_name: str = "User"
    preferences: dict[str, Any] = field(default_factory=dict)
    boundaries: list[str] = field(default_factory=list)
    ethics_config: dict[str, Any] = field(default_factory=dict)
    learning_config: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    updated_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    is_active: bool = True

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "id": self.id,
            "display_name": self.display_name,
            "preferences": self.preferences,
            "boundaries": self.boundaries,
            "ethics_config": self.ethics_config,
            "learning_config": self.learning_config,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "is_active": self.is_active,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> UserProfile:
        """Deserialize from dictionary."""
        return cls(
            id=data["id"],
            display_name=data.get("display_name", "User"),
            preferences=data.get("preferences", {}),
            boundaries=data.get("boundaries", []),
            ethics_config=data.get("ethics_config", {}),
            learning_config=data.get("learning_config", {}),
            metadata=data.get("metadata", {}),
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"]),
            is_active=data.get("is_active", True),
        )


@dataclass
class SafetyCheckResult:
    """Result of a safety guard check."""

    allowed: bool
    reason: str | None = None
    action: dict[str, Any] = field(default_factory=dict)
    checked_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    workflow_id: str | None = None
    step_id: str | None = None
