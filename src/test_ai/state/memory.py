"""Agent memory and context persistence."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Callable

from .backends import DatabaseBackend, SQLiteBackend

logger = logging.getLogger(__name__)


@dataclass
class MemoryEntry:
    """A single memory entry."""

    id: int | None = None
    agent_id: str = ""
    workflow_id: str | None = None
    memory_type: str = "conversation"  # conversation, fact, preference, learned
    content: str = ""
    metadata: dict = field(default_factory=dict)
    importance: float = 0.5  # 0.0 to 1.0
    created_at: datetime | None = None
    accessed_at: datetime | None = None
    access_count: int = 0

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "agent_id": self.agent_id,
            "workflow_id": self.workflow_id,
            "memory_type": self.memory_type,
            "content": self.content,
            "metadata": self.metadata,
            "importance": self.importance,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "accessed_at": self.accessed_at.isoformat() if self.accessed_at else None,
            "access_count": self.access_count,
        }

    @classmethod
    def from_dict(cls, data: dict) -> MemoryEntry:
        """Create from dictionary."""
        return cls(
            id=data.get("id"),
            agent_id=data.get("agent_id", ""),
            workflow_id=data.get("workflow_id"),
            memory_type=data.get("memory_type", "conversation"),
            content=data.get("content", ""),
            metadata=json.loads(data["metadata"])
            if isinstance(data.get("metadata"), str)
            else data.get("metadata", {}),
            importance=data.get("importance", 0.5),
            created_at=datetime.fromisoformat(data["created_at"])
            if data.get("created_at")
            else None,
            accessed_at=datetime.fromisoformat(data["accessed_at"])
            if data.get("accessed_at")
            else None,
            access_count=data.get("access_count", 0),
        )


class AgentMemory:
    """Persistent memory store for agents.

    Provides long-term storage and retrieval of agent context,
    learned facts, and conversation history.
    """

    SCHEMA = """
        CREATE TABLE IF NOT EXISTS agent_memories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            agent_id TEXT NOT NULL,
            workflow_id TEXT,
            memory_type TEXT NOT NULL DEFAULT 'conversation',
            content TEXT NOT NULL,
            metadata TEXT,
            importance REAL DEFAULT 0.5,
            embedding TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            accessed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            access_count INTEGER DEFAULT 0
        );

        CREATE INDEX IF NOT EXISTS idx_memories_agent
        ON agent_memories(agent_id, memory_type);

        CREATE INDEX IF NOT EXISTS idx_memories_workflow
        ON agent_memories(workflow_id);

        CREATE INDEX IF NOT EXISTS idx_memories_importance
        ON agent_memories(importance DESC);

        CREATE INDEX IF NOT EXISTS idx_memories_accessed
        ON agent_memories(accessed_at DESC);
    """

    def __init__(
        self, backend: DatabaseBackend | None = None, db_path: str = "gorgon-memory.db"
    ):
        """Initialize agent memory.

        Args:
            backend: Database backend to use
            db_path: Path to SQLite database (if no backend provided)
        """
        self.backend = backend or SQLiteBackend(db_path=db_path)
        self._init_schema()

    def _init_schema(self):
        """Initialize database schema."""
        self.backend.executescript(self.SCHEMA)

    def store(
        self,
        agent_id: str,
        content: str,
        memory_type: str = "conversation",
        workflow_id: str | None = None,
        metadata: dict | None = None,
        importance: float = 0.5,
    ) -> int:
        """Store a memory entry.

        Args:
            agent_id: Agent identifier
            content: Memory content
            memory_type: Type of memory (conversation, fact, preference, learned)
            workflow_id: Optional workflow context
            metadata: Optional metadata dict
            importance: Importance score (0.0 to 1.0)

        Returns:
            Memory entry ID
        """
        with self.backend.transaction():
            cursor = self.backend.execute(
                """
                INSERT INTO agent_memories
                (agent_id, workflow_id, memory_type, content, metadata, importance)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    agent_id,
                    workflow_id,
                    memory_type,
                    content,
                    json.dumps(metadata) if metadata else None,
                    importance,
                ),
            )
            return cursor.lastrowid

    def recall(
        self,
        agent_id: str,
        memory_type: str | None = None,
        workflow_id: str | None = None,
        limit: int = 10,
        min_importance: float = 0.0,
        since: datetime | None = None,
    ) -> list[MemoryEntry]:
        """Recall memories for an agent.

        Args:
            agent_id: Agent identifier
            memory_type: Optional filter by memory type
            workflow_id: Optional filter by workflow
            limit: Maximum entries to return
            min_importance: Minimum importance threshold
            since: Only memories created after this time

        Returns:
            List of memory entries
        """
        conditions = ["agent_id = ?"]
        params: list[Any] = [agent_id]

        if memory_type:
            conditions.append("memory_type = ?")
            params.append(memory_type)

        if workflow_id:
            conditions.append("workflow_id = ?")
            params.append(workflow_id)

        if min_importance > 0:
            conditions.append("importance >= ?")
            params.append(min_importance)

        if since:
            conditions.append("created_at >= ?")
            params.append(since.isoformat())

        where_clause = " AND ".join(conditions)
        params.append(limit)

        rows = self.backend.fetchall(
            f"""
            SELECT * FROM agent_memories
            WHERE {where_clause}
            ORDER BY importance DESC, accessed_at DESC
            LIMIT ?
            """,
            tuple(params),
        )

        # Update access timestamps
        if rows:
            ids = [row["id"] for row in rows]
            placeholders = ",".join("?" * len(ids))
            self.backend.execute(
                f"""
                UPDATE agent_memories
                SET accessed_at = CURRENT_TIMESTAMP, access_count = access_count + 1
                WHERE id IN ({placeholders})
                """,
                tuple(ids),
            )

        return [MemoryEntry.from_dict(row) for row in rows]

    def recall_recent(
        self,
        agent_id: str,
        hours: int = 24,
        limit: int = 20,
    ) -> list[MemoryEntry]:
        """Recall recent memories within time window.

        Args:
            agent_id: Agent identifier
            hours: Number of hours to look back
            limit: Maximum entries to return

        Returns:
            List of recent memory entries
        """
        since = datetime.now(timezone.utc) - timedelta(hours=hours)
        return self.recall(agent_id, since=since, limit=limit)

    def recall_context(
        self,
        agent_id: str,
        workflow_id: str | None = None,
        include_facts: bool = True,
        include_preferences: bool = True,
        max_entries: int = 50,
    ) -> dict[str, list[MemoryEntry]]:
        """Recall contextual memories for a workflow.

        Args:
            agent_id: Agent identifier
            workflow_id: Current workflow context
            include_facts: Include learned facts
            include_preferences: Include user preferences
            max_entries: Maximum total entries

        Returns:
            Dictionary of memories by type
        """
        result: dict[str, list[MemoryEntry]] = {}
        remaining = max_entries

        # Get workflow-specific memories first
        if workflow_id:
            workflow_memories = self.recall(
                agent_id,
                workflow_id=workflow_id,
                limit=min(20, remaining),
            )
            if workflow_memories:
                result["workflow"] = workflow_memories
                remaining -= len(workflow_memories)

        # Get high-importance facts
        if include_facts and remaining > 0:
            facts = self.recall(
                agent_id,
                memory_type="fact",
                min_importance=0.7,
                limit=min(15, remaining),
            )
            if facts:
                result["facts"] = facts
                remaining -= len(facts)

        # Get preferences
        if include_preferences and remaining > 0:
            preferences = self.recall(
                agent_id,
                memory_type="preference",
                limit=min(10, remaining),
            )
            if preferences:
                result["preferences"] = preferences
                remaining -= len(preferences)

        # Get recent conversation context
        if remaining > 0:
            recent = self.recall_recent(
                agent_id,
                hours=4,
                limit=remaining,
            )
            if recent:
                # Filter out memory types that were explicitly excluded
                excluded_types: set[str] = set()
                if not include_facts:
                    excluded_types.add("fact")
                if not include_preferences:
                    excluded_types.add("preference")
                if excluded_types:
                    recent = [m for m in recent if m.memory_type not in excluded_types]
                if recent:
                    result["recent"] = recent

        return result

    def forget(
        self,
        agent_id: str,
        memory_id: int | None = None,
        memory_type: str | None = None,
        older_than: datetime | None = None,
        below_importance: float | None = None,
    ) -> int:
        """Remove memories.

        Args:
            agent_id: Agent identifier
            memory_id: Specific memory to remove
            memory_type: Remove all of this type
            older_than: Remove memories older than this
            below_importance: Remove memories below this importance

        Returns:
            Number of memories removed
        """
        conditions = ["agent_id = ?"]
        params: list[Any] = [agent_id]

        if memory_id:
            conditions.append("id = ?")
            params.append(memory_id)

        if memory_type:
            conditions.append("memory_type = ?")
            params.append(memory_type)

        if older_than:
            conditions.append("created_at < ?")
            params.append(older_than.isoformat())

        if below_importance is not None:
            conditions.append("importance < ?")
            params.append(below_importance)

        where_clause = " AND ".join(conditions)

        with self.backend.transaction():
            cursor = self.backend.execute(
                f"DELETE FROM agent_memories WHERE {where_clause}",
                tuple(params),
            )
            return cursor.rowcount

    def consolidate(
        self,
        agent_id: str,
        keep_recent_hours: int = 168,  # 1 week
        min_access_count: int = 2,
    ) -> int:
        """Consolidate old, rarely-accessed memories.

        Removes old memories that haven't been accessed frequently,
        keeping important and frequently-used ones.

        Args:
            agent_id: Agent identifier
            keep_recent_hours: Keep all memories newer than this
            min_access_count: Minimum accesses to keep old memories

        Returns:
            Number of memories removed
        """
        cutoff = datetime.now(timezone.utc) - timedelta(hours=keep_recent_hours)

        with self.backend.transaction():
            cursor = self.backend.execute(
                """
                DELETE FROM agent_memories
                WHERE agent_id = ?
                AND created_at < ?
                AND access_count < ?
                AND importance < 0.8
                AND memory_type NOT IN ('fact', 'preference')
                """,
                (agent_id, cutoff.isoformat(), min_access_count),
            )
            return cursor.rowcount

    def update_importance(
        self,
        memory_id: int,
        importance: float,
    ) -> bool:
        """Update memory importance score.

        Args:
            memory_id: Memory entry ID
            importance: New importance score (0.0 to 1.0)

        Returns:
            True if updated
        """
        with self.backend.transaction():
            cursor = self.backend.execute(
                "UPDATE agent_memories SET importance = ? WHERE id = ?",
                (importance, memory_id),
            )
            return cursor.rowcount > 0

    def get_stats(self, agent_id: str) -> dict:
        """Get memory statistics for an agent.

        Args:
            agent_id: Agent identifier

        Returns:
            Dictionary with memory stats
        """
        total = self.backend.fetchone(
            "SELECT COUNT(*) as count FROM agent_memories WHERE agent_id = ?",
            (agent_id,),
        )

        by_type = self.backend.fetchall(
            """
            SELECT memory_type, COUNT(*) as count
            FROM agent_memories
            WHERE agent_id = ?
            GROUP BY memory_type
            """,
            (agent_id,),
        )

        avg_importance = self.backend.fetchone(
            "SELECT AVG(importance) as avg FROM agent_memories WHERE agent_id = ?",
            (agent_id,),
        )

        return {
            "total_memories": total["count"] if total else 0,
            "by_type": {row["memory_type"]: row["count"] for row in by_type},
            "average_importance": round(avg_importance["avg"] or 0, 2)
            if avg_importance
            else 0,
        }

    def format_context(self, memories: dict[str, list[MemoryEntry]]) -> str:
        """Format memories as context string for agent prompts.

        Args:
            memories: Dictionary of memories by category

        Returns:
            Formatted context string
        """
        parts = []

        if "facts" in memories:
            facts_text = "\n".join(f"- {m.content}" for m in memories["facts"])
            parts.append(f"Known Facts:\n{facts_text}")

        if "preferences" in memories:
            prefs_text = "\n".join(f"- {m.content}" for m in memories["preferences"])
            parts.append(f"User Preferences:\n{prefs_text}")

        if "workflow" in memories:
            workflow_text = "\n".join(
                f"- {m.content}" for m in memories["workflow"][:5]
            )
            parts.append(f"Current Workflow Context:\n{workflow_text}")

        if "recent" in memories:
            recent_text = "\n".join(f"- {m.content}" for m in memories["recent"][:5])
            parts.append(f"Recent Context:\n{recent_text}")

        return "\n\n".join(parts)


