"""Coordination-aware parallel executor for Gorgon workflows.

Extends the existing parallel group execution with Convergent intent
publishing, resolution, and stability-gated merging:

1. **Before execution** — publishes intents for each parallel step,
   describing what it builds and what interfaces it exposes/requires.
2. **After execution** — runs the stability gate. If agents haven't
   converged (stability below threshold), triggers additional resolution
   passes before allowing merge.
3. **Fallback** — if Convergent is not installed, delegates directly to
   the standard ``ParallelGroupMixin`` with zero overhead.

This module is designed as a mixin that composes alongside
``ParallelGroupMixin``. The ``WorkflowExecutor`` uses
``CoordinatedParallelMixin`` instead of calling ``_execute_parallel_group``
directly when coordination is enabled.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from test_ai.workflow.executor_results import StepStatus
from test_ai.workflow.loader import StepConfig

from .convergent_bridge import (
    HAS_CONVERGENT,
    StabilityReport,
    WorkflowCoordinator,
)

logger = logging.getLogger(__name__)


class CoordinatedParallelMixin:
    """Mixin providing Convergent-coordinated parallel group execution.

    Wraps the existing ``ParallelGroupMixin._execute_parallel_group`` and
    ``_execute_parallel_group_async`` methods with intent publishing and
    stability gating.

    Configuration is read from ``workflow.settings``:
    - ``coordination_enabled`` — opt-in flag (default ``False``).
    - ``coordination_min_stability`` — gate threshold (default ``0.3``).
    - ``coordination_max_passes`` — max resolution passes (default ``3``).

    When coordination is disabled (flag off, or Convergent not installed),
    this mixin delegates directly to the parent parallel group methods.

    Expects the host class to also inherit from ``ParallelGroupMixin``
    and expose the following from the executor:
    - ``_execute_step(step, workflow_id) -> StepResult``
    - ``_record_step_completion(step, step_result, result) -> None``
    - ``_handle_step_failure(step, step_result, result, workflow_id) -> str``
    - ``_store_step_outputs(step, step_result) -> None``
    """

    def _get_coordinator(self, workflow_settings: Any) -> WorkflowCoordinator | None:
        """Create a coordinator from workflow settings if coordination is enabled.

        Args:
            workflow_settings: ``WorkflowSettings`` from the current workflow.

        Returns:
            WorkflowCoordinator if enabled, None otherwise.
        """
        if not HAS_CONVERGENT:
            return None

        enabled = getattr(workflow_settings, "coordination_enabled", False)
        if not enabled:
            return None

        min_stab = getattr(
            workflow_settings,
            "coordination_min_stability",
            0.3,
        )
        max_passes = getattr(
            workflow_settings,
            "coordination_max_passes",
            3,
        )

        coordinator = WorkflowCoordinator(
            min_stability=min_stab,
            max_resolution_passes=max_passes,
        )
        return coordinator if coordinator.enabled else None

    @staticmethod
    def _publish_intents(
        steps: list[StepConfig],
        coordinator: WorkflowCoordinator,
    ) -> None:
        """Publish intents for each step in a parallel group.

        Args:
            steps: Steps to publish intents for.
            coordinator: Active WorkflowCoordinator.
        """
        for step in steps:
            agent_role = step.params.get("role", step.type)
            description = step.params.get(
                "prompt",
                step.params.get("command", f"Execute {step.id}"),
            )
            provides = step.outputs or []
            requires = list(step.depends_on) if step.depends_on else []

            coordinator.publish_step_intent(
                step_id=step.id,
                agent_role=agent_role,
                description=description[:200],
                provides=provides,
                requires=requires,
            )

        logger.info(
            "Published %d intents for parallel group [%s]",
            len(steps),
            ", ".join(s.id for s in steps),
        )

    @staticmethod
    def _log_coordination_result(
        report: StabilityReport,
        coordinator: WorkflowCoordinator,
        elapsed_ms: int,
        result: Any,
        label: str = "parallel group",
    ) -> None:
        """Log the outcome of a coordinated parallel group execution.

        Args:
            report: StabilityReport from the gate check.
            coordinator: Active WorkflowCoordinator.
            elapsed_ms: Wall-clock time for the coordinated execution.
            result: ExecutionResult to check for failure status.
            label: Descriptive label for log messages.
        """
        if not report.converged and result.status != "failed":
            logger.warning(
                "Coordinated %s did not converge (min_stability=%.3f, "
                "threshold=%.3f). Proceeding with degraded confidence.",
                label,
                report.min_stability,
                coordinator.min_stability,
            )

        logger.info(
            "Coordinated %s complete: converged=%s "
            "mean_stability=%.3f passes=%d (%dms)",
            label,
            report.converged,
            report.mean_stability,
            report.passes,
            elapsed_ms,
        )

    def _coordinated_execute_parallel_group(
        self,
        steps: list[StepConfig],
        workflow_id: str | None,
        result: Any,
        max_workers: int,
        coordinator: WorkflowCoordinator,
    ) -> StabilityReport:
        """Execute a parallel group with Convergent coordination.

        Lifecycle:
        1. Publish intents for each step.
        2. Delegate to parent ``_execute_parallel_group``.
        3. Run stability gate on results.
        4. Log coordination metrics.

        Args:
            steps: Steps to execute in parallel.
            workflow_id: Current workflow ID.
            result: ExecutionResult to update.
            max_workers: Maximum concurrent workers.
            coordinator: Active WorkflowCoordinator.

        Returns:
            StabilityReport from the post-execution gate check.
        """
        start_time = time.monotonic()

        self._publish_intents(steps, coordinator)
        super()._execute_parallel_group(steps, workflow_id, result, max_workers)
        report = coordinator.check_stability()

        elapsed_ms = int((time.monotonic() - start_time) * 1000)
        self._log_coordination_result(report, coordinator, elapsed_ms, result)
        coordinator.reset()

        return report

    async def _coordinated_execute_parallel_group_async(
        self,
        steps: list[StepConfig],
        workflow_id: str | None,
        result: Any,
        max_workers: int,
        coordinator: WorkflowCoordinator,
    ) -> StabilityReport:
        """Async version of coordinated parallel group execution.

        Same lifecycle as sync version but delegates to
        ``_execute_parallel_group_async``.

        Args:
            steps: Steps to execute in parallel.
            workflow_id: Current workflow ID.
            result: ExecutionResult to update.
            max_workers: Maximum concurrent workers.
            coordinator: Active WorkflowCoordinator.

        Returns:
            StabilityReport from the post-execution gate check.
        """
        start_time = time.monotonic()

        self._publish_intents(steps, coordinator)
        await super()._execute_parallel_group_async(
            steps, workflow_id, result, max_workers
        )
        report = coordinator.check_stability()

        elapsed_ms = int((time.monotonic() - start_time) * 1000)
        self._log_coordination_result(
            report, coordinator, elapsed_ms, result, label="async parallel group"
        )
        coordinator.reset()

        return report

    def _execute_with_coordination(
        self,
        workflow: Any,
        start_index: int,
        workflow_id: str | None,
        result: Any,
    ) -> None:
        """Execute workflow with auto-parallel and Convergent coordination.

        Drop-in replacement for ``_execute_with_auto_parallel`` that adds
        intent publishing and stability gating around each parallel group.

        Falls back to ``_execute_with_auto_parallel`` when coordination is
        not available.

        Args:
            workflow: WorkflowConfig to execute.
            start_index: Index to start from.
            workflow_id: Current workflow ID.
            result: ExecutionResult to update.
        """
        coordinator = self._get_coordinator(workflow.settings)
        if coordinator is None:
            # Fall back to standard auto-parallel
            super()._execute_with_auto_parallel(
                workflow, start_index, workflow_id, result
            )
            return

        from test_ai.workflow.auto_parallel import (
            build_dependency_graph,
            find_parallel_groups,
        )

        steps = workflow.steps[start_index:]
        if not steps:
            result.status = "success"
            return

        graph = build_dependency_graph(steps)
        groups = find_parallel_groups(graph)
        max_workers = workflow.settings.auto_parallel_max_workers
        step_map = {step.id: step for step in steps}

        logger.info(
            "Coordinated auto-parallel: %d steps in %d groups "
            "(max_workers=%d, coordination=enabled)",
            len(steps),
            len(groups),
            max_workers,
        )

        for group in groups:
            group_steps = [step_map[step_id] for step_id in group.step_ids]

            for step in group_steps:
                if self._check_budget_exceeded(step, result):
                    return

            if len(group_steps) == 1:
                # Single step — no coordination needed
                step = group_steps[0]
                step_result = self._execute_step(step, workflow_id)
                self._record_step_completion(step, step_result, result)

                if step_result.status == StepStatus.FAILED:
                    action = self._handle_step_failure(
                        step, step_result, result, workflow_id
                    )
                    if action == "abort":
                        return
                    if action != "skip":
                        self._store_step_outputs(step, step_result)
                else:
                    self._store_step_outputs(step, step_result)
            else:
                # Multi-step parallel group — coordinate
                self._coordinated_execute_parallel_group(
                    group_steps, workflow_id, result, max_workers, coordinator
                )

                if result.status == "failed":
                    return

        result.status = "success"

    async def _execute_with_coordination_async(
        self,
        workflow: Any,
        start_index: int,
        workflow_id: str | None,
        result: Any,
    ) -> None:
        """Async version of coordinated workflow execution.

        Args:
            workflow: WorkflowConfig to execute.
            start_index: Index to start from.
            workflow_id: Current workflow ID.
            result: ExecutionResult to update.
        """
        coordinator = self._get_coordinator(workflow.settings)
        if coordinator is None:
            await super()._execute_with_auto_parallel_async(
                workflow, start_index, workflow_id, result
            )
            return

        from test_ai.workflow.auto_parallel import (
            build_dependency_graph,
            find_parallel_groups,
        )

        steps = workflow.steps[start_index:]
        if not steps:
            result.status = "success"
            return

        graph = build_dependency_graph(steps)
        groups = find_parallel_groups(graph)
        max_workers = workflow.settings.auto_parallel_max_workers
        step_map = {step.id: step for step in steps}

        logger.info(
            "Coordinated auto-parallel async: %d steps in %d groups "
            "(max_workers=%d, coordination=enabled)",
            len(steps),
            len(groups),
            max_workers,
        )

        for group in groups:
            group_steps = [step_map[step_id] for step_id in group.step_ids]

            for step in group_steps:
                if self._check_budget_exceeded(step, result):
                    return

            if len(group_steps) == 1:
                step = group_steps[0]
                step_result = await self._execute_step_async(step, workflow_id)
                self._record_step_completion(step, step_result, result)

                if step_result.status == StepStatus.FAILED:
                    action = await self._handle_step_failure_async(
                        step, step_result, result, workflow_id
                    )
                    if action == "abort":
                        return
                    if action != "skip":
                        self._store_step_outputs(step, step_result)
                else:
                    self._store_step_outputs(step, step_result)
            else:
                await self._coordinated_execute_parallel_group_async(
                    group_steps, workflow_id, result, max_workers, coordinator
                )

                if result.status == "failed":
                    return

        result.status = "success"
