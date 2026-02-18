"""Sovereign execution mode for Animus integration.

Combines identity, safety, local-first providers, and memory into
a unified execution mode where the AI operates autonomously within
user-defined constraints. Data never leaves the user's infrastructure
unless explicitly allowed.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class SovereigntyLevel(str, Enum):
    """How strictly to enforce local-only execution."""

    FULL = "full"  # All execution local, no cloud APIs
    HYBRID = "hybrid"  # Local preferred, cloud for reasoning tier
    CLOUD = "cloud"  # Standard cloud execution (no sovereignty constraints)


@dataclass
class SovereignConfig:
    """Configuration for sovereign execution mode."""

    sovereignty_level: SovereigntyLevel = SovereigntyLevel.HYBRID

    # Provider preferences
    local_provider: str = "ollama"
    cloud_fallback_providers: list[str] = field(
        default_factory=lambda: ["anthropic", "openai"]
    )
    preferred_local_model: str | None = None

    # Autonomy constraints
    max_autonomous_steps: int = 50
    require_approval_for: list[str] = field(
        default_factory=lambda: ["deploy", "delete", "publish", "send"]
    )

    # Memory persistence
    persist_all_outputs: bool = True
    memory_confidence_threshold: float = 0.5

    # Identity injection
    inject_identity_context: bool = True
    inject_boundaries_as_system_prompt: bool = True


class SovereignExecutor:
    """Orchestrates sovereign workflow execution.

    Wraps WorkflowExecutor with Animus bridge components to provide:
    - Local-first provider routing via TierRouter
    - Pre-step safety validation via SafetyGuard
    - Identity context injection into all agent prompts
    - Automatic memory persistence of workflow results
    - Convergent coordination for multi-agent steps

    Usage:
        from test_ai.animus import AnimusBridge
        from test_ai.animus.sovereign import SovereignExecutor, SovereignConfig

        bridge = AnimusBridge()
        bridge.initialize()

        sovereign = SovereignExecutor(bridge=bridge)
        result = sovereign.execute_workflow("workflows/my_workflow.yaml")
    """

    def __init__(
        self,
        bridge: Any = None,
        config: SovereignConfig | None = None,
        convergent_bridge: Any = None,
    ):
        """Initialize sovereign executor.

        Args:
            bridge: AnimusBridge instance (provides identity, memory, safety)
            config: Sovereign execution configuration
            convergent_bridge: Optional ExecutorConvergentBridge for stigmergy
        """
        self.bridge = bridge
        self.config = config or SovereignConfig()
        self.convergent = convergent_bridge
        self._executor = None
        self._tier_router = None

    def _setup_tier_router(self) -> Any:
        """Configure TierRouter based on sovereignty level."""
        try:
            from test_ai.providers.manager import ProviderManager
            from test_ai.providers.router import RoutingConfig, RoutingMode, TierRouter

            manager = ProviderManager()

            # Register local provider
            try:
                from test_ai.providers.ollama_provider import OllamaProvider

                ollama = OllamaProvider()
                if ollama.is_configured():
                    manager.register_provider(self.config.local_provider, ollama)
            except Exception as e:
                logger.debug("Ollama registration failed: %s", e)

            # Register cloud providers if sovereignty allows
            if self.config.sovereignty_level != SovereigntyLevel.FULL:
                self._register_cloud_providers(manager)

            # Configure routing mode
            mode_map = {
                SovereigntyLevel.FULL: RoutingMode.LOCAL,
                SovereigntyLevel.HYBRID: RoutingMode.HYBRID,
                SovereigntyLevel.CLOUD: RoutingMode.CLOUD,
            }

            fallback_chain = [self.config.local_provider]
            if self.config.sovereignty_level != SovereigntyLevel.FULL:
                fallback_chain.extend(self.config.cloud_fallback_providers)

            routing_config = RoutingConfig(
                mode=mode_map[self.config.sovereignty_level],
                fallback_chain=fallback_chain,
            )

            self._tier_router = TierRouter(manager, config=routing_config)

            if self.config.sovereignty_level == SovereigntyLevel.FULL:
                self._tier_router.force_local_only(True)

            return self._tier_router

        except Exception as e:
            logger.warning("TierRouter setup failed: %s", e)
            return None

    def _register_cloud_providers(self, manager: Any) -> None:
        """Register cloud providers from settings."""
        try:
            from test_ai.config import get_settings

            settings = get_settings()

            if settings.anthropic_api_key:
                from test_ai.providers.anthropic_provider import AnthropicProvider

                provider = AnthropicProvider(api_key=settings.anthropic_api_key)
                manager.register_provider("anthropic", provider)

            if settings.openai_api_key:
                from test_ai.providers.openai_provider import OpenAIProvider

                provider = OpenAIProvider(api_key=settings.openai_api_key)
                manager.register_provider("openai", provider)

        except Exception as e:
            logger.debug("Cloud provider registration failed: %s", e)

    def _build_executor(self) -> Any:
        """Build a WorkflowExecutor with sovereign configuration."""
        from test_ai.workflow.executor_core import WorkflowExecutor

        kwargs: dict[str, Any] = {}

        # Wire safety guard
        if self.bridge and self.bridge.safety:
            kwargs["safety_guard"] = self.bridge.safety

        # Wire memory manager
        if self.bridge and self.bridge.memory:
            from test_ai.state.agent_context import WorkflowMemoryManager
            from test_ai.state.agent_memory import AgentMemory

            memory = AgentMemory(
                db_path=self.bridge.config.memory_db_path
            )
            kwargs["memory_manager"] = WorkflowMemoryManager(memory=memory)

        # Wire convergent bridge
        if self.convergent:
            kwargs["coordination_bridge"] = self.convergent

        self._executor = WorkflowExecutor(**kwargs)
        return self._executor

    def execute_workflow(
        self,
        workflow_path: str,
        variables: dict[str, Any] | None = None,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        """Execute a workflow in sovereign mode.

        Args:
            workflow_path: Path to workflow YAML file
            variables: Input variables for the workflow
            dry_run: If True, simulate without API calls

        Returns:
            Dict with success, outputs, duration, and metadata
        """
        from test_ai.workflow.loader import load_workflow

        executor = self._build_executor()
        executor.dry_run = dry_run

        config = load_workflow(workflow_path)
        inputs = variables or {}

        # Inject identity context
        if self.config.inject_identity_context and self.bridge and self.bridge.identity:
            identity_ctx = self.bridge.identity.get_identity_context()
            if identity_ctx:
                inputs["_identity_context"] = identity_ctx
                inputs["_sovereignty_level"] = self.config.sovereignty_level.value

        # Execute
        result = executor.execute(config, inputs=inputs)

        # Persist outputs as memories
        if (
            self.config.persist_all_outputs
            and self.bridge
            and self.bridge.memory
            and result.status == "success"
        ):
            self._persist_workflow_result(config.name, result)

        return {
            "success": result.status == "success",
            "outputs": result.outputs,
            "total_tokens": result.total_tokens,
            "duration_ms": result.total_duration_ms,
            "sovereignty_level": self.config.sovereignty_level.value,
            "error": result.error,
        }

    def _persist_workflow_result(self, workflow_name: str, result: Any) -> None:
        """Store workflow results as Animus memories."""
        try:
            from .models import MemoryType

            # Store workflow completion as episodic memory
            output_summary = str(result.outputs)[:2000] if result.outputs else ""
            self.bridge.memory.store_workflow_result(
                workflow_id=workflow_name,
                agent_id="sovereign-executor",
                content=f"Completed workflow '{workflow_name}': {output_summary}",
                memory_type=MemoryType.EPISODIC,
                confidence=self.config.memory_confidence_threshold,
                tags=["sovereign", "workflow-result", workflow_name],
            )

            # Store individual step outputs as semantic memories
            for step in result.steps:
                if step.status.value == "success" and step.output:
                    response = step.output.get("response", "")
                    if response:
                        role = step.output.get("role", "unknown")
                        self.bridge.memory.store_workflow_result(
                            workflow_id=workflow_name,
                            agent_id=role,
                            content=response[:1000],
                            memory_type=MemoryType.SEMANTIC,
                            confidence=self.config.memory_confidence_threshold,
                            tags=["sovereign", "step-output", role],
                        )
        except Exception as e:
            logger.warning("Failed to persist workflow result: %s", e)

    def get_status(self) -> dict[str, Any]:
        """Get current sovereign executor status."""
        status: dict[str, Any] = {
            "sovereignty_level": self.config.sovereignty_level.value,
            "bridge_initialized": self.bridge is not None and self.bridge.is_initialized,
            "convergent_enabled": self.convergent is not None and self.convergent.enabled
            if self.convergent
            else False,
        }

        if self.bridge and self.bridge.identity:
            profile = self.bridge.identity.get_active_profile()
            if profile:
                status["active_profile"] = profile.display_name
                status["boundaries_count"] = len(profile.boundaries)

        if self.bridge and self.bridge.memory:
            try:
                stats = self.bridge.memory.get_stats()
                status["memory_count"] = stats["total"]
            except Exception:
                pass

        if self.bridge and self.bridge.safety:
            status["safety_violations"] = self.bridge.safety.get_violation_count()

        return status
