"""Workflow Executor with Contract Validation and State Persistence."""

from __future__ import annotations

import asyncio
import logging
import subprocess
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Callable

from .loader import WorkflowConfig, StepConfig
from .parallel import ParallelExecutor, ParallelTask, ParallelStrategy
from .rate_limited_executor import RateLimitedParallelExecutor
from .auto_parallel import build_dependency_graph, find_parallel_groups
from test_ai.monitoring.parallel_tracker import (
    ParallelPatternType,
    get_parallel_tracker,
)
from test_ai.utils.validation import substitute_shell_variables, validate_shell_command
from test_ai.utils.circuit_breaker import CircuitBreaker, CircuitBreakerError
from test_ai.state.agent_context import WorkflowMemoryManager, MemoryConfig

logger = logging.getLogger(__name__)

# Global circuit breakers for step types
_circuit_breakers: dict[str, CircuitBreaker] = {}


def configure_circuit_breaker(
    key: str,
    failure_threshold: int = 5,
    recovery_timeout: float = 60.0,
    success_threshold: int = 2,
) -> CircuitBreaker:
    """Configure a circuit breaker for a step type or custom key.

    Args:
        key: Identifier for the circuit breaker (e.g., step type or custom key)
        failure_threshold: Number of failures before opening circuit
        recovery_timeout: Seconds to wait before trying again
        success_threshold: Successes needed in half-open to close circuit

    Returns:
        The configured CircuitBreaker instance
    """
    cb = CircuitBreaker(
        name=key,
        failure_threshold=failure_threshold,
        recovery_timeout=recovery_timeout,
        success_threshold=success_threshold,
    )
    _circuit_breakers[key] = cb
    return cb


def get_circuit_breaker(key: str) -> CircuitBreaker | None:
    """Get circuit breaker by key."""
    return _circuit_breakers.get(key)


def reset_circuit_breakers() -> None:
    """Reset all circuit breakers (for testing)."""
    global _circuit_breakers
    for cb in _circuit_breakers.values():
        cb.reset()
    _circuit_breakers = {}


# Lazy-loaded API clients to avoid circular imports
_claude_client = None
_openai_client = None


def _get_claude_client():
    """Get or create ClaudeCodeClient instance."""
    global _claude_client
    if _claude_client is None:
        try:
            from test_ai.api_clients.claude_code_client import ClaudeCodeClient

            _claude_client = ClaudeCodeClient()
        except Exception:
            _claude_client = False  # Mark as unavailable
    return _claude_client if _claude_client else None


def _get_openai_client():
    """Get or create OpenAIClient instance."""
    global _openai_client
    if _openai_client is None:
        try:
            from test_ai.api_clients.openai_client import OpenAIClient

            _openai_client = OpenAIClient()
        except Exception:
            _openai_client = False  # Mark as unavailable
    return _openai_client if _openai_client else None


class StepStatus(Enum):
    """Status of a workflow step."""

    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class StepResult:
    """Result of executing a single step."""

    step_id: str
    status: StepStatus
    output: dict = field(default_factory=dict)
    error: str | None = None
    duration_ms: int = 0
    tokens_used: int = 0
    retries: int = 0


@dataclass
class ExecutionResult:
    """Result of executing a complete workflow."""

    workflow_name: str
    status: str = "pending"  # "success", "failed", "partial", "pending"
    steps: list[StepResult] = field(default_factory=list)
    outputs: dict = field(default_factory=dict)
    total_tokens: int = 0
    total_duration_ms: int = 0
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: datetime | None = None
    error: str | None = None

    def to_dict(self) -> dict:
        return {
            "workflow_name": self.workflow_name,
            "status": self.status,
            "steps": [
                {
                    "step_id": s.step_id,
                    "status": s.status.value,
                    "output": s.output,
                    "error": s.error,
                    "duration_ms": s.duration_ms,
                    "tokens_used": s.tokens_used,
                    "retries": s.retries,
                }
                for s in self.steps
            ],
            "outputs": self.outputs,
            "total_tokens": self.total_tokens,
            "total_duration_ms": self.total_duration_ms,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat()
            if self.completed_at
            else None,
            "error": self.error,
        }


# Type alias for step handlers
StepHandler = Callable[[StepConfig, dict], dict]


