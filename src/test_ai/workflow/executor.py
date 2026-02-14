"""Workflow Executor with Contract Validation and State Persistence."""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime, timezone
from typing import Callable

from .loader import WorkflowConfig, StepConfig
from .parallel import ParallelExecutor, ParallelTask, ParallelStrategy
from .rate_limited_executor import RateLimitedParallelExecutor
from .auto_parallel import build_dependency_graph, find_parallel_groups
from .executor_results import (  # noqa: F401 — re-exported for backward compat
    ExecutionResult,
    StepHandler,
    StepResult,
    StepStatus,
)
from .executor_clients import (  # noqa: F401 — re-exported for backward compat
    _get_claude_client,
    _get_openai_client,
    configure_circuit_breaker,
    get_circuit_breaker,
    reset_circuit_breakers,
)
from .executor_integrations import IntegrationHandlersMixin  # noqa: F401
from .executor_ai import AIHandlersMixin  # noqa: F401
from .executor_patterns import DistributionPatternsMixin  # noqa: F401
from test_ai.monitoring.parallel_tracker import (
    ParallelPatternType,
    get_parallel_tracker,
)
from test_ai.utils.circuit_breaker import CircuitBreaker, CircuitBreakerError
from test_ai.state.agent_context import WorkflowMemoryManager, MemoryConfig

logger = logging.getLogger(__name__)


