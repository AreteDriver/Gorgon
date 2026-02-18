"""Animus bridge — Phase 3 integration between Gorgon and Animus.

Gorgon serves as the orchestration layer for the Animus personal
exocortex, providing multi-agent workflow execution, budget control,
and quality gates. This package implements the bridge conforming to
Animus's protocol interfaces:

    IntelligenceProvider — model abstraction
    MemoryProvider       — episodic/semantic/procedural memory
    SafetyGuard          — action and learning validation
    BaseIntegration      — tool registration

Usage:
    from test_ai.animus import AnimusBridge

    bridge = AnimusBridge()
    bridge.initialize()

    # Store a memory
    from test_ai.animus.models import Memory, MemoryType
    bridge.memory.store(Memory(content="User prefers dark mode", memory_type=MemoryType.SEMANTIC))

    # Check safety
    allowed, reason = bridge.safety.check_action({"description": "deploy to prod"})

    # Get identity context for prompts
    context = bridge.identity.get_identity_context()
"""

from __future__ import annotations

from .config import AnimusBridgeConfig
from .identity import IdentityStore
from .integration import GorgonIntegration
from .intelligence_bridge import GorgonIntelligenceProvider
from .memory_bridge import AnimusMemoryProvider
from .models import Memory, MemorySource, MemoryType, SafetyCheckResult, UserProfile
from .safety_bridge import SafetyGuardBridge

__all__ = [
    "AnimusBridge",
    "AnimusBridgeConfig",
    "AnimusMemoryProvider",
    "GorgonIntelligenceProvider",
    "GorgonIntegration",
    "IdentityStore",
    "Memory",
    "MemorySource",
    "MemoryType",
    "SafetyCheckResult",
    "SafetyGuardBridge",
    "UserProfile",
]


class AnimusBridge:
    """Unified entry point for the Gorgon-Animus bridge.

    Composes all bridge components (identity, memory, safety,
    intelligence, integration) into a single facade with shared
    database backend and configuration.
    """

    def __init__(self, config: AnimusBridgeConfig | None = None):
        self.config = config or AnimusBridgeConfig()
        self.identity: IdentityStore | None = None
        self.memory: AnimusMemoryProvider | None = None
        self.safety: SafetyGuardBridge | None = None
        self.intelligence: GorgonIntelligenceProvider | None = None
        self.integration: GorgonIntegration | None = None
        self._initialized = False

    def initialize(self, db_path: str | None = None) -> None:
        """Initialize all bridge components with a shared database.

        Args:
            db_path: Override database path. Defaults to config value.
        """
        from test_ai.state.backends import SQLiteBackend

        path = db_path or self.config.memory_db_path
        backend = SQLiteBackend(db_path=path)

        self.identity = IdentityStore(backend=backend)
        self.memory = AnimusMemoryProvider(backend=backend)
        self.safety = SafetyGuardBridge(backend=backend, config=self.config)
        self.intelligence = GorgonIntelligenceProvider(config=self.config)
        self.integration = GorgonIntegration(
            config=self.config,
            identity_store=self.identity,
            memory_provider=self.memory,
            safety_guard=self.safety,
        )

        # Load user boundaries into safety guard
        profile = self.identity.get_active_profile()
        if profile and profile.boundaries:
            self.safety.load_boundaries_from_profile(profile.boundaries)

        self._initialized = True

    @property
    def is_initialized(self) -> bool:
        """Whether the bridge has been initialized."""
        return self._initialized