class MessageRole(Enum):
    """Role of a message in the context window."""

    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


@dataclass
class Message:
    """A message in the context window."""

    role: MessageRole
    content: str
    name: str | None = None  # For tool messages
    tool_call_id: str | None = None  # For tool responses
    metadata: dict = field(default_factory=dict)
    tokens: int = 0  # Cached token count
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict:
        """Convert to API message format."""
        msg = {"role": self.role.value, "content": self.content}
        if self.name:
            msg["name"] = self.name
        if self.tool_call_id:
            msg["tool_call_id"] = self.tool_call_id
        return msg

    @classmethod
    def from_dict(cls, data: dict) -> "Message":
        """Create from dictionary."""
        return cls(
            role=MessageRole(data["role"]),
            content=data["content"],
            name=data.get("name"),
            tool_call_id=data.get("tool_call_id"),
            metadata=data.get("metadata", {}),
            tokens=data.get("tokens", 0),
            timestamp=datetime.fromisoformat(data["timestamp"])
            if "timestamp" in data
            else datetime.now(timezone.utc),
        )


@dataclass
class ContextWindowStats:
    """Statistics about the context window."""

    total_tokens: int = 0
    message_count: int = 0
    user_messages: int = 0
    assistant_messages: int = 0
    system_tokens: int = 0
    available_tokens: int = 0
    utilization_percent: float = 0.0


class ContextWindow:
    """Manages conversation context with token budgeting.

    Provides:
    - Message history with role tracking
    - Token counting and budget management
    - Automatic truncation when exceeding limits
    - Context summarization for long conversations
    - Integration with AgentMemory for persistence
    """

    # Default token limits for common models
    MODEL_LIMITS = {
        "gpt-4o": 128000,
        "gpt-4o-mini": 128000,
        "gpt-4-turbo": 128000,
        "gpt-4": 8192,
        "gpt-3.5-turbo": 16385,
        "claude-3-opus": 200000,
        "claude-3-sonnet": 200000,
        "claude-3-haiku": 200000,
        "claude-sonnet-4-20250514": 200000,
        "claude-opus-4-5-20251101": 200000,
    }

    def __init__(
        self,
        max_tokens: int = 128000,
        reserve_tokens: int = 4096,
        token_counter: Callable[[str], int] | None = None,
        summarizer: Callable[[list[Message]], str] | None = None,
        memory: AgentMemory | None = None,
        agent_id: str = "default",
    ):
        """Initialize context window.

        Args:
            max_tokens: Maximum context window size
            reserve_tokens: Tokens to reserve for response
            token_counter: Function to count tokens (default: char/4 estimate)
            summarizer: Function to summarize messages (optional)
            memory: AgentMemory for persistence (optional)
            agent_id: Agent identifier for memory storage
        """
        self.max_tokens = max_tokens
        self.reserve_tokens = reserve_tokens
        self.token_counter = token_counter or self._estimate_tokens
        self.summarizer = summarizer
        self.memory = memory
        self.agent_id = agent_id

        self._messages: list[Message] = []
        self._system_message: Message | None = None
        self._summary: str | None = None
        self._total_tokens: int = 0

    @classmethod
    def for_model(
        cls,
        model: str,
        reserve_tokens: int = 4096,
        **kwargs,
    ) -> "ContextWindow":
        """Create context window with model-specific limits.

        Args:
            model: Model name
            reserve_tokens: Tokens to reserve for response
            **kwargs: Additional arguments for __init__

        Returns:
            Configured ContextWindow
        """
        max_tokens = cls.MODEL_LIMITS.get(model, 128000)
        return cls(max_tokens=max_tokens, reserve_tokens=reserve_tokens, **kwargs)

    def _estimate_tokens(self, text: str) -> int:
        """Estimate token count (rough approximation).

        Uses ~4 characters per token as a conservative estimate.
        For accurate counts, provide a model-specific token_counter.
        """
        return len(text) // 4 + 1

    @property
    def available_tokens(self) -> int:
        """Get available tokens for new content."""
        system_tokens = self._system_message.tokens if self._system_message else 0
        summary_tokens = self._estimate_tokens(self._summary) if self._summary else 0
        used = system_tokens + summary_tokens + self._total_tokens + self.reserve_tokens
        return max(0, self.max_tokens - used)

    def set_system_message(self, content: str) -> None:
        """Set the system message.

        Args:
            content: System message content
        """
        tokens = self.token_counter(content)
        self._system_message = Message(
            role=MessageRole.SYSTEM,
            content=content,
            tokens=tokens,
        )

    def add_message(
        self,
        role: MessageRole | str,
        content: str,
        name: str | None = None,
        tool_call_id: str | None = None,
        metadata: dict | None = None,
    ) -> Message:
        """Add a message to the context.

        Args:
            role: Message role
            content: Message content
            name: Optional name for tool messages
            tool_call_id: Optional tool call ID
            metadata: Optional metadata

        Returns:
            The added message
        """
        if isinstance(role, str):
            role = MessageRole(role)

        tokens = self.token_counter(content)
        message = Message(
            role=role,
            content=content,
            name=name,
            tool_call_id=tool_call_id,
            metadata=metadata or {},
            tokens=tokens,
        )

        self._messages.append(message)
        self._total_tokens += tokens

        # Check if we need to truncate (when over budget)
        if self._is_over_budget():
            self._truncate()

        return message

    def _is_over_budget(self) -> bool:
        """Check if context exceeds token budget."""
        system_tokens = self._system_message.tokens if self._system_message else 0
        summary_tokens = self._estimate_tokens(self._summary) if self._summary else 0
        used = system_tokens + summary_tokens + self._total_tokens + self.reserve_tokens
        return used > self.max_tokens

    def add_user_message(self, content: str, metadata: dict | None = None) -> Message:
        """Add a user message."""
        return self.add_message(MessageRole.USER, content, metadata=metadata)

    def add_assistant_message(
        self, content: str, metadata: dict | None = None
    ) -> Message:
        """Add an assistant message."""
        return self.add_message(MessageRole.ASSISTANT, content, metadata=metadata)

    def add_tool_message(
        self,
        content: str,
        name: str,
        tool_call_id: str | None = None,
    ) -> Message:
        """Add a tool response message."""
        return self.add_message(
            MessageRole.TOOL, content, name=name, tool_call_id=tool_call_id
        )

    def get_messages(self, include_system: bool = True) -> list[dict]:
        """Get messages in API format.

        Args:
            include_system: Include system message

        Returns:
            List of message dicts for API call
        """
        messages = []

        # System message first
        if include_system and self._system_message:
            messages.append(self._system_message.to_dict())

        # Add summary as a system message if present
        if self._summary:
            messages.append(
                {
                    "role": "system",
                    "content": f"Previous conversation summary:\n{self._summary}",
                }
            )

        # Add all conversation messages
        messages.extend(m.to_dict() for m in self._messages)

        return messages

    def _truncate(self) -> None:
        """Truncate context to fit within limits.

        Strategy:
        1. If summarizer available, summarize older messages
        2. Otherwise, remove oldest messages until within limit
        """
        if not self._messages:
            return

        target_tokens = self.max_tokens - self.reserve_tokens
        system_tokens = self._system_message.tokens if self._system_message else 0
        available = target_tokens - system_tokens

        # Try summarization first
        if self.summarizer and len(self._messages) > 10:
            # Summarize older half of messages
            midpoint = len(self._messages) // 2
            to_summarize = self._messages[:midpoint]

            if to_summarize:
                try:
                    new_summary = self.summarizer(to_summarize)
                    summary_tokens = self._estimate_tokens(new_summary)

                    # Combine with existing summary if present
                    if self._summary:
                        self._summary = f"{self._summary}\n\n{new_summary}"
                    else:
                        self._summary = new_summary

                    # Remove summarized messages
                    removed_tokens = sum(m.tokens for m in to_summarize)
                    self._messages = self._messages[midpoint:]
                    self._total_tokens -= removed_tokens

                    logger.info(
                        f"Summarized {midpoint} messages, freed {removed_tokens} tokens"
                    )
                    return
                except Exception as e:
                    logger.warning(f"Summarization failed: {e}")

        # Fallback: remove oldest messages
        summary_tokens = self._estimate_tokens(self._summary) if self._summary else 0
        available -= summary_tokens

        while self._total_tokens > available and self._messages:
            removed = self._messages.pop(0)
            self._total_tokens -= removed.tokens
            logger.debug(f"Removed message with {removed.tokens} tokens")

    def clear(self) -> None:
        """Clear all messages (keeps system message)."""
        self._messages = []
        self._summary = None
        self._total_tokens = 0

    def get_stats(self) -> ContextWindowStats:
        """Get context window statistics."""
        system_tokens = self._system_message.tokens if self._system_message else 0
        summary_tokens = self._estimate_tokens(self._summary) if self._summary else 0

        user_count = sum(1 for m in self._messages if m.role == MessageRole.USER)
        assistant_count = sum(
            1 for m in self._messages if m.role == MessageRole.ASSISTANT
        )

        total = system_tokens + summary_tokens + self._total_tokens
        utilization = (total / self.max_tokens) * 100 if self.max_tokens > 0 else 0

        return ContextWindowStats(
            total_tokens=total,
            message_count=len(self._messages),
            user_messages=user_count,
            assistant_messages=assistant_count,
            system_tokens=system_tokens,
            available_tokens=self.available_tokens,
            utilization_percent=round(utilization, 1),
        )

    def save_to_memory(
        self,
        workflow_id: str | None = None,
        importance: float = 0.5,
    ) -> list[int]:
        """Save current context to agent memory.

        Args:
            workflow_id: Optional workflow context
            importance: Importance score for memories

        Returns:
            List of memory entry IDs
        """
        if not self.memory:
            return []

        entry_ids = []
        for msg in self._messages:
            content = f"[{msg.role.value}] {msg.content}"
            entry_id = self.memory.store(
                agent_id=self.agent_id,
                content=content,
                memory_type="conversation",
                workflow_id=workflow_id,
                metadata={
                    "role": msg.role.value,
                    "timestamp": msg.timestamp.isoformat(),
                },
                importance=importance,
            )
            entry_ids.append(entry_id)

        return entry_ids

    def load_from_memory(
        self,
        workflow_id: str | None = None,
        limit: int = 20,
    ) -> int:
        """Load recent context from agent memory.

        Args:
            workflow_id: Optional workflow context filter
            limit: Maximum messages to load

        Returns:
            Number of messages loaded
        """
        if not self.memory:
            return 0

        memories = self.memory.recall(
            agent_id=self.agent_id,
            memory_type="conversation",
            workflow_id=workflow_id,
            limit=limit,
        )

        count = 0
        for mem in memories:
            # Parse role from content format "[role] content"
            content = mem.content
            role = MessageRole.USER

            if content.startswith("["):
                end_bracket = content.find("]")
                if end_bracket > 0:
                    role_str = content[1:end_bracket]
                    try:
                        role = MessageRole(role_str)
                    except ValueError:
                        pass
                    content = content[end_bracket + 2 :]  # Skip "] "

            self.add_message(role, content, metadata=mem.metadata)
            count += 1

        return count

    def to_dict(self) -> dict:
        """Serialize context window to dictionary."""
        return {
            "max_tokens": self.max_tokens,
            "reserve_tokens": self.reserve_tokens,
            "agent_id": self.agent_id,
            "system_message": self._system_message.to_dict()
            if self._system_message
            else None,
            "messages": [
                {
                    **m.to_dict(),
                    "tokens": m.tokens,
                    "timestamp": m.timestamp.isoformat(),
                    "metadata": m.metadata,
                }
                for m in self._messages
            ],
            "summary": self._summary,
            "total_tokens": self._total_tokens,
        }

    @classmethod
    def from_dict(cls, data: dict, **kwargs) -> "ContextWindow":
        """Deserialize context window from dictionary."""
        window = cls(
            max_tokens=data.get("max_tokens", 128000),
            reserve_tokens=data.get("reserve_tokens", 4096),
            agent_id=data.get("agent_id", "default"),
            **kwargs,
        )

        if data.get("system_message"):
            sys_msg = data["system_message"]
            window.set_system_message(sys_msg["content"])

        window._summary = data.get("summary")

        for msg_data in data.get("messages", []):
            window._messages.append(Message.from_dict(msg_data))

        window._total_tokens = data.get("total_tokens", 0)

        return window
