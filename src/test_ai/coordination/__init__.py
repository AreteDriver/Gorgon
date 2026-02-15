"""Coordination layer: Convergent ↔ Gorgon workflow integration.

Provides intent-graph-based coordination for parallel workflow execution.
When Convergent is installed, parallel agents publish intents describing
their work and resolve conflicts through shared graph analysis. A stability
gate prevents merging results until agents have converged.

When Convergent is not installed, all coordination classes gracefully
degrade to no-ops — Gorgon continues to work with its standard parallel
execution engine.

Usage::

    from test_ai.coordination import WorkflowCoordinator, StabilityReport

    coordinator = WorkflowCoordinator(min_stability=0.3)
    if coordinator.enabled:
        coordinator.publish_step_intent("step_1", "builder", "Build auth module")
        coordinator.publish_step_intent("step_2", "tester", "Write auth tests")
        report = coordinator.check_stability()
        if report.converged:
            # Safe to merge results
            ...
"""

from .convergent_bridge import (
    HAS_CONVERGENT,
    ConvergentPublisher,
    ResolutionResult,
    StabilityGate,
    StabilityReport,
    StepIntent,
    WorkflowCoordinator,
)
from .parallel_executor import CoordinatedParallelMixin

__all__ = [
    "HAS_CONVERGENT",
    "ConvergentPublisher",
    "CoordinatedParallelMixin",
    "ResolutionResult",
    "StabilityGate",
    "StabilityReport",
    "StepIntent",
    "WorkflowCoordinator",
]