class WorkflowExecutor(
    IntegrationHandlersMixin,
    AIHandlersMixin,
    DistributionPatternsMixin,
):
    """Executes workflows with contract validation and state persistence.

    Integrates with:
    - ContractValidator for input/output validation
    - CheckpointManager for state persistence
    - BudgetManager for token tracking
    """

    def __init__(
        self,
        checkpoint_manager=None,
        contract_validator=None,
        budget_manager=None,
        dry_run: bool = False,
        error_callback: Callable[[str, str, Exception], None] | None = None,
        fallback_callbacks: dict[str, Callable[[StepConfig, dict, Exception], dict]]
        | None = None,
        memory_manager: WorkflowMemoryManager | None = None,
        memory_config: MemoryConfig | None = None,
        feedback_engine=None,
    ):
        """Initialize executor.

        Args:
            checkpoint_manager: Optional CheckpointManager for state persistence
            contract_validator: Optional ContractValidator for contract validation
            budget_manager: Optional BudgetManager for token tracking
            dry_run: If True, use mock responses instead of real API calls
            error_callback: Optional callback for error notifications (step_id, workflow_id, error)
            fallback_callbacks: Dict of named callbacks for fallback handling
            memory_manager: Optional WorkflowMemoryManager for agent memory
            memory_config: Optional MemoryConfig for memory behavior
            feedback_engine: Optional FeedbackEngine for outcome tracking and learning
        """
        self.checkpoint_manager = checkpoint_manager
        self.contract_validator = contract_validator
        self.budget_manager = budget_manager
        self.dry_run = dry_run
        self.error_callback = error_callback
        self.fallback_callbacks = fallback_callbacks or {}
        self.memory_manager = memory_manager
        self.memory_config = memory_config
        self.feedback_engine = feedback_engine
        self._handlers: dict[str, StepHandler] = {
            "shell": self._execute_shell,
            "checkpoint": self._execute_checkpoint,
            "parallel": self._execute_parallel,
            "claude_code": self._execute_claude_code,
            "openai": self._execute_openai,
            "fan_out": self._execute_fan_out,
            "fan_in": self._execute_fan_in,
            "map_reduce": self._execute_map_reduce,
            # Integration handlers
            "github": self._execute_github,
            "notion": self._execute_notion,
            "gmail": self._execute_gmail,
            "slack": self._execute_slack,
            "calendar": self._execute_calendar,
            "browser": self._execute_browser,
        }
        self._context: dict = {}
        self._current_workflow_id: str | None = None

    def register_handler(self, step_type: str, handler: StepHandler) -> None:
        """Register a custom step handler.

        Args:
            step_type: Step type name
            handler: Function that takes (StepConfig, context) and returns output dict
        """
        self._handlers[step_type] = handler

    def _validate_workflow_inputs(
        self, workflow: WorkflowConfig, result: ExecutionResult
    ) -> bool:
        """Validate required workflow inputs, applying defaults where available.

        Args:
            workflow: WorkflowConfig to validate
            result: ExecutionResult to update on failure

        Returns:
            True if valid, False if missing required input
        """
        for input_name, input_spec in workflow.inputs.items():
            if input_spec.get("required", False) and input_name not in self._context:
                if "default" in input_spec:
                    self._context[input_name] = input_spec["default"]
                else:
                    result.status = "failed"
                    result.error = f"Missing required input: {input_name}"
                    return False
        return True

    def _find_resume_index(self, workflow: WorkflowConfig, resume_from: str) -> int:
        """Find the step index to resume from.

        Args:
            workflow: WorkflowConfig containing steps
            resume_from: Step ID to resume from

        Returns:
            Index of the step to resume from, or 0 if not found
        """
        if not resume_from:
            return 0
        for i, step in enumerate(workflow.steps):
            if step.id == resume_from:
                return i
        return 0

    def _check_budget_exceeded(self, step: StepConfig, result: ExecutionResult) -> bool:
        """Check if token budget would be exceeded by step.

        Args:
            step: Step to check
            result: ExecutionResult to update if budget exceeded

        Returns:
            True if budget exceeded, False if OK to proceed
        """
        if not self.budget_manager:
            return False
        estimated_tokens = step.params.get("estimated_tokens", 1000)
        if not self.budget_manager.can_allocate(estimated_tokens):
            result.status = "failed"
            result.error = "Token budget exceeded"
            return True
        return False

    def _record_step_completion(
        self, step: StepConfig, step_result: StepResult, result: ExecutionResult
    ) -> None:
        """Record step completion in result, budget manager, and feedback engine.

        Args:
            step: Completed step
            step_result: Step result to record
            result: ExecutionResult to update
        """
        result.steps.append(step_result)
        result.total_tokens += step_result.tokens_used
        result.total_duration_ms += step_result.duration_ms

        if self.budget_manager and step_result.tokens_used > 0:
            self.budget_manager.record_usage(step.id, step_result.tokens_used)

        # Feed step outcome into the intelligence layer
        if self.feedback_engine:
            try:
                self.feedback_engine.process_step_result(
                    step_id=step.id,
                    workflow_id=self._current_workflow_id or "",
                    agent_role=step.params.get("role", step.type),
                    provider=step.type,
                    model=step.params.get("model", ""),
                    step_result=step_result,
                    cost_usd=0.0,  # Cost tracked separately via cost_tracker
                    tokens_used=step_result.tokens_used,
                )
            except Exception as fb_err:
                logger.debug(f"Feedback engine error (non-fatal): {fb_err}")

    def _store_step_outputs(self, step: StepConfig, step_result: StepResult) -> None:
        """Store step outputs in execution context.

        Args:
            step: Step with output keys
            step_result: Step result containing outputs

        For AI steps (claude_code, openai), the handler returns 'response' as the key.
        If the workflow defines custom output names, we map 'response' to the first
        output name, allowing intuitive workflow syntax like:
            outputs:
              - situation_analysis
        instead of forcing:
            outputs:
              - response
        """
        for i, output_key in enumerate(step.outputs):
            if output_key in step_result.output:
                # Direct match - use the value
                self._context[output_key] = step_result.output[output_key]
            elif i == 0 and "response" in step_result.output:
                # Map 'response' to the first custom output name for AI steps
                self._context[output_key] = step_result.output["response"]
            elif i == 0 and "stdout" in step_result.output:
                # Map 'stdout' to the first custom output name for shell steps
                self._context[output_key] = step_result.output["stdout"]

    def _handle_step_failure(
        self,
        step: StepConfig,
        step_result: StepResult,
        result: ExecutionResult,
        workflow_id: str | None,
    ) -> str:
        """Handle step failure based on on_failure strategy.

        Args:
            step: The failed step configuration
            step_result: The step result to potentially update
            result: The workflow result to update on abort
            workflow_id: Current workflow ID

        Returns:
            Action to take: "abort", "skip", "continue", or "recovered"
        """
        # Notify error callback
        if self.error_callback:
            try:
                self.error_callback(
                    step.id,
                    workflow_id or "",
                    Exception(step_result.error or "Unknown error"),
                )
            except Exception as cb_err:
                logger.warning(f"Error callback failed: {cb_err}")

        if step.on_failure == "abort":
            result.status = "failed"
            result.error = f"Step '{step.id}' failed: {step_result.error}"
            return "abort"

        if step.on_failure == "skip":
            return "skip"

        if step.on_failure == "continue_with_default":
            step_result.status = StepStatus.SUCCESS
            step_result.output = step.default_output.copy()
            logger.info(f"Step '{step.id}' failed, using default output")
            return "continue"

        if step.on_failure == "fallback" and step.fallback:
            fallback_output = self._execute_fallback(
                step, step_result.error, workflow_id
            )
            if fallback_output is not None:
                step_result.status = StepStatus.SUCCESS
                step_result.output = fallback_output
                logger.info(f"Step '{step.id}' recovered via fallback")
                return "recovered"
            result.status = "failed"
            result.error = f"Step '{step.id}' failed and fallback failed"
            return "abort"

        # Default: abort
        result.status = "failed"
        result.error = f"Step '{step.id}' failed: {step_result.error}"
        return "abort"

    async def _handle_step_failure_async(
        self,
        step: StepConfig,
        step_result: StepResult,
        result: ExecutionResult,
        workflow_id: str | None,
    ) -> str:
        """Async version of _handle_step_failure."""
        # Notify error callback
        if self.error_callback:
            try:
                self.error_callback(
                    step.id,
                    workflow_id or "",
                    Exception(step_result.error or "Unknown error"),
                )
            except Exception as cb_err:
                logger.warning(f"Error callback failed: {cb_err}")

        if step.on_failure == "abort":
            result.status = "failed"
            result.error = f"Step '{step.id}' failed: {step_result.error}"
            return "abort"

        if step.on_failure == "skip":
            return "skip"

        if step.on_failure == "continue_with_default":
            step_result.status = StepStatus.SUCCESS
            step_result.output = step.default_output.copy()
            logger.info(f"Step '{step.id}' failed, using default output")
            return "continue"

        if step.on_failure == "fallback" and step.fallback:
            fallback_output = await self._execute_fallback_async(
                step, step_result.error, workflow_id
            )
            if fallback_output is not None:
                step_result.status = StepStatus.SUCCESS
                step_result.output = fallback_output
                logger.info(f"Step '{step.id}' recovered via fallback")
                return "recovered"
            result.status = "failed"
            result.error = f"Step '{step.id}' failed and fallback failed"
            return "abort"

        # Default: abort
        result.status = "failed"
        result.error = f"Step '{step.id}' failed: {step_result.error}"
        return "abort"

    def _finalize_workflow(
        self,
        result: ExecutionResult,
        workflow: WorkflowConfig,
        workflow_id: str | None,
        error: Exception | None = None,
    ) -> None:
        """Finalize workflow execution - update checkpoints and collect outputs.

        Args:
            result: ExecutionResult to finalize
            workflow: WorkflowConfig with output definitions
            workflow_id: Current workflow ID
            error: Exception if workflow failed with error
        """
        if error:
            result.status = "failed"
            result.error = str(error)
            if self.checkpoint_manager and workflow_id:
                self.checkpoint_manager.fail_workflow(str(error), workflow_id)
        else:
            if self.checkpoint_manager and workflow_id:
                if result.status == "success":
                    self.checkpoint_manager.complete_workflow(workflow_id)
                else:
                    self.checkpoint_manager.fail_workflow(
                        result.error or "Unknown error", workflow_id
                    )

        # Collect workflow outputs
        for output_name in workflow.outputs:
            if output_name in self._context:
                result.outputs[output_name] = self._context[output_name]

        result.completed_at = datetime.now(timezone.utc)
        result.total_duration_ms = int(
            (result.completed_at - result.started_at).total_seconds() * 1000
        )

        # Save agent memories
        if self.memory_manager:
            try:
                self.memory_manager.save_all()
            except Exception as mem_err:
                logger.warning(f"Failed to save agent memories: {mem_err}")

        # Feed workflow outcome into the intelligence layer
        if self.feedback_engine:
            try:
                self.feedback_engine.process_workflow_result(
                    workflow_id=workflow_id or "",
                    workflow_name=workflow.name,
                    execution_result=result,
                )
            except Exception as fb_err:
                logger.debug(
                    f"Feedback engine workflow processing error (non-fatal): {fb_err}"
                )

        # Clear workflow ID
        self._current_workflow_id = None

    def execute(
        self,
        workflow: WorkflowConfig,
        inputs: dict = None,
        resume_from: str = None,
        enable_memory: bool = True,
    ) -> ExecutionResult:
        """Execute a workflow.

        Args:
            workflow: WorkflowConfig to execute
            inputs: Input values for the workflow
            resume_from: Optional step ID to resume from
            enable_memory: Enable agent memory (default True)

        Returns:
            ExecutionResult with status and outputs
        """
        result = ExecutionResult(workflow_name=workflow.name)
        self._context = inputs.copy() if inputs else {}

        if not self._validate_workflow_inputs(workflow, result):
            return result

        # Start workflow in checkpoint manager
        workflow_id = None
        if self.checkpoint_manager:
            workflow_id = self.checkpoint_manager.start_workflow(
                workflow.name,
                config={"inputs": self._context},
            )
        self._current_workflow_id = workflow_id

        # Initialize memory manager if enabled and not provided
        if enable_memory and not self.memory_manager:
            from test_ai.state import AgentMemory

            memory = AgentMemory()
            self.memory_manager = WorkflowMemoryManager(
                memory=memory,
                workflow_id=workflow_id,
                config=self.memory_config,
            )
        elif self.memory_manager and workflow_id:
            # Update workflow ID if manager exists
            self.memory_manager.workflow_id = workflow_id

        start_index = self._find_resume_index(workflow, resume_from)

        # Execute steps - use auto-parallel if enabled
        error = None
        try:
            if workflow.settings.auto_parallel:
                self._execute_with_auto_parallel(
                    workflow, start_index, workflow_id, result
                )
            else:
                self._execute_sequential(workflow, start_index, workflow_id, result)
        except Exception as e:
            error = e

        self._finalize_workflow(result, workflow, workflow_id, error)
        return result

    def _execute_sequential(
        self,
        workflow: WorkflowConfig,
        start_index: int,
        workflow_id: str | None,
        result: ExecutionResult,
    ) -> None:
        """Execute workflow steps sequentially.

        Args:
            workflow: WorkflowConfig to execute
            start_index: Index to start from
            workflow_id: Current workflow ID
            result: ExecutionResult to update
        """
        for step in workflow.steps[start_index:]:
            if self._check_budget_exceeded(step, result):
                break

            step_result = self._execute_step(step, workflow_id)
            self._record_step_completion(step, step_result, result)

            if step_result.status == StepStatus.FAILED:
                action = self._handle_step_failure(
                    step, step_result, result, workflow_id
                )
                if action == "abort":
                    break
                if action == "skip":
                    continue

            self._store_step_outputs(step, step_result)
        else:
            result.status = "success"

    def _execute_with_auto_parallel(
        self,
        workflow: WorkflowConfig,
        start_index: int,
        workflow_id: str | None,
        result: ExecutionResult,
    ) -> None:
        """Execute workflow with auto-parallel optimization.

        Analyzes step dependencies and executes independent steps
        concurrently for improved performance.

        Args:
            workflow: WorkflowConfig to execute
            start_index: Index to start from
            workflow_id: Current workflow ID
            result: ExecutionResult to update
        """
        steps = workflow.steps[start_index:]
        if not steps:
            result.status = "success"
            return

        # Build dependency graph and find parallel groups
        graph = build_dependency_graph(steps)
        groups = find_parallel_groups(graph)

        max_workers = workflow.settings.auto_parallel_max_workers
        step_map = {step.id: step for step in steps}
        completed: set[str] = set()

        logger.info(
            f"Auto-parallel: {len(steps)} steps in {len(groups)} groups "
            f"(max_workers={max_workers})"
        )

        for group in groups:
            group_steps = [step_map[step_id] for step_id in group.step_ids]

            # Check budget for all steps in group
            for step in group_steps:
                if self._check_budget_exceeded(step, result):
                    return

            if len(group_steps) == 1:
                # Single step - execute directly
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

                completed.add(step.id)
            else:
                # Multiple steps - execute in parallel
                self._execute_parallel_group(
                    group_steps, workflow_id, result, max_workers
                )
                completed.update(step.id for step in group_steps)

                # Check if any step in the group failed fatally
                if result.status == "failed":
                    return

        result.status = "success"

    def _execute_parallel_group(
        self,
        steps: list[StepConfig],
        workflow_id: str | None,
        result: ExecutionResult,
        max_workers: int,
    ) -> None:
        """Execute a group of steps in parallel.

        Args:
            steps: Steps to execute concurrently
            workflow_id: Current workflow ID
            result: ExecutionResult to update
            max_workers: Maximum concurrent workers
        """
        logger.debug(
            f"Executing parallel group: {[s.id for s in steps]} "
            f"(max_workers={max_workers})"
        )

        # Start parallel execution tracking
        tracker = get_parallel_tracker()
        group_id = "_".join(s.id for s in steps[:3])  # First 3 step IDs
        execution_id = f"parallel_group_{group_id}_{int(time.time() * 1000)}"
        tracker.start_execution(
            execution_id=execution_id,
            pattern_type=ParallelPatternType.PARALLEL_GROUP,
            step_id=group_id,
            total_items=len(steps),
            max_concurrent=max_workers,
            workflow_id=workflow_id,
        )

        # Detect AI step types for rate limiting
        ai_step_types = {"claude_code", "openai"}
        has_ai_steps = any(step.type in ai_step_types for step in steps)
        max_timeout = max(step.timeout_seconds for step in steps)

        if has_ai_steps:
            # Use rate-limited executor with adaptive configuration
            executor = RateLimitedParallelExecutor(
                strategy=ParallelStrategy.ASYNCIO,
                max_workers=max_workers,
                timeout=max_timeout,
                adaptive=True,  # Enable adaptive rate limiting
            )
        else:
            executor = ParallelExecutor(
                strategy=ParallelStrategy.THREADING,
                max_workers=max_workers,
                timeout=max_timeout,
            )

        step_results: dict[str, StepResult] = {}

        def make_handler(step: StepConfig, idx: int):
            def handler(**kwargs):
                # Track branch start
                tracker.start_branch(execution_id, step.id, idx, step.id)
                try:
                    step_result = self._execute_step(step, workflow_id)
                    tokens = step_result.tokens_used if step_result else 0
                    if step_result and step_result.status == StepStatus.FAILED:
                        tracker.fail_branch(
                            execution_id, step.id, step_result.error or "Unknown error"
                        )
                    else:
                        tracker.complete_branch(execution_id, step.id, tokens)
                    return step_result
                except Exception as e:
                    tracker.fail_branch(execution_id, step.id, str(e))
                    raise

            return handler

        tasks = [
            ParallelTask(
                id=step.id,
                step_id=step.id,
                handler=make_handler(step, idx),
                kwargs={"step_type": step.type},
            )
            for idx, step in enumerate(steps)
        ]

        def on_complete(task_id: str, step_result: StepResult):
            step_results[task_id] = step_result

        def on_error(task_id: str, error: Exception):
            step_results[task_id] = StepResult(
                step_id=task_id,
                status=StepStatus.FAILED,
                error=str(error),
            )

        executor.execute_parallel(
            tasks=tasks,
            on_complete=on_complete,
            on_error=on_error,
            fail_fast=False,
        )

        # Capture and track rate limit stats for AI executors
        if has_ai_steps and hasattr(executor, "get_provider_stats"):
            provider_stats = executor.get_provider_stats()
            for provider, stats in provider_stats.items():
                if stats.get("total_429s", 0) > 0 or stats.get("is_throttled", False):
                    tracker.update_rate_limit_state(
                        provider=provider,
                        current_limit=stats.get("current_limit", 0),
                        base_limit=stats.get("base_limit", 0),
                        total_429s=stats.get("total_429s", 0),
                        is_throttled=stats.get("is_throttled", False),
                    )

        # Process results
        step_map = {step.id: step for step in steps}
        abort = False
        has_failures = False

        for step_id, step_result in step_results.items():
            step = step_map[step_id]
            self._record_step_completion(step, step_result, result)

            if step_result.status == StepStatus.FAILED:
                has_failures = True
                action = self._handle_step_failure(
                    step, step_result, result, workflow_id
                )
                if action == "abort":
                    abort = True
                elif action != "skip":
                    self._store_step_outputs(step, step_result)
            else:
                self._store_step_outputs(step, step_result)

        # Complete execution tracking
        if has_failures:
            tracker.fail_execution(execution_id)
        else:
            tracker.complete_execution(execution_id)

        if abort:
            result.status = "failed"

    async def execute_async(
        self,
        workflow: WorkflowConfig,
        inputs: dict = None,
        resume_from: str = None,
    ) -> ExecutionResult:
        """Execute a workflow asynchronously.

        This is the async version of execute() for non-blocking execution.

        Args:
            workflow: WorkflowConfig to execute
            inputs: Input values for the workflow
            resume_from: Optional step ID to resume from

        Returns:
            ExecutionResult with status and outputs
        """
        result = ExecutionResult(workflow_name=workflow.name)
        self._context = inputs.copy() if inputs else {}

        if not self._validate_workflow_inputs(workflow, result):
            return result

        # Start workflow in checkpoint manager
        workflow_id = None
        if self.checkpoint_manager:
            workflow_id = self.checkpoint_manager.start_workflow(
                workflow.name,
                config={"inputs": self._context},
            )
        self._current_workflow_id = workflow_id

        start_index = self._find_resume_index(workflow, resume_from)

        # Execute steps - use auto-parallel if enabled
        error = None
        try:
            if workflow.settings.auto_parallel:
                await self._execute_with_auto_parallel_async(
                    workflow, start_index, workflow_id, result
                )
            else:
                await self._execute_sequential_async(
                    workflow, start_index, workflow_id, result
                )
        except Exception as e:
            error = e

        self._finalize_workflow(result, workflow, workflow_id, error)
        return result

    async def _execute_sequential_async(
        self,
        workflow: WorkflowConfig,
        start_index: int,
        workflow_id: str | None,
        result: ExecutionResult,
    ) -> None:
        """Execute workflow steps sequentially (async version)."""
        for step in workflow.steps[start_index:]:
            if self._check_budget_exceeded(step, result):
                break

            step_result = await self._execute_step_async(step, workflow_id)
            self._record_step_completion(step, step_result, result)

            if step_result.status == StepStatus.FAILED:
                action = await self._handle_step_failure_async(
                    step, step_result, result, workflow_id
                )
                if action == "abort":
                    break
                if action == "skip":
                    continue

            self._store_step_outputs(step, step_result)
        else:
            result.status = "success"

    async def _execute_with_auto_parallel_async(
        self,
        workflow: WorkflowConfig,
        start_index: int,
        workflow_id: str | None,
        result: ExecutionResult,
    ) -> None:
        """Execute workflow with auto-parallel optimization (async version)."""
        steps = workflow.steps[start_index:]
        if not steps:
            result.status = "success"
            return

        graph = build_dependency_graph(steps)
        groups = find_parallel_groups(graph)

        max_workers = workflow.settings.auto_parallel_max_workers
        step_map = {step.id: step for step in steps}

        logger.info(
            f"Auto-parallel async: {len(steps)} steps in {len(groups)} groups "
            f"(max_workers={max_workers})"
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
                await self._execute_parallel_group_async(
                    group_steps, workflow_id, result, max_workers
                )
                if result.status == "failed":
                    return

        result.status = "success"

    async def _execute_parallel_group_async(
        self,
        steps: list[StepConfig],
        workflow_id: str | None,
        result: ExecutionResult,
        max_workers: int,
    ) -> None:
        """Execute a group of steps in parallel (async version)."""
        logger.debug(
            f"Executing parallel group async: {[s.id for s in steps]} "
            f"(max_workers={max_workers})"
        )

        semaphore = asyncio.Semaphore(max_workers)
        step_results: dict[str, StepResult] = {}

        async def execute_step(step: StepConfig):
            async with semaphore:
                return step.id, await self._execute_step_async(step, workflow_id)

        tasks = [execute_step(step) for step in steps]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for item in results:
            if isinstance(item, Exception):
                continue
            step_id, step_result = item
            step_results[step_id] = step_result

        step_map = {step.id: step for step in steps}
        abort = False

        for step_id, step_result in step_results.items():
            step = step_map[step_id]
            self._record_step_completion(step, step_result, result)

            if step_result.status == StepStatus.FAILED:
                action = await self._handle_step_failure_async(
                    step, step_result, result, workflow_id
                )
                if action == "abort":
                    abort = True
                elif action != "skip":
                    self._store_step_outputs(step, step_result)
            else:
                self._store_step_outputs(step, step_result)

        if abort:
            result.status = "failed"

    def _check_step_preconditions(
        self, step: StepConfig, result: StepResult
    ) -> tuple[StepHandler | None, CircuitBreaker | None, str | None]:
        """Check step preconditions and return handler/circuit breaker.

        Returns:
            Tuple of (handler, circuit_breaker, error_message)
            If error_message is set, the step should fail with that message.
        """
        # Check condition
        if step.condition and not step.condition.evaluate(self._context):
            result.status = StepStatus.SKIPPED
            return None, None, None

        # Validate input contract if applicable
        role = step.params.get("role")
        if self.contract_validator and role:
            try:
                input_data = step.params.get("input", {})
                self.contract_validator.validate_input(role, input_data, self._context)
            except Exception as e:
                return None, None, f"Input validation failed: {e}"

        handler = self._handlers.get(step.type)
        if not handler:
            return None, None, f"Unknown step type: {step.type}"

        cb_key = step.circuit_breaker_key or step.type
        cb = get_circuit_breaker(cb_key)
        if cb and cb.is_open:
            logger.warning(f"Step '{step.id}' skipped: circuit breaker open")
            return None, None, f"Circuit breaker open for {cb_key}"

        return handler, cb, None

    def _invoke_handler(
        self, handler: StepHandler, step: StepConfig, cb: CircuitBreaker | None
    ) -> dict:
        """Invoke step handler with optional circuit breaker."""
        if cb:
            return cb.call(handler, step, self._context)
        return handler(step, self._context)

    async def _invoke_handler_async(
        self, handler: StepHandler, step: StepConfig, cb: CircuitBreaker | None
    ) -> dict:
        """Invoke step handler asynchronously with optional circuit breaker."""
        loop = asyncio.get_event_loop()
        if cb:
            return await loop.run_in_executor(
                None, cb.call, handler, step, self._context
            )
        return await loop.run_in_executor(None, handler, step, self._context)

    async def _execute_step_async(
        self, step: StepConfig, workflow_id: str = None
    ) -> StepResult:
        """Execute a single workflow step asynchronously."""
        start_time = time.time()
        result = StepResult(step_id=step.id, status=StepStatus.PENDING)

        handler, cb, error = self._check_step_preconditions(step, result)
        if result.status == StepStatus.SKIPPED:
            return result
        if error:
            result.status = StepStatus.FAILED
            result.error = error
            return result

        role = step.params.get("role")
        last_error = None

        for attempt in range(step.max_retries + 1):
            result.retries = attempt
            result.status = StepStatus.RUNNING

            try:
                if self.checkpoint_manager and workflow_id:
                    with self.checkpoint_manager.stage(
                        step.id, input_data=step.params, workflow_id=workflow_id
                    ) as ctx:
                        output = await self._invoke_handler_async(handler, step, cb)
                        ctx.output_data = output
                        ctx.tokens_used = output.get("tokens_used", 0)
                else:
                    output = await self._invoke_handler_async(handler, step, cb)

                if self.contract_validator and role:
                    self.contract_validator.validate_output(role, output)

                result.status = StepStatus.SUCCESS
                result.output = output
                result.tokens_used = output.get("tokens_used", 0)
                break

            except CircuitBreakerError as e:
                result.status = StepStatus.FAILED
                result.error = str(e)
                break

            except Exception as e:
                last_error = str(e)
                if attempt < step.max_retries:
                    await asyncio.sleep(min(2**attempt, 30))
                else:
                    result.status = StepStatus.FAILED
                    result.error = last_error

        result.duration_ms = int((time.time() - start_time) * 1000)
        return result

    async def _execute_fallback_async(
        self, step: StepConfig, error: str | None, workflow_id: str | None
    ) -> dict | None:
        """Execute fallback strategy for a failed step asynchronously.

        Args:
            step: The failed step configuration
            error: The error message from the failed step
            workflow_id: Current workflow ID

        Returns:
            Fallback output dict, or None if fallback failed
        """
        if not step.fallback:
            return None

        fallback = step.fallback
        logger.info(f"Executing fallback ({fallback.type}) for step '{step.id}'")

        try:
            if fallback.type == "default_value":
                # Return the configured default value
                return {"fallback_value": fallback.value, "fallback_used": True}

            elif fallback.type == "alternate_step" and fallback.step:
                # Execute an alternate step
                alt_step = StepConfig.from_dict(fallback.step)
                alt_result = await self._execute_step_async(alt_step, workflow_id)
                if alt_result.status == StepStatus.SUCCESS:
                    return alt_result.output
                return None

            elif fallback.type == "callback" and fallback.callback:
                # Invoke a registered callback
                if fallback.callback in self.fallback_callbacks:
                    callback = self.fallback_callbacks[fallback.callback]
                    # Run callback in executor if not async
                    loop = asyncio.get_event_loop()
                    return await loop.run_in_executor(
                        None,
                        callback,
                        step,
                        self._context,
                        Exception(error or "Unknown"),
                    )
                else:
                    logger.warning(
                        f"Fallback callback '{fallback.callback}' not registered"
                    )
                    return None

        except Exception as e:
            logger.error(f"Fallback execution failed: {e}")
            return None

        return None

    def _execute_step(self, step: StepConfig, workflow_id: str = None) -> StepResult:
        """Execute a single workflow step."""
        start_time = time.time()
        result = StepResult(step_id=step.id, status=StepStatus.PENDING)

        handler, cb, error = self._check_step_preconditions(step, result)
        if result.status == StepStatus.SKIPPED:
            return result
        if error:
            result.status = StepStatus.FAILED
            result.error = error
            return result

        role = step.params.get("role")
        last_error = None

        for attempt in range(step.max_retries + 1):
            result.retries = attempt
            result.status = StepStatus.RUNNING

            try:
                if self.checkpoint_manager and workflow_id:
                    with self.checkpoint_manager.stage(
                        step.id, input_data=step.params, workflow_id=workflow_id
                    ) as ctx:
                        output = self._invoke_handler(handler, step, cb)
                        ctx.output_data = output
                        ctx.tokens_used = output.get("tokens_used", 0)
                else:
                    output = self._invoke_handler(handler, step, cb)

                if self.contract_validator and role:
                    self.contract_validator.validate_output(role, output)

                result.status = StepStatus.SUCCESS
                result.output = output
                result.tokens_used = output.get("tokens_used", 0)
                break

            except CircuitBreakerError as e:
                result.status = StepStatus.FAILED
                result.error = str(e)
                break

            except Exception as e:
                last_error = str(e)
                if attempt < step.max_retries:
                    time.sleep(min(2**attempt, 30))
                else:
                    result.status = StepStatus.FAILED
                    result.error = last_error

        result.duration_ms = int((time.time() - start_time) * 1000)
        return result

    def _execute_fallback(
        self, step: StepConfig, error: str | None, workflow_id: str | None
    ) -> dict | None:
        """Execute fallback strategy for a failed step.

        Args:
            step: The failed step configuration
            error: The error message from the failed step
            workflow_id: Current workflow ID

        Returns:
            Fallback output dict, or None if fallback failed
        """
        if not step.fallback:
            return None

        fallback = step.fallback
        logger.info(f"Executing fallback ({fallback.type}) for step '{step.id}'")

        try:
            if fallback.type == "default_value":
                # Return the configured default value
                return {"fallback_value": fallback.value, "fallback_used": True}

            elif fallback.type == "alternate_step" and fallback.step:
                # Execute an alternate step
                alt_step = StepConfig.from_dict(fallback.step)
                alt_result = self._execute_step(alt_step, workflow_id)
                if alt_result.status == StepStatus.SUCCESS:
                    return alt_result.output
                return None

            elif fallback.type == "callback" and fallback.callback:
                # Invoke a registered callback
                if fallback.callback in self.fallback_callbacks:
                    callback = self.fallback_callbacks[fallback.callback]
                    return callback(step, self._context, Exception(error or "Unknown"))
                else:
                    logger.warning(
                        f"Fallback callback '{fallback.callback}' not registered"
                    )
                    return None

        except Exception as e:
            logger.error(f"Fallback execution failed: {e}")
            return None

        return None

    def get_context(self) -> dict:
        """Get current execution context."""
        return self._context.copy()

    def set_context(self, context: dict) -> None:
        """Set execution context."""
        self._context = context.copy()
