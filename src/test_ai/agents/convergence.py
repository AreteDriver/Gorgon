"""Adapter between Convergent's IntentResolver and Gorgon's delegation pipeline.

Optional integration — Gorgon works without Convergent installed.
When available, checks delegations for coherence before parallel execution:
overlapping tasks, conflicting agents, redundant work.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

try:
    from convergent import Intent, InterfaceKind, InterfaceSpec

    HAS_CONVERGENT = True
except ImportError:
    HAS_CONVERGENT = False


@dataclass
class ConvergenceResult:
    """Result of checking delegations for coherence."""

    adjustments: list[dict[str, Any]] = field(default_factory=list)
    conflicts: list[dict[str, Any]] = field(default_factory=list)
    dropped_agents: set[str] = field(default_factory=set)

    @property
    def has_conflicts(self) -> bool:
        return len(self.conflicts) > 0


class DelegationConvergenceChecker:
    """Checks delegations for coherence using Convergent's IntentResolver.

    No-ops gracefully when Convergent is not installed.
    """

    def __init__(self, resolver: Any | None = None) -> None:
        self._resolver = resolver
        self._enabled = HAS_CONVERGENT and resolver is not None

    @property
    def enabled(self) -> bool:
        return self._enabled

    def check_delegations(self, delegations: list[dict[str, str]]) -> ConvergenceResult:
        """Check a list of delegations for overlap and conflicts.

        Each delegation is {"agent": str, "task": str}. Publishes each as
        an Intent, then resolves each against the graph.

        Returns:
            ConvergenceResult with any adjustments, conflicts, or agents to drop.
        """
        if not self._enabled:
            return ConvergenceResult()

        result = ConvergenceResult()

        # Publish all delegations as intents
        intents: list[tuple[str, Any]] = []
        for delegation in delegations:
            intent = self._delegation_to_intent(delegation)
            self._resolver.publish(intent)
            intents.append((delegation.get("agent", "unknown"), intent))

        # Resolve each against the graph
        for agent_name, intent in intents:
            resolution = self._resolver.resolve(intent)

            for adj in resolution.adjustments:
                result.adjustments.append(
                    {
                        "agent": agent_name,
                        "kind": adj.kind,
                        "description": adj.description,
                        "confidence": adj.confidence,
                    }
                )
                # If told to consume instead, the agent is redundant
                if adj.kind == "ConsumeInstead" and adj.confidence >= 0.7:
                    result.dropped_agents.add(agent_name)

            for conflict in resolution.conflicts:
                result.conflicts.append(
                    {
                        "agent": agent_name,
                        "description": conflict.description,
                        "their_stability": conflict.their_stability,
                        "confidence": conflict.confidence,
                    }
                )

        return result

    @staticmethod
    def _delegation_to_intent(delegation: dict[str, str]) -> Any:
        """Convert a Gorgon delegation dict to a Convergent Intent."""
        agent = delegation.get("agent", "unknown")
        task = delegation.get("task", "")

        # Infer tags from the agent role
        role_tags = {
            "planner": ["planning", "architecture", "design"],
            "builder": ["implementation", "code", "feature"],
            "tester": ["testing", "qa", "coverage"],
            "reviewer": ["review", "security", "quality"],
            "architect": ["architecture", "design", "system"],
            "documenter": ["documentation", "docs", "guide"],
            "analyst": ["analysis", "data", "metrics"],
        }
        tags = role_tags.get(agent, [agent])

        return Intent(
            agent_id=agent,
            intent=task,
            provides=[
                InterfaceSpec(
                    name=f"{agent}_output",
                    kind=InterfaceKind.FUNCTION,
                    signature="(task: str) -> str",
                    tags=tags,
                ),
            ],
        )
