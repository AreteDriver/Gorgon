"""Convergent integration for WorkflowExecutor.

Wires stigmergy enrichment, outcome recording, and coherence checking
into the workflow execution pipeline. This bridges the gap between the
SupervisorAgent's Convergent integration and the WorkflowExecutor.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

try:
    from test_ai.agents.convergence import (
        HAS_CONVERGENT,
        ConvergenceResult,
        DelegationConvergenceChecker,
        create_checker,
        format_convergence_alert,
    )
except ImportError:
    HAS_CONVERGENT = False


class ExecutorConvergentBridge:
    """Bridges the Convergent coordination library into WorkflowExecutor.

    Provides three integration points:
    1. Stigmergy enrichment — inject trail markers into AI step prompts
    2. Outcome recording — record step results for future trail building
    3. Coherence checking — filter redundant parallel steps

    Gracefully no-ops when Convergent is not installed.
    """

    def __init__(self, coordination_bridge: Any = None) -> None:
        """Initialize with an optional GorgonBridge instance.

        Args:
            coordination_bridge: A GorgonBridge from convergent library.
                                 Obtained via ``convergence.create_bridge()``.
        """
        self._bridge = coordination_bridge
        self._checker: DelegationConvergenceChecker | None = None
        self._enabled = HAS_CONVERGENT and coordination_bridge is not None

        if self._enabled:
            self._checker = create_checker()
            logger.info("ExecutorConvergentBridge enabled")
        else:
            logger.debug("ExecutorConvergentBridge disabled (no bridge)")

    @property
    def enabled(self) -> bool:
        """Whether Convergent integration is active."""
        return self._enabled

    # --- Stigmergy enrichment ---

    def enrich_prompt(
        self,
        agent_id: str,
        prompt: str,
        file_paths: list[str] | None = None,
    ) -> str:
        """Inject stigmergy trail markers into a prompt.

        Called before AI step execution to give the agent context from
        previous runs of the same or related agents.

        Args:
            agent_id: Agent role (e.g., "builder", "tester")
            prompt: The original prompt
            file_paths: Optional file paths for context

        Returns:
            Enriched prompt with trail markers appended
        """
        if not self._enabled or self._bridge is None:
            return prompt

        try:
            enrichment = self._bridge.enrich_prompt(
                agent_id=agent_id,
                task_description=prompt,
                file_paths=file_paths or [],
                current_work=prompt,
            )
            if enrichment:
                return prompt + "\n\n" + enrichment
        except Exception as e:
            logger.debug("Stigmergy enrichment failed (non-fatal): %s", e)

        return prompt

    # --- Outcome recording ---

    def record_outcome(
        self,
        agent_id: str,
        step_id: str,
        success: bool,
        skill_domain: str | None = None,
    ) -> None:
        """Record a step outcome for stigmergy trail building.

        Called after step completion so future runs can benefit from
        trail markers left by this execution.

        Args:
            agent_id: Agent role
            step_id: Step identifier
            success: Whether the step succeeded
            skill_domain: Optional skill domain override
        """
        if not self._enabled or self._bridge is None:
            return

        try:
            outcome = "approved" if success else "failed"
            self._bridge.record_task_outcome(
                agent_id=agent_id,
                skill_domain=skill_domain or agent_id,
                outcome=outcome,
            )
        except Exception as e:
            logger.debug("Outcome recording failed (non-fatal): %s", e)

    # --- Coherence checking ---

    def check_parallel_coherence(
        self,
        steps: list[dict[str, str]],
    ) -> ConvergenceResult | None:
        """Check parallel steps for overlap and redundancy.

        Called before parallel group execution to filter out redundant steps.

        Args:
            steps: List of {"agent": role, "task": description} dicts

        Returns:
            ConvergenceResult with adjustments, conflicts, dropped_agents.
            None if Convergent is not available.
        """
        if not self._enabled or self._checker is None:
            return None

        try:
            result = self._checker.check_delegations(steps)
            if result.has_conflicts or result.dropped_agents:
                alert = format_convergence_alert(result)
                logger.info("Convergence check:\n%s", alert)
            return result
        except Exception as e:
            logger.debug("Coherence check failed (non-fatal): %s", e)
            return None

    # --- Lifecycle ---

    def close(self) -> None:
        """Close the underlying coordination bridge."""
        if self._bridge is not None:
            try:
                self._bridge.close()
            except Exception:
                pass
