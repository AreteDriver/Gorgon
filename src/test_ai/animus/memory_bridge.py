"""Animus MemoryProvider implementation backed by Gorgon's database layer.

Conforms to the MemoryProvider protocol defined in animus/protocols/memory.py:
    store(memory) -> None
    update(memory) -> bool
    retrieve(memory_id) -> Memory | None
    search(query, memory_type, tags, source, min_confidence, limit) -> list[Memory]
    delete(memory_id) -> bool
    list_all(memory_type) -> list[Memory]
    get_all_tags() -> dict[str, int]
"""

from __future__ import annotations

import json
import logging
from collections import Counter
from datetime import datetime, timezone
from typing import Any

from test_ai.state.backends import DatabaseBackend, SQLiteBackend

from .models import Memory, MemorySource, MemoryType

logger = logging.getLogger(__name__)


class AnimusMemoryProvider:
    """MemoryProvider protocol implementation using Gorgon's database backend.

    Stores episodic, semantic, procedural, and active memories with
    confidence scoring, source tracking, and tag-based retrieval.
    Satisfies Animus's MemoryProvider structural protocol.
    """

    SCHEMA = """
        CREATE TABLE IF NOT EXISTS animus_memories (
            id TEXT PRIMARY KEY,
            content TEXT NOT NULL,
            memory_type TEXT NOT NULL,
            subtype TEXT,
            source TEXT NOT NULL DEFAULT 'stated',
            confidence REAL NOT NULL DEFAULT 1.0,
            tags TEXT,
            metadata TEXT,
            workflow_id TEXT,
            agent_id TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            accessed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            access_count INTEGER NOT NULL DEFAULT 0
        );

        CREATE INDEX IF NOT EXISTS idx_animus_mem_type
        ON animus_memories(memory_type);

        CREATE INDEX IF NOT EXISTS idx_animus_mem_source
        ON animus_memories(source);

        CREATE INDEX IF NOT EXISTS idx_animus_mem_confidence
        ON animus_memories(confidence DESC);

        CREATE INDEX IF NOT EXISTS idx_animus_mem_workflow
        ON animus_memories(workflow_id);

        CREATE INDEX IF NOT EXISTS idx_animus_mem_agent
        ON animus_memories(agent_id);

        CREATE INDEX IF NOT EXISTS idx_animus_mem_accessed
        ON animus_memories(accessed_at DESC);
    """

    def __init__(
        self,
        backend: DatabaseBackend | None = None,
        db_path: str = "gorgon-animus-memory.db",
    ):
        self.backend = backend or SQLiteBackend(db_path=db_path)
        self._init_schema()

    def _init_schema(self) -> None:
        self.backend.executescript(self.SCHEMA)

    # --- MemoryProvider protocol methods ---

    def store(self, memory: Memory) -> None:
        """Store a memory entry."""
        with self.backend.transaction():
            self.backend.execute(
                """
                INSERT INTO animus_memories
                (id, content, memory_type, subtype, source, confidence,
                 tags, metadata, created_at, updated_at, accessed_at, access_count)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
                """,
                (
                    memory.id,
                    memory.content,
                    memory.memory_type.value,
                    memory.subtype,
                    memory.source,
                    memory.confidence,
                    json.dumps(memory.tags),
                    json.dumps(memory.metadata),
                    memory.created_at.isoformat(),
                    memory.updated_at.isoformat(),
                    memory.created_at.isoformat(),
                ),
            )
        logger.debug("Stored memory %s (type=%s)", memory.id, memory.memory_type.value)

    def update(self, memory: Memory) -> bool:
        """Update an existing memory. Returns True if found and updated."""
        now = datetime.now(timezone.utc).isoformat()
        with self.backend.transaction():
            cursor = self.backend.execute(
                """
                UPDATE animus_memories
                SET content = ?, memory_type = ?, subtype = ?, source = ?,
                    confidence = ?, tags = ?, metadata = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    memory.content,
                    memory.memory_type.value,
                    memory.subtype,
                    memory.source,
                    memory.confidence,
                    json.dumps(memory.tags),
                    json.dumps(memory.metadata),
                    now,
                    memory.id,
                ),
            )
        updated = cursor.rowcount > 0
        if updated:
            logger.debug("Updated memory %s", memory.id)
        return updated

    def retrieve(self, memory_id: str) -> Memory | None:
        """Retrieve a memory by ID. Updates access tracking."""
        row = self.backend.fetchone(
            "SELECT * FROM animus_memories WHERE id = ?",
            (memory_id,),
        )
        if not row:
            return None

        # Update access tracking
        now = datetime.now(timezone.utc).isoformat()
        self.backend.execute(
            "UPDATE animus_memories SET accessed_at = ?, access_count = access_count + 1 WHERE id = ?",
            (now, memory_id),
        )

        return self._row_to_memory(row)

    def search(
        self,
        query: str,
        memory_type: MemoryType | None = None,
        tags: list[str] | None = None,
        source: str | None = None,
        min_confidence: float = 0.0,
        limit: int = 10,
    ) -> list[Memory]:
        """Search memories by content and filters.

        Uses LIKE-based content matching. For production use with large
        datasets, this should be extended with vector embeddings.
        """
        conditions: list[str] = []
        params: list[Any] = []

        # Content search (case-insensitive LIKE)
        if query:
            conditions.append("content LIKE ?")
            params.append(f"%{query}%")

        if memory_type is not None:
            conditions.append("memory_type = ?")
            params.append(memory_type.value)

        if source is not None:
            conditions.append("source = ?")
            params.append(source)

        if min_confidence > 0.0:
            conditions.append("confidence >= ?")
            params.append(min_confidence)

        where = " AND ".join(conditions) if conditions else "1=1"
        sql = f"""
            SELECT * FROM animus_memories
            WHERE {where}
            ORDER BY confidence DESC, accessed_at DESC
            LIMIT ?
        """
        params.append(limit)

        rows = self.backend.fetchall(sql, tuple(params))

        # Post-filter by tags (stored as JSON array)
        results = []
        for row in rows:
            memory = self._row_to_memory(row)
            if tags:
                if not all(t in memory.tags for t in tags):
                    continue
            results.append(memory)

        return results

    def delete(self, memory_id: str) -> bool:
        """Delete a memory by ID."""
        with self.backend.transaction():
            cursor = self.backend.execute(
                "DELETE FROM animus_memories WHERE id = ?",
                (memory_id,),
            )
        deleted = cursor.rowcount > 0
        if deleted:
            logger.debug("Deleted memory %s", memory_id)
        return deleted

    def list_all(self, memory_type: MemoryType | None = None) -> list[Memory]:
        """List all memories, optionally filtered by type."""
        if memory_type is not None:
            rows = self.backend.fetchall(
                "SELECT * FROM animus_memories WHERE memory_type = ? ORDER BY created_at DESC",
                (memory_type.value,),
            )
        else:
            rows = self.backend.fetchall(
                "SELECT * FROM animus_memories ORDER BY created_at DESC",
                (),
            )
        return [self._row_to_memory(row) for row in rows]

    def get_all_tags(self) -> dict[str, int]:
        """Get all tags with their occurrence counts."""
        rows = self.backend.fetchall(
            "SELECT tags FROM animus_memories WHERE tags IS NOT NULL",
            (),
        )
        counter: Counter[str] = Counter()
        for row in rows:
            try:
                tag_list = json.loads(row["tags"])
                counter.update(tag_list)
            except (json.JSONDecodeError, TypeError):
                pass
        return dict(counter)

    # --- Extended methods for Gorgon workflow integration ---

    def store_workflow_result(
        self,
        workflow_id: str,
        agent_id: str,
        content: str,
        memory_type: MemoryType = MemoryType.EPISODIC,
        confidence: float = 0.8,
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Memory:
        """Store a workflow execution result as a memory.

        Convenience method for the common case of persisting
        agent outputs from Gorgon workflows.
        """
        memory = Memory(
            content=content,
            memory_type=memory_type,
            source=MemorySource.INFERRED.value,
            confidence=confidence,
            tags=tags or ["gorgon", "workflow"],
            metadata={
                **(metadata or {}),
                "workflow_id": workflow_id,
                "agent_id": agent_id,
            },
        )
        self.store(memory)
        return memory

    def recall_for_agent(
        self,
        agent_id: str,
        memory_type: MemoryType | None = None,
        limit: int = 10,
        min_confidence: float = 0.3,
    ) -> list[Memory]:
        """Recall memories relevant to a specific agent."""
        conditions = ["confidence >= ?"]
        params: list[Any] = [min_confidence]

        if memory_type is not None:
            conditions.append("memory_type = ?")
            params.append(memory_type.value)

        where = " AND ".join(conditions)
        rows = self.backend.fetchall(
            f"""
            SELECT * FROM animus_memories
            WHERE {where}
            ORDER BY confidence DESC, accessed_at DESC
            LIMIT ?
            """,
            (*params, limit),
        )
        return [self._row_to_memory(row) for row in rows]

    def get_stats(self) -> dict[str, Any]:
        """Get memory store statistics."""
        total = self.backend.fetchone(
            "SELECT COUNT(*) as count FROM animus_memories", ()
        )
        by_type = self.backend.fetchall(
            "SELECT memory_type, COUNT(*) as count FROM animus_memories GROUP BY memory_type",
            (),
        )
        by_source = self.backend.fetchall(
            "SELECT source, COUNT(*) as count FROM animus_memories GROUP BY source",
            (),
        )
        return {
            "total": total["count"] if total else 0,
            "by_type": {row["memory_type"]: row["count"] for row in by_type},
            "by_source": {row["source"]: row["count"] for row in by_source},
        }

    # --- Private helpers ---

    def _row_to_memory(self, row: dict) -> Memory:
        """Convert a database row to a Memory object."""
        return Memory(
            id=row["id"],
            content=row["content"],
            memory_type=MemoryType(row["memory_type"]),
            subtype=row.get("subtype"),
            source=row.get("source", MemorySource.STATED.value),
            confidence=row.get("confidence", 1.0),
            tags=json.loads(row["tags"]) if row.get("tags") else [],
            metadata=json.loads(row["metadata"]) if row.get("metadata") else {},
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )
