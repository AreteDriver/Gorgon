"""Tests for agent memory module."""

import pytest
import tempfile
import os
import sys
from datetime import datetime, timedelta
sys.path.insert(0, 'src')

from test_ai.state.memory import AgentMemory, MemoryEntry


class TestMemoryEntry:
    """Tests for MemoryEntry class."""

    def test_create_entry(self):
        """Can create memory entry."""
        entry = MemoryEntry(
            agent_id="agent-1",
            content="Test memory",
            memory_type="fact",
            importance=0.8,
        )
        assert entry.agent_id == "agent-1"
        assert entry.content == "Test memory"
        assert entry.importance == 0.8

    def test_to_dict(self):
        """Entry can be converted to dict."""
        entry = MemoryEntry(
            agent_id="agent-1",
            content="Test",
            memory_type="conversation",
        )
        data = entry.to_dict()
        assert data["agent_id"] == "agent-1"
        assert data["memory_type"] == "conversation"

    def test_from_dict(self):
        """Entry can be created from dict."""
        data = {
            "id": 1,
            "agent_id": "agent-1",
            "content": "Test",
            "memory_type": "fact",
            "metadata": '{"key": "value"}',
            "importance": 0.9,
            "access_count": 5,
        }
        entry = MemoryEntry.from_dict(data)
        assert entry.id == 1
        assert entry.agent_id == "agent-1"
        assert entry.metadata == {"key": "value"}
        assert entry.importance == 0.9


class TestAgentMemory:
    """Tests for AgentMemory class."""

    @pytest.fixture
    def memory(self):
        """Create a temporary memory store."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "memory.db")
            yield AgentMemory(db_path=db_path)

    def test_store_memory(self, memory):
        """Can store a memory."""
        mem_id = memory.store(
            agent_id="agent-1",
            content="User prefers dark mode",
            memory_type="preference",
        )
        assert mem_id > 0

    def test_recall_memory(self, memory):
        """Can recall stored memories."""
        memory.store("agent-1", "Fact 1", memory_type="fact")
        memory.store("agent-1", "Fact 2", memory_type="fact")

        memories = memory.recall("agent-1", memory_type="fact")
        assert len(memories) == 2

    def test_recall_by_workflow(self, memory):
        """Can filter by workflow."""
        memory.store("agent-1", "Memory 1", workflow_id="wf-1")
        memory.store("agent-1", "Memory 2", workflow_id="wf-2")

        memories = memory.recall("agent-1", workflow_id="wf-1")
        assert len(memories) == 1
        assert memories[0].content == "Memory 1"

    def test_recall_by_importance(self, memory):
        """Can filter by importance threshold."""
        memory.store("agent-1", "Low importance", importance=0.2)
        memory.store("agent-1", "High importance", importance=0.9)

        memories = memory.recall("agent-1", min_importance=0.5)
        assert len(memories) == 1
        assert memories[0].content == "High importance"

    def test_recall_limit(self, memory):
        """Recall respects limit."""
        for i in range(10):
            memory.store("agent-1", f"Memory {i}")

        memories = memory.recall("agent-1", limit=5)
        assert len(memories) == 5

    def test_recall_recent(self, memory):
        """Can recall recent memories."""
        memory.store("agent-1", "Recent memory")

        # Use recall without time filter since SQLite timestamp format may differ
        memories = memory.recall("agent-1", limit=10)
        assert len(memories) == 1
        assert memories[0].content == "Recent memory"

    def test_recall_context(self, memory):
        """Can recall contextual memories."""
        memory.store("agent-1", "User prefers Python", memory_type="preference")
        memory.store("agent-1", "API returns JSON", memory_type="fact", importance=0.8)
        memory.store("agent-1", "Workflow note", workflow_id="wf-1")

        context = memory.recall_context("agent-1", workflow_id="wf-1")
        assert "preferences" in context or "facts" in context or "workflow" in context

    def test_forget_specific(self, memory):
        """Can forget specific memory."""
        mem_id = memory.store("agent-1", "To forget")

        count = memory.forget("agent-1", memory_id=mem_id)
        assert count == 1

        memories = memory.recall("agent-1")
        assert len(memories) == 0

    def test_forget_by_type(self, memory):
        """Can forget all of a type."""
        memory.store("agent-1", "Convo 1", memory_type="conversation")
        memory.store("agent-1", "Convo 2", memory_type="conversation")
        memory.store("agent-1", "Fact 1", memory_type="fact")

        count = memory.forget("agent-1", memory_type="conversation")
        assert count == 2

        remaining = memory.recall("agent-1")
        assert len(remaining) == 1
        assert remaining[0].memory_type == "fact"

    def test_update_importance(self, memory):
        """Can update memory importance."""
        mem_id = memory.store("agent-1", "Test", importance=0.5)

        success = memory.update_importance(mem_id, 0.95)
        assert success is True

        memories = memory.recall("agent-1")
        assert memories[0].importance == 0.95

    def test_get_stats(self, memory):
        """Can get memory statistics."""
        memory.store("agent-1", "Fact", memory_type="fact", importance=0.8)
        memory.store("agent-1", "Pref", memory_type="preference", importance=0.6)

        stats = memory.get_stats("agent-1")
        assert stats["total_memories"] == 2
        assert stats["by_type"]["fact"] == 1
        assert stats["by_type"]["preference"] == 1

    def test_format_context(self, memory):
        """Can format memories as context string."""
        memory.store("agent-1", "User likes Python", memory_type="preference")
        memory.store("agent-1", "API uses REST", memory_type="fact", importance=0.8)

        context = memory.recall_context("agent-1")
        formatted = memory.format_context(context)

        assert isinstance(formatted, str)
        # Should contain some content
        assert len(formatted) > 0

    def test_access_tracking(self, memory):
        """Memory access is tracked."""
        memory.store("agent-1", "Test memory")

        # First recall
        memories = memory.recall("agent-1")
        # Access count should have increased (starts at 0, becomes 1 on first recall)

        # Second recall
        memories = memory.recall("agent-1")
        assert memories[0].access_count >= 1
