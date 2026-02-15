"""Bridge between Convergent's intent graph and Gorgon's workflow executor.

This module provides workflow-level coordination using Convergent's intent
resolution engine. When parallel agents execute, each publishes intents
describing what it builds and what interfaces it exposes or requires.
Before merging results, a stability gate checks that agents have converged.

Unlike the delegation-level checker in ``agents/convergence.py`` (which
decides *which* agents to spawn), this bridge coordinates agents *during*
parallel execution — publishing intents, resolving conflicts, and gating
merges on stability scores.

Optional integration — Gorgon works without Convergent installed, falling
back to standard parallel execution with no coordination overhead.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

try:
    from convergent import (
        Intent,
        IntentResolver,
        InterfaceKind,
        InterfaceSpec,
    )

    HAS_CONVERGENT = True
except ImportError:
    HAS_CONVERGENT = False


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class StepIntent:
    """An intent published by a workflow step during parallel execution.

    Attributes:
        step_id: Workflow step identifier.
        agent_role: Role of the agent executing this step (e.g. ``builder``).
        description: Human-readable description of what the step produces.
        provides: Interface names this step exposes to other steps.
        requires: Interface names this step depends on from other steps.
        tags: Free-form tags for overlap detection.
        stability: Current stability score (0.0–1.0) from Convergent.
    """

    step_id: str
    agent_role: str
    description: str
    provides: list[str] = field(default_factory=list)
    requires: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    stability: float = 0.0


@dataclass
class ResolutionResult:
    """Result of resolving a step's intent against the shared graph.

    Attributes:
        step_id: The step that was resolved.
        adjustments: Recommended changes from Convergent.
        conflicts: Detected conflicts with other steps.
        stability: Updated stability score after resolution.
        should_yield: Whether this step should yield to a higher-stability peer.
    """

    step_id: str
    adjustments: list[dict[str, Any]] = field(default_factory=list)
    conflicts: list[dict[str, Any]] = field(default_factory=list)
    stability: float = 0.0
    should_yield: bool = False


@dataclass
class StabilityReport:
    """Aggregate stability report across all parallel steps.

    Attributes:
        converged: Whether all steps meet the minimum stability threshold.
        mean_stability: Average stability across all steps.
        min_stability: Lowest individual step stability.
        step_stabilities: Per-step stability scores.
        unresolved_conflicts: Conflicts that remain after resolution.
        passes: Number of resolution passes executed.
    """

    converged: bool = False
    mean_stability: float = 0.0
    min_stability: float = 0.0
    step_stabilities: dict[str, float] = field(default_factory=dict)
    unresolved_conflicts: list[dict[str, Any]] = field(default_factory=list)
    passes: int = 0


# ---------------------------------------------------------------------------
# ConvergentPublisher — one per parallel step
# ---------------------------------------------------------------------------


class ConvergentPublisher:
    """Publishes intents for a single workflow step into the shared graph.

    Each parallel agent receives its own publisher. The publisher converts
    step metadata into a Convergent ``Intent`` and publishes it to the
    shared ``IntentResolver``.
    """

    def __init__(
        self,
        resolver: Any,
        step_id: str,
        agent_role: str,
    ) -> None:
        self._resolver = resolver
        self._step_id = step_id
        self._agent_role = agent_role
        self._published: Intent | None = None

    @property
    def step_id(self) -> str:
        return self._step_id

    def publish(
        self,
        description: str,
        provides: list[str] | None = None,
        requires: list[str] | None = None,
        tags: list[str] | None = None,
    ) -> StepIntent:
        """Publish an intent describing what this step builds.

        Args:
            description: What the step produces.
            provides: Interface names exposed to other steps.
            requires: Interface names consumed from other steps.
            tags: Free-form tags for overlap/conflict detection.

        Returns:
            StepIntent with the published information.
        """
        provides = provides or []
        requires = requires or []
        tags = tags or _role_tags(self._agent_role)

        intent = _build_intent(
            step_id=self._step_id,
            agent_role=self._agent_role,
            description=description,
            provides=provides,
            requires=requires,
            tags=tags,
        )
        self._resolver.publish(intent)
        self._published = intent

        return StepIntent(
            step_id=self._step_id,
            agent_role=self._agent_role,
            description=description,
            provides=provides,
            requires=requires,
            tags=tags,
        )

    def resolve(self) -> ResolutionResult:
        """Resolve this step's intent against the shared graph.

        Should be called before major decisions to check for compatibility
        with other agents' high-stability decisions.

        Returns:
            ResolutionResult with adjustments, conflicts, and stability.
        """
        if self._published is None:
            return ResolutionResult(step_id=self._step_id)

        resolution = self._resolver.resolve(self._published)

        adjustments = []
        should_yield = False
        for adj in resolution.adjustments:
            entry = {
                "kind": adj.kind,
                "description": adj.description,
                "confidence": adj.confidence,
            }
            adjustments.append(entry)
            if adj.kind == "ConsumeInstead" and adj.confidence >= 0.7:
                should_yield = True

        conflicts = []
        for conflict in resolution.conflicts:
            conflicts.append(
                {
                    "description": conflict.description,
                    "their_stability": conflict.their_stability,
                    "confidence": conflict.confidence,
                }
            )

        stability = getattr(resolution, "stability", 0.0)

        return ResolutionResult(
            step_id=self._step_id,
            adjustments=adjustments,
            conflicts=conflicts,
            stability=stability,
            should_yield=should_yield,
        )


# ---------------------------------------------------------------------------
# StabilityGate — checks convergence before merge
# ---------------------------------------------------------------------------


class StabilityGate:
    """Gates parallel merge on Convergent stability scores.

    Before allowing parallel step results to merge, the gate verifies
    that all steps have reached a minimum stability threshold. If not,
    it triggers additional resolution passes.

    Args:
        resolver: Convergent ``IntentResolver`` instance.
        min_stability: Minimum stability required for convergence (0.0–1.0).
        max_passes: Maximum resolution passes before accepting current state.
    """

    DEFAULT_MIN_STABILITY = 0.3
    DEFAULT_MAX_PASSES = 3

    def __init__(
        self,
        resolver: Any,
        min_stability: float | None = None,
        max_passes: int | None = None,
    ) -> None:
        self._resolver = resolver
        self._min_stability = (
            min_stability if min_stability is not None else self.DEFAULT_MIN_STABILITY
        )
        self._max_passes = (
            max_passes if max_passes is not None else self.DEFAULT_MAX_PASSES
        )

    @property
    def min_stability(self) -> float:
        return self._min_stability

    def check(self, publishers: list[ConvergentPublisher]) -> StabilityReport:
        """Check whether all parallel steps have converged.

        Runs up to ``max_passes`` resolution cycles. Each pass resolves
        every publisher's intent against the graph, collecting stability
        scores. If all scores exceed ``min_stability``, convergence is
        declared.

        Args:
            publishers: List of publishers, one per parallel step.

        Returns:
            StabilityReport with convergence status and details.
        """
        stabilities: dict[str, float] = {}
        all_conflicts: list[dict[str, Any]] = []

        for pass_num in range(1, self._max_passes + 1):
            stabilities.clear()
            all_conflicts.clear()

            for pub in publishers:
                result = pub.resolve()
                stabilities[pub.step_id] = result.stability
                all_conflicts.extend(result.conflicts)

            if not stabilities:
                return StabilityReport(converged=True, passes=pass_num)

            min_s = min(stabilities.values())
            mean_s = sum(stabilities.values()) / len(stabilities)

            if min_s >= self._min_stability:
                return StabilityReport(
                    converged=True,
                    mean_stability=mean_s,
                    min_stability=min_s,
                    step_stabilities=dict(stabilities),
                    unresolved_conflicts=all_conflicts,
                    passes=pass_num,
                )

            logger.debug(
                "Stability gate pass %d/%d: min=%.3f (threshold=%.3f)",
                pass_num,
                self._max_passes,
                min_s,
                self._min_stability,
            )

        # Exhausted passes — return current state
        min_s = min(stabilities.values()) if stabilities else 0.0
        mean_s = sum(stabilities.values()) / len(stabilities) if stabilities else 0.0
        return StabilityReport(
            converged=False,
            mean_stability=mean_s,
            min_stability=min_s,
            step_stabilities=dict(stabilities),
            unresolved_conflicts=all_conflicts,
            passes=self._max_passes,
        )


# ---------------------------------------------------------------------------
# WorkflowCoordinator — orchestrates the full coordination lifecycle
# ---------------------------------------------------------------------------


class WorkflowCoordinator:
    """Orchestrates Convergent coordination for a parallel workflow group.

    Manages the lifecycle of intent publishing, resolution, and stability
    gating across a set of parallel steps.

    Args:
        min_stability: Minimum stability for the gate (default 0.3).
        max_resolution_passes: Max resolution passes (default 3).
    """

    def __init__(
        self,
        min_stability: float = 0.3,
        max_resolution_passes: int = 3,
    ) -> None:
        self._min_stability = min_stability
        self._max_passes = max_resolution_passes
        self._resolver: Any | None = None
        self._gate: StabilityGate | None = None
        self._publishers: dict[str, ConvergentPublisher] = {}
        self._enabled = False
        self._setup()

    def _setup(self) -> None:
        """Initialize Convergent resolver and gate if available."""
        if not HAS_CONVERGENT:
            logger.debug("Convergent not installed — coordination disabled")
            return

        try:
            self._resolver = IntentResolver(min_stability=0.0)
            self._gate = StabilityGate(
                resolver=self._resolver,
                min_stability=self._min_stability,
                max_passes=self._max_passes,
            )
            self._enabled = True
            logger.debug("Workflow coordinator initialized")
        except Exception as exc:
            logger.warning("Failed to initialize workflow coordinator: %s", exc)

    @property
    def enabled(self) -> bool:
        """Whether Convergent coordination is active."""
        return self._enabled

    @property
    def min_stability(self) -> float:
        """Minimum stability threshold for convergence gating."""
        return self._min_stability

    def create_publisher(
        self,
        step_id: str,
        agent_role: str,
    ) -> ConvergentPublisher | None:
        """Create a publisher for a parallel step.

        Args:
            step_id: Workflow step identifier.
            agent_role: Agent role executing this step.

        Returns:
            ConvergentPublisher if coordination is enabled, None otherwise.
        """
        if not self._enabled or self._resolver is None:
            return None

        pub = ConvergentPublisher(
            resolver=self._resolver,
            step_id=step_id,
            agent_role=agent_role,
        )
        self._publishers[step_id] = pub
        return pub

    def publish_step_intent(
        self,
        step_id: str,
        agent_role: str,
        description: str,
        provides: list[str] | None = None,
        requires: list[str] | None = None,
        tags: list[str] | None = None,
    ) -> StepIntent | None:
        """Convenience: create a publisher and immediately publish an intent.

        Args:
            step_id: Step identifier.
            agent_role: Agent role for this step.
            description: What the step produces.
            provides: Exposed interfaces.
            requires: Consumed interfaces.
            tags: Free-form tags.

        Returns:
            StepIntent if published, None if coordination is disabled.
        """
        pub = self.create_publisher(step_id, agent_role)
        if pub is None:
            return None
        return pub.publish(
            description=description,
            provides=provides,
            requires=requires,
            tags=tags,
        )

    def check_stability(self) -> StabilityReport:
        """Run the stability gate across all registered publishers.

        Returns:
            StabilityReport. If coordination is disabled, returns a report
            with ``converged=True`` (no-op pass-through).
        """
        if not self._enabled or self._gate is None:
            return StabilityReport(converged=True)

        publishers = list(self._publishers.values())
        if not publishers:
            return StabilityReport(converged=True)

        start = time.monotonic()
        report = self._gate.check(publishers)
        elapsed_ms = int((time.monotonic() - start) * 1000)

        if report.converged:
            logger.info(
                "Stability gate passed: mean=%.3f min=%.3f passes=%d (%dms)",
                report.mean_stability,
                report.min_stability,
                report.passes,
                elapsed_ms,
            )
        else:
            logger.warning(
                "Stability gate FAILED: mean=%.3f min=%.3f "
                "threshold=%.3f passes=%d (%dms)",
                report.mean_stability,
                report.min_stability,
                self._min_stability,
                report.passes,
                elapsed_ms,
            )
        return report

    def reset(self) -> None:
        """Reset the coordinator for a new parallel group."""
        self._publishers.clear()
        if self._enabled and HAS_CONVERGENT:
            try:
                self._resolver = IntentResolver(min_stability=0.0)
                self._gate = StabilityGate(
                    resolver=self._resolver,
                    min_stability=self._min_stability,
                    max_passes=self._max_passes,
                )
            except Exception as exc:
                logger.warning("Failed to reset coordinator: %s", exc)
                self._enabled = False


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _role_tags(agent_role: str) -> list[str]:
    """Derive default tags from an agent role name."""
    mapping = {
        "planner": ["planning", "architecture", "design"],
        "builder": ["implementation", "code", "feature"],
        "tester": ["testing", "qa", "coverage"],
        "reviewer": ["review", "security", "quality"],
        "architect": ["architecture", "design", "system"],
        "documenter": ["documentation", "docs", "guide"],
        "analyst": ["analysis", "data", "metrics"],
    }
    return mapping.get(agent_role, [agent_role])


def _build_intent(
    step_id: str,
    agent_role: str,
    description: str,
    provides: list[str],
    requires: list[str],
    tags: list[str],
) -> Any:
    """Build a Convergent ``Intent`` from step metadata.

    Only called when ``HAS_CONVERGENT`` is True.
    """
    # Signatures are synthetic placeholders for Convergent's overlap detection.
    # They don't represent real function signatures — just provide enough
    # structural differentiation for the resolver to distinguish interfaces.
    provide_specs = [
        InterfaceSpec(
            name=name,
            kind=InterfaceKind.FUNCTION,
            signature=f"() -> {name}_output",
            tags=tags,
        )
        for name in provides
    ]

    require_specs = [
        InterfaceSpec(
            name=name,
            kind=InterfaceKind.FUNCTION,
            signature=f"({name}_input) -> None",
            tags=tags,
        )
        for name in requires
    ]

    return Intent(
        agent_id=step_id,
        intent=description,
        provides=provide_specs,
        requires=require_specs,
    )
