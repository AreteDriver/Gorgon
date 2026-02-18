"""Animus bridge configuration."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class AnimusBridgeConfig:
    """Configuration for the Gorgon-Animus bridge.

    Controls how Gorgon connects to and exchanges data with Animus.
    """

    # Animus API connection
    animus_url: str = "http://localhost:8420"
    animus_token: str | None = None

    # Memory sync
    sync_memories: bool = True
    memory_db_path: str = "gorgon-animus-memory.db"

    # Identity
    default_profile_name: str = "User"

    # Safety
    enforce_safety_checks: bool = True
    log_safety_checks: bool = True
    block_on_guard_unavailable: bool = False

    # Intelligence provider defaults
    default_model: str = "claude-sonnet-4-20250514"
    default_max_tokens: int = 4096
    default_temperature: float = 0.7

    # Workflow result storage
    store_workflow_results: bool = True
    result_memory_type: str = "episodic"
    result_confidence: float = 0.8

    # Tags applied to all Gorgon-originated memories
    gorgon_tags: list[str] = field(
        default_factory=lambda: ["gorgon", "workflow"]
    )