class WorkflowExecutor:
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
        """
        self.checkpoint_manager = checkpoint_manager
        self.contract_validator = contract_validator
        self.budget_manager = budget_manager
        self.dry_run = dry_run
        self.error_callback = error_callback
        self.fallback_callbacks = fallback_callbacks or {}
        self.memory_manager = memory_manager
        self.memory_config = memory_config
        self._handlers: dict[str, StepHandler] = {
            "shell": self._execute_shell,
            "checkpoint": self._execute_checkpoint,
            "parallel": self._execute_parallel,
            "claude_code": self._execute_claude_code,
            "openai": self._execute_openai,
            "fan_out": self._execute_fan_out,
            "fan_in": self._execute_fan_in,
            "map_reduce": self._execute_map_reduce,
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
        """Record step completion in result and budget manager.

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
        cb = _circuit_breakers.get(cb_key)
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

    def _execute_shell(self, step: StepConfig, context: dict) -> dict:
        """Execute a shell command step with resource limits.

        Security: Variables are escaped using shlex.quote to prevent injection.
        Set allow_dangerous=True in params to skip dangerous pattern checks.
        Set escape_variables=False to disable escaping (use with extreme caution).

        Resource limits (configurable via settings):
        - Timeout: SHELL_TIMEOUT_SECONDS (default: 300s / 5 minutes)
        - Output size: SHELL_MAX_OUTPUT_BYTES (default: 10MB)
        - Command whitelist: SHELL_ALLOWED_COMMANDS (optional)
        """
        from test_ai.config import get_settings

        settings = get_settings()
        command = step.params.get("command", "")
        if not command:
            raise ValueError("Shell step requires 'command' parameter")

        # Check command whitelist if configured
        if settings.shell_allowed_commands:
            allowed = [c.strip() for c in settings.shell_allowed_commands.split(",")]
            # Extract the base command (first word before space or pipe)
            base_cmd = command.split()[0].split("/")[-1] if command.split() else ""
            if base_cmd not in allowed:
                raise ValueError(
                    f"Command '{base_cmd}' not in allowed list. "
                    f"Allowed commands: {', '.join(allowed)}"
                )

        # Validate command template (before substitution)
        allow_dangerous = step.params.get("allow_dangerous", False)
        validate_shell_command(command, allow_dangerous=allow_dangerous)

        # Safely substitute context variables with shell escaping
        escape_variables = step.params.get("escape_variables", True)
        command = substitute_shell_variables(command, context, escape=escape_variables)

        # Determine timeout: use step timeout if set, otherwise use global setting
        timeout = step.timeout_seconds or settings.shell_timeout_seconds

        logger.debug(
            "Executing shell command (timeout=%ds): %s",
            timeout,
            command[:200],
        )

        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired as e:
            raise RuntimeError(
                f"Command timed out after {timeout} seconds. "
                f"Partial stdout: {e.stdout[:500] if e.stdout else 'None'}... "
                f"Partial stderr: {e.stderr[:500] if e.stderr else 'None'}..."
            )

        # Check output size limits
        max_output = settings.shell_max_output_bytes
        stdout = result.stdout or ""
        stderr = result.stderr or ""

        if len(stdout.encode()) > max_output:
            logger.warning(
                "Shell stdout truncated from %d to %d bytes",
                len(stdout.encode()),
                max_output,
            )
            stdout = stdout[:max_output] + "\n... [OUTPUT TRUNCATED]"

        if len(stderr.encode()) > max_output:
            logger.warning(
                "Shell stderr truncated from %d to %d bytes",
                len(stderr.encode()),
                max_output,
            )
            stderr = stderr[:max_output] + "\n... [OUTPUT TRUNCATED]"

        if result.returncode != 0 and not step.params.get("allow_failure", False):
            raise RuntimeError(
                f"Command failed with code {result.returncode}: {stderr[:1000]}"
            )

        return {
            "stdout": stdout,
            "stderr": stderr,
            "returncode": result.returncode,
        }

    def _execute_checkpoint(self, step: StepConfig, context: dict) -> dict:
        """Create a checkpoint (no-op if no checkpoint manager)."""
        return {"checkpoint": step.id}

    def _check_sub_step_budget(self, sub_step: StepConfig, stage_name: str) -> None:
        """Check budget allocation for a sub-step.

        Raises:
            RuntimeError: If budget is exceeded
        """
        if not self.budget_manager:
            return
        estimated_tokens = sub_step.params.get("estimated_tokens", 1000)
        if not self.budget_manager.can_allocate(estimated_tokens, agent_id=stage_name):
            raise RuntimeError(f"Budget exceeded for sub-step '{sub_step.id}'")

    def _record_sub_step_metrics(
        self,
        stage_name: str,
        sub_step: StepConfig,
        parent_step_id: str,
        tokens_used: int,
        duration_ms: int,
        retries_used: int,
        output: dict | None,
        error_msg: str | None,
    ) -> None:
        """Record budget and checkpoint metrics for a sub-step."""
        if self.budget_manager and tokens_used > 0:
            self.budget_manager.record_usage(
                agent_id=stage_name,
                tokens=tokens_used,
                operation=f"parallel:{sub_step.type}",
                metadata={
                    "parent_step": parent_step_id,
                    "sub_step": sub_step.id,
                    "step_type": sub_step.type,
                    "duration_ms": duration_ms,
                    "retries": retries_used,
                },
            )

        if self.checkpoint_manager and self._current_workflow_id:
            self.checkpoint_manager.checkpoint_now(
                stage=stage_name,
                status="success" if error_msg is None else "failed",
                input_data=sub_step.params,
                output_data=output if output else {"error": error_msg},
                tokens_used=tokens_used,
                duration_ms=duration_ms,
                workflow_id=self._current_workflow_id,
            )

    def _execute_sub_step_attempt(
        self,
        sub_step: StepConfig,
        stage_name: str,
        context: dict,
        context_updates: dict,
    ) -> tuple[dict, int]:
        """Execute a single sub-step attempt.

        Returns:
            Tuple of (output dict, tokens_used)
        """
        self._check_sub_step_budget(sub_step, stage_name)

        step_context = context.copy()
        step_context.update(context_updates)

        step_handler = self._handlers.get(sub_step.type)
        if not step_handler:
            raise ValueError(f"Unknown step type: {sub_step.type}")

        output = step_handler(sub_step, step_context)
        tokens_used = output.get("tokens_used", 0)

        for output_key in sub_step.outputs:
            if output_key in output:
                context_updates[output_key] = output[output_key]

        return output, tokens_used

    def _execute_with_retries(
        self,
        sub_step: StepConfig,
        stage_name: str,
        context: dict,
        context_updates: dict,
    ) -> tuple[dict | None, int, str | None, int]:
        """Execute a sub-step with retry logic.

        Args:
            sub_step: Step configuration
            stage_name: Stage name for metrics
            context: Execution context
            context_updates: Dictionary to collect output updates

        Returns:
            Tuple of (output, tokens_used, error_msg, retries_used)
        """
        output, error_msg, tokens_used, retries_used = None, None, 0, 0

        for attempt in range(sub_step.max_retries + 1):
            try:
                output, tokens_used = self._execute_sub_step_attempt(
                    sub_step, stage_name, context, context_updates
                )
                output["retries"] = retries_used
                return output, tokens_used, None, retries_used
            except Exception as e:
                error_msg = str(e)
                retries_used = attempt + 1
                if attempt < sub_step.max_retries:
                    time.sleep(min(2**attempt, 30))
                elif attempt == sub_step.max_retries:
                    raise

        return output, tokens_used, error_msg, retries_used

    def _execute_parallel(self, step: StepConfig, context: dict) -> dict:
        """Execute parallel sub-steps using ParallelExecutor.

        Params:
            steps: List of sub-step configurations
            strategy: "threading" | "asyncio" (default: "threading")
            max_workers: int (default: 4)
            fail_fast: bool - if True, abort on first failure (default: False)
            rate_limit: bool - if True, use rate-limited executor for AI steps (default: True)
            anthropic_concurrent: int - max concurrent Anthropic calls (default: 5)
            openai_concurrent: int - max concurrent OpenAI calls (default: 8)
        """
        sub_steps = step.params.get("steps", [])
        if not sub_steps:
            return {"parallel_results": {}, "tokens_used": 0}

        # Check if any sub-steps are AI steps
        ai_step_types = {"claude_code", "openai"}
        parsed_step_types = {s.get("type") for s in sub_steps}
        has_ai_steps = bool(parsed_step_types & ai_step_types)

        # Use rate-limited executor for AI steps (unless explicitly disabled)
        use_rate_limiting = step.params.get("rate_limit", True) and has_ai_steps

        strategy_map = {
            "threading": ParallelStrategy.THREADING,
            "asyncio": ParallelStrategy.ASYNCIO,
            "process": ParallelStrategy.PROCESS,
        }

        if use_rate_limiting:
            # Force asyncio strategy for rate limiting
            executor = RateLimitedParallelExecutor(
                strategy=ParallelStrategy.ASYNCIO,
                max_workers=step.params.get("max_workers", 4),
                timeout=step.timeout_seconds or 300.0,
                provider_limits={
                    "anthropic": step.params.get("anthropic_concurrent", 5),
                    "openai": step.params.get("openai_concurrent", 8),
                },
            )
            logger.debug(
                f"Using rate-limited executor for parallel step '{step.id}' "
                f"(AI steps detected: {parsed_step_types & ai_step_types})"
            )
        else:
            strategy = strategy_map.get(
                step.params.get("strategy", "threading"), ParallelStrategy.THREADING
            )
            executor = ParallelExecutor(
                strategy=strategy,
                max_workers=step.params.get("max_workers", 4),
                timeout=step.timeout_seconds,
            )

        parsed_steps = {
            StepConfig.from_dict(s).id: StepConfig.from_dict(s) for s in sub_steps
        }

        results: dict[str, dict] = {}
        total_tokens = 0
        first_error: Exception | None = None
        context_updates: dict[str, any] = {}
        parent_step_id = step.id
        fail_fast = step.params.get("fail_fast", False)

        def make_handler(sub_step: StepConfig):
            def handler(**kwargs):
                # kwargs may contain step_type from rate-limited executor
                nonlocal total_tokens
                start_time = time.time()
                stage_name = f"{parent_step_id}.{sub_step.id}"
                output, tokens_used, error_msg, retries_used = None, 0, None, 0

                try:
                    output, tokens_used, error_msg, retries_used = (
                        self._execute_with_retries(
                            sub_step, stage_name, context, context_updates
                        )
                    )
                    total_tokens += tokens_used
                    return output
                except Exception as e:
                    # Capture error message for checkpoint recording
                    error_msg = str(e)
                    raise
                finally:
                    duration_ms = int((time.time() - start_time) * 1000)
                    self._record_sub_step_metrics(
                        stage_name,
                        sub_step,
                        parent_step_id,
                        tokens_used,
                        duration_ms,
                        retries_used,
                        output,
                        error_msg,
                    )

            return handler

        tasks = [
            ParallelTask(
                id=sub_step.id,
                step_id=sub_step.id,
                handler=make_handler(sub_step),
                dependencies=sub_step.depends_on,
                kwargs={
                    "step_type": sub_step.type
                },  # For rate limiter provider detection
            )
            for sub_step in parsed_steps.values()
        ]

        def on_complete(task_id: str, result: any):
            results[task_id] = result

        def on_error(task_id: str, error: Exception):
            nonlocal first_error
            results[task_id] = {"error": str(error)}
            if first_error is None:
                first_error = error

        try:
            parallel_result = executor.execute_parallel(
                tasks=tasks,
                on_complete=on_complete,
                on_error=on_error,
                fail_fast=fail_fast,
            )
        except ValueError as e:
            raise RuntimeError(f"Parallel execution failed: {e}")

        if fail_fast and first_error is not None:
            raise RuntimeError(f"Parallel step failed: {first_error}")

        self._context.update(context_updates)

        total_retries = sum(
            r.get("retries", 0) for r in results.values() if isinstance(r, dict)
        )

        return {
            "parallel_results": results,
            "tokens_used": total_tokens,
            "successful": parallel_result.successful,
            "failed": parallel_result.failed,
            "cancelled": parallel_result.cancelled,
            "duration_ms": parallel_result.total_duration_ms,
            "total_retries": total_retries,
        }

    def _execute_claude_code(self, step: StepConfig, context: dict) -> dict:
        """Execute a Claude Code step using the Anthropic API.

        Params:
            prompt: The task/prompt to send
            role: Agent role (planner, builder, tester, reviewer)
            model: Claude model to use (default: claude-sonnet-4-20250514)
            max_tokens: Maximum tokens in response (default: 4096)
            system_prompt: Optional custom system prompt (overrides role)
            use_memory: Enable memory context injection (default: True)
        """
        prompt = step.params.get("prompt", "")
        role = step.params.get("role", "builder")
        model = step.params.get("model", "claude-sonnet-4-20250514")
        max_tokens = step.params.get("max_tokens", 4096)
        system_prompt = step.params.get("system_prompt")
        use_memory = step.params.get("use_memory", True)

        # Substitute context variables in prompt
        for key, value in context.items():
            if isinstance(value, str):
                prompt = prompt.replace(f"${{{key}}}", value)

        # Inject memory context if available
        if use_memory and self.memory_manager:
            prompt = self.memory_manager.inject_context(role, prompt)

        # Dry run mode - return mock response
        if self.dry_run:
            output = {
                "role": role,
                "prompt": prompt,
                "response": f"[DRY RUN] Claude {role} would process: {prompt[:100]}...",
                "tokens_used": step.params.get("estimated_tokens", 1000),
                "model": model,
                "dry_run": True,
            }
            # Store output in memory even for dry run
            if self.memory_manager:
                self.memory_manager.store_output(role, step.id, output)
            return output

        # Get Claude client
        client = _get_claude_client()
        if not client:
            raise RuntimeError(
                "Claude Code client not available. Check API key configuration."
            )

        if not client.is_configured():
            raise RuntimeError(
                "Claude Code client not configured. Set ANTHROPIC_API_KEY."
            )

        # Execute via API
        if system_prompt:
            # Custom system prompt - use generate_completion
            result = client.generate_completion(
                prompt=prompt,
                system_prompt=system_prompt,
                model=model,
                max_tokens=max_tokens,
            )
        else:
            # Role-based execution
            result = client.execute_agent(
                role=role,
                task=prompt,
                context=context.get("_previous_output"),
                model=model,
                max_tokens=max_tokens,
            )

        if not result.get("success"):
            error_msg = result.get('error', 'Unknown error')
            # Store error in memory
            if self.memory_manager:
                self.memory_manager.store_error(role, step.id, error_msg)
            raise RuntimeError(f"Claude API error: {error_msg}")

        # Estimate tokens (actual count would require API response metadata)
        response_text = result.get("output", "")
        estimated_tokens = len(response_text) // 4 + len(prompt) // 4

        output = {
            "role": role,
            "prompt": prompt,
            "response": response_text,
            "tokens_used": estimated_tokens,
            "model": model,
        }

        # Store output in memory
        if self.memory_manager:
            self.memory_manager.store_output(role, step.id, output)

        return output

    def _execute_openai(self, step: StepConfig, context: dict) -> dict:
        """Execute an OpenAI step using the OpenAI API.

        Params:
            prompt: The prompt to send
            model: OpenAI model to use (default: gpt-4o-mini)
            system_prompt: Optional system prompt
            temperature: Sampling temperature (default: 0.7)
            max_tokens: Maximum tokens in response (optional)
            use_memory: Enable memory context injection (default: True)
        """
        prompt = step.params.get("prompt", "")
        model = step.params.get("model", "gpt-4o-mini")
        system_prompt = step.params.get("system_prompt")
        temperature = step.params.get("temperature", 0.7)
        max_tokens = step.params.get("max_tokens")
        use_memory = step.params.get("use_memory", True)

        # Substitute context variables in prompt
        for key, value in context.items():
            if isinstance(value, str):
                prompt = prompt.replace(f"${{{key}}}", value)

        # Inject memory context if available
        agent_id = f"openai-{model}"
        if use_memory and self.memory_manager:
            prompt = self.memory_manager.inject_context(agent_id, prompt)

        # Dry run mode - return mock response
        if self.dry_run:
            output = {
                "model": model,
                "prompt": prompt,
                "response": f"[DRY RUN] OpenAI {model} would process: {prompt[:100]}...",
                "tokens_used": step.params.get("estimated_tokens", 1000),
                "dry_run": True,
            }
            if self.memory_manager:
                self.memory_manager.store_output(agent_id, step.id, output)
            return output

        # Get OpenAI client
        client = _get_openai_client()
        if not client:
            raise RuntimeError(
                "OpenAI client not available. Check API key configuration."
            )

        try:
            response_text = client.generate_completion(
                prompt=prompt,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
                system_prompt=system_prompt,
            )
        except Exception as e:
            error_msg = str(e)
            if self.memory_manager:
                self.memory_manager.store_error(agent_id, step.id, error_msg)
            raise RuntimeError(f"OpenAI API error: {e}")

        # Estimate tokens (actual count would require API response metadata)
        estimated_tokens = len(response_text) // 4 + len(prompt) // 4

        output = {
            "model": model,
            "prompt": prompt,
            "response": response_text,
            "tokens_used": estimated_tokens,
        }

        # Store output in memory
        if self.memory_manager:
            self.memory_manager.store_output(agent_id, step.id, output)

        return output

    def _substitute_template_vars(self, template: str, item: any, index: int) -> str:
        """Substitute template variables with item value and index.

        Supports:
            ${item} - The current item value
            ${index} - The current item index (0-based)
            ${context_var} - Any variable from execution context
        """
        result = template.replace("${item}", str(item))
        result = result.replace("${index}", str(index))

        # Also substitute context variables
        for key, value in self._context.items():
            if isinstance(value, str):
                result = result.replace(f"${{{key}}}", value)

        return result

    def _execute_fan_out(self, step: StepConfig, context: dict) -> dict:
        """Execute a fan-out (scatter) step.

        Iterates over a list of items and executes a step template for each
        item concurrently with rate limiting.

        Params:
            items: Expression that resolves to a list (e.g., "${files}")
            max_concurrent: Maximum concurrent executions (default: 5)
            step_template: Step configuration template with ${item} placeholders
            fail_fast: If True, abort on first failure (default: False)
            collect_errors: If True, include errors in results (default: True)

        Returns:
            Dict with:
            - results: List of results from each item
            - successful: Count of successful executions
            - failed: Count of failed executions
            - tokens_used: Total tokens used
        """
        # Resolve items from context
        items_expr = step.params.get("items", [])
        if (
            isinstance(items_expr, str)
            and items_expr.startswith("${")
            and items_expr.endswith("}")
        ):
            var_name = items_expr[2:-1]
            items = context.get(var_name, [])
        else:
            items = items_expr

        if not isinstance(items, list):
            raise ValueError(f"fan_out items must be a list, got {type(items)}")

        if not items:
            return {
                "results": [],
                "successful": 0,
                "failed": 0,
                "tokens_used": 0,
            }

        max_concurrent = step.params.get("max_concurrent", 5)
        step_template = step.params.get("step_template", {})
        fail_fast = step.params.get("fail_fast", False)
        collect_errors = step.params.get("collect_errors", True)

        if not step_template:
            raise ValueError("fan_out requires step_template parameter")

        # Start parallel execution tracking
        tracker = get_parallel_tracker()
        execution_id = f"fan_out_{step.id}_{int(time.time() * 1000)}"
        tracker.start_execution(
            execution_id=execution_id,
            pattern_type=ParallelPatternType.FAN_OUT,
            step_id=step.id,
            total_items=len(items),
            max_concurrent=max_concurrent,
            workflow_id=context.get("workflow_id"),
        )

        # Build parallel tasks for each item
        tasks = []
        for idx, item in enumerate(items):
            # Create a step config from template with substituted values
            template_copy = step_template.copy()
            params = template_copy.get("params", {}).copy()

            # Substitute ${item} and ${index} in prompt and other string params
            for key, value in params.items():
                if isinstance(value, str):
                    params[key] = self._substitute_template_vars(value, item, idx)

            template_copy["params"] = params
            template_copy["id"] = f"{step.id}_item_{idx}"
            template_copy["outputs"] = template_copy.get("outputs", [])

            sub_step = StepConfig.from_dict(template_copy)
            branch_id = f"{step.id}_item_{idx}"

            # Create task with tracking
            def make_handler(
                sub_step_config: StepConfig,
                item_value: any,
                item_idx: int,
                b_id: str,
            ):
                def handler(**kwargs):
                    # Start branch tracking
                    tracker.start_branch(execution_id, b_id, item_idx, item_value)

                    try:
                        step_handler = self._handlers.get(sub_step_config.type)
                        if not step_handler:
                            raise ValueError(
                                f"Unknown step type: {sub_step_config.type}"
                            )

                        # Add item to context for this execution
                        item_context = context.copy()
                        item_context["item"] = item_value
                        item_context["index"] = item_idx

                        output = step_handler(sub_step_config, item_context)
                        tokens = output.get("tokens_used", 0) if output else 0

                        # Complete branch tracking
                        tracker.complete_branch(execution_id, b_id, tokens)

                        return {
                            "item": item_value,
                            "index": item_idx,
                            "output": output,
                        }
                    except Exception as e:
                        tracker.fail_branch(execution_id, b_id, str(e))
                        raise

                return handler

            task = ParallelTask(
                id=branch_id,
                step_id=sub_step.id,
                handler=make_handler(sub_step, item, idx, branch_id),
                kwargs={"step_type": sub_step.type},
            )
            tasks.append(task)

        # Rate limiting configuration from step params
        adaptive_enabled = step.params.get("adaptive_rate_limiting", True)
        distributed_enabled = step.params.get("distributed_rate_limiting", False)
        backoff_factor = step.params.get("rate_limit_backoff_factor", 0.5)
        recovery_threshold = step.params.get("rate_limit_recovery_threshold", 10)

        # Use rate-limited executor with full configuration
        from .rate_limited_executor import AdaptiveRateLimitConfig

        adaptive_config = (
            AdaptiveRateLimitConfig(
                backoff_factor=backoff_factor,
                recovery_threshold=recovery_threshold,
            )
            if adaptive_enabled
            else None
        )

        executor = RateLimitedParallelExecutor(
            strategy=ParallelStrategy.ASYNCIO,
            max_workers=max_concurrent,
            timeout=step.timeout_seconds or 300.0,
            provider_limits={
                "anthropic": step.params.get("anthropic_concurrent", 5),
                "openai": step.params.get("openai_concurrent", 8),
            },
            adaptive=adaptive_enabled,
            adaptive_config=adaptive_config,
            distributed=distributed_enabled,
            distributed_window=step.params.get("distributed_window", 60),
            distributed_rpm={
                "anthropic": step.params.get("anthropic_rpm", 60),
                "openai": step.params.get("openai_rpm", 90),
            },
        )

        results: list[dict] = []
        errors: list[dict] = []
        total_tokens = 0

        def on_complete(task_id: str, result: any):
            nonlocal total_tokens
            results.append(result)
            if isinstance(result, dict) and "output" in result:
                total_tokens += result["output"].get("tokens_used", 0)

        def on_error(task_id: str, error: Exception):
            if collect_errors:
                errors.append(
                    {
                        "task_id": task_id,
                        "error": str(error),
                    }
                )

        parallel_result = executor.execute_parallel(
            tasks=tasks,
            on_complete=on_complete,
            on_error=on_error,
            fail_fast=fail_fast,
        )

        # Capture rate limit stats before completing tracking
        provider_stats = executor.get_provider_stats()

        # Update tracker with rate limit state for each provider
        for provider, stats in provider_stats.items():
            if stats.get("total_429s", 0) > 0 or stats.get("is_throttled", False):
                tracker.update_rate_limit_state(
                    provider=provider,
                    current_limit=stats.get("current_limit", 0),
                    base_limit=stats.get("base_limit", 0),
                    total_429s=stats.get("total_429s", 0),
                    is_throttled=stats.get("is_throttled", False),
                )

        # Complete execution tracking
        if parallel_result.failed:
            tracker.fail_execution(execution_id)
        else:
            tracker.complete_execution(execution_id)

        # Sort results by index
        results.sort(key=lambda x: x.get("index", 0))

        # Collect all results for output variable
        all_results = [
            r.get("output", {}).get("response", r.get("output", {})) for r in results
        ]

        return {
            "results": all_results,
            "detailed_results": results,
            "errors": errors if collect_errors else [],
            "successful": len(parallel_result.successful),
            "failed": len(parallel_result.failed),
            "cancelled": len(parallel_result.cancelled),
            "tokens_used": total_tokens,
            "duration_ms": parallel_result.total_duration_ms,
            "execution_id": execution_id,
            "rate_limit_stats": provider_stats,
        }

    def _execute_fan_in(self, step: StepConfig, context: dict) -> dict:
        """Execute a fan-in (gather) step.

        Aggregates results from a previous step (typically fan_out) and
        optionally processes them through an aggregation step.

        Params:
            input: Expression that resolves to the input list (e.g., "${reviews}")
            aggregation: "concat" | "claude_code" | "openai" | "custom"
            aggregate_prompt: Prompt template for AI aggregation
            separator: Separator for concat aggregation (default: "\\n")

        Returns:
            Dict with aggregated result
        """
        # Resolve input from context
        input_expr = step.params.get("input", [])
        if (
            isinstance(input_expr, str)
            and input_expr.startswith("${")
            and input_expr.endswith("}")
        ):
            var_name = input_expr[2:-1]
            input_data = context.get(var_name, [])
        else:
            input_data = input_expr

        if not isinstance(input_data, list):
            input_data = [input_data]

        aggregation = step.params.get("aggregation", "concat")
        aggregate_prompt = step.params.get("aggregate_prompt", "")

        if aggregation == "concat":
            separator = step.params.get("separator", "\n")
            result = separator.join(str(item) for item in input_data)
            return {
                "response": result,
                "aggregation_type": "concat",
                "item_count": len(input_data),
                "tokens_used": 0,
            }

        elif aggregation in ("claude_code", "openai"):
            # Use AI to aggregate results
            items_text = "\n---\n".join(str(item) for item in input_data)
            prompt = aggregate_prompt.replace("${items}", items_text)

            # Substitute other context variables
            for key, value in context.items():
                if isinstance(value, str):
                    prompt = prompt.replace(f"${{{key}}}", value)

            # Create sub-step for aggregation
            agg_step_config = {
                "id": f"{step.id}_aggregate",
                "type": aggregation,
                "params": {
                    "prompt": prompt,
                    "role": step.params.get("role", "analyst"),
                    "model": step.params.get("model"),
                    "max_tokens": step.params.get("max_tokens", 4096),
                },
            }
            agg_step = StepConfig.from_dict(agg_step_config)

            handler = self._handlers.get(aggregation)
            if not handler:
                raise ValueError(f"Unknown aggregation type: {aggregation}")

            output = handler(agg_step, context)
            return {
                "response": output.get("response", ""),
                "aggregation_type": aggregation,
                "item_count": len(input_data),
                "tokens_used": output.get("tokens_used", 0),
            }

        elif aggregation == "custom":
            # Custom aggregation via callback
            callback_name = step.params.get("callback")
            if callback_name and callback_name in self.fallback_callbacks:
                callback = self.fallback_callbacks[callback_name]
                result = callback(step, context, None)
                return {
                    "response": result,
                    "aggregation_type": "custom",
                    "item_count": len(input_data),
                    "tokens_used": 0,
                }
            raise ValueError(f"Custom callback '{callback_name}' not registered")

        else:
            raise ValueError(f"Unknown aggregation type: {aggregation}")

    def _execute_map_reduce(self, step: StepConfig, context: dict) -> dict:
        """Execute a map-reduce step.

        Combines fan_out (map) and fan_in (reduce) in a single step.

        Params:
            items: Expression that resolves to a list
            max_concurrent: Maximum concurrent map executions
            map_step: Step configuration for map phase
            reduce_step: Step configuration for reduce phase
            fail_fast: If True, abort map phase on first failure

        Returns:
            Dict with final reduced result
        """
        # Resolve items
        items_expr = step.params.get("items", [])
        if (
            isinstance(items_expr, str)
            and items_expr.startswith("${")
            and items_expr.endswith("}")
        ):
            var_name = items_expr[2:-1]
            items = context.get(var_name, [])
        else:
            items = items_expr

        if not isinstance(items, list):
            raise ValueError(f"map_reduce items must be a list, got {type(items)}")

        map_step_config = step.params.get("map_step", {})
        reduce_step_config = step.params.get("reduce_step", {})

        if not map_step_config:
            raise ValueError("map_reduce requires map_step parameter")
        if not reduce_step_config:
            raise ValueError("map_reduce requires reduce_step parameter")

        # Execute map phase using fan_out
        fan_out_step = StepConfig(
            id=f"{step.id}_map",
            type="fan_out",
            params={
                "items": items,
                "max_concurrent": step.params.get("max_concurrent", 5),
                "step_template": map_step_config,
                "fail_fast": step.params.get("fail_fast", False),
            },
            timeout_seconds=step.timeout_seconds,
        )

        map_result = self._execute_fan_out(fan_out_step, context)

        if map_result["failed"] > 0 and step.params.get("fail_fast", False):
            return {
                "response": None,
                "map_results": map_result["results"],
                "map_errors": map_result.get("errors", []),
                "phase": "map_failed",
                "tokens_used": map_result["tokens_used"],
            }

        # Execute reduce phase using fan_in
        # Put map results into context for reduce
        reduce_context = context.copy()
        reduce_context["map_results"] = map_result["results"]

        # Substitute ${map_results} in reduce prompt
        reduce_params = reduce_step_config.get("params", {}).copy()
        if "prompt" in reduce_params:
            items_text = "\n---\n".join(str(r) for r in map_result["results"])
            reduce_params["prompt"] = reduce_params["prompt"].replace(
                "${map_results}", items_text
            )

        fan_in_step = StepConfig(
            id=f"{step.id}_reduce",
            type="fan_in",
            params={
                "input": map_result["results"],
                "aggregation": reduce_step_config.get("type", "claude_code"),
                "aggregate_prompt": reduce_params.get("prompt", ""),
                "role": reduce_params.get("role", "analyst"),
                "model": reduce_params.get("model"),
            },
            timeout_seconds=step.timeout_seconds,
        )

        reduce_result = self._execute_fan_in(fan_in_step, reduce_context)

        return {
            "response": reduce_result.get("response", ""),
            "map_results": map_result["results"],
            "map_successful": map_result["successful"],
            "map_failed": map_result["failed"],
            "tokens_used": map_result["tokens_used"]
            + reduce_result.get("tokens_used", 0),
            "duration_ms": map_result.get("duration_ms", 0),
        }

    def get_context(self) -> dict:
        """Get current execution context."""
        return self._context.copy()

    def set_context(self, context: dict) -> None:
        """Set execution context."""
        self._context = context.copy()
