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
from test_ai.utils.validation import substitute_shell_variables, validate_shell_command
from test_ai.utils.circuit_breaker import CircuitBreaker, CircuitBreakerError

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
    ):
        """Initialize executor.

        Args:
            checkpoint_manager: Optional CheckpointManager for state persistence
            contract_validator: Optional ContractValidator for contract validation
            budget_manager: Optional BudgetManager for token tracking
            dry_run: If True, use mock responses instead of real API calls
            error_callback: Optional callback for error notifications (step_id, workflow_id, error)
            fallback_callbacks: Dict of named callbacks for fallback handling
        """
        self.checkpoint_manager = checkpoint_manager
        self.contract_validator = contract_validator
        self.budget_manager = budget_manager
        self.dry_run = dry_run
        self.error_callback = error_callback
        self.fallback_callbacks = fallback_callbacks or {}
        self._handlers: dict[str, StepHandler] = {
            "shell": self._execute_shell,
            "checkpoint": self._execute_checkpoint,
            "parallel": self._execute_parallel,
            "claude_code": self._execute_claude_code,
            "openai": self._execute_openai,
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
            fallback_output = self._execute_fallback(step, step_result.error, workflow_id)
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

        # Clear workflow ID
        self._current_workflow_id = None

    def execute(
        self,
        workflow: WorkflowConfig,
        inputs: dict = None,
        resume_from: str = None,
    ) -> ExecutionResult:
        """Execute a workflow.

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

        # Execute steps
        error = None
        try:
            for step in workflow.steps[start_index:]:
                # Check budget before execution
                if self.budget_manager and not self.budget_manager.can_allocate(
                    step.params.get("estimated_tokens", 1000)
                ):
                    result.status = "failed"
                    result.error = "Token budget exceeded"
                    break

                step_result = self._execute_step(step, workflow_id)
                result.steps.append(step_result)
                result.total_tokens += step_result.tokens_used
                result.total_duration_ms += step_result.duration_ms

                # Record tokens in budget manager
                if self.budget_manager and step_result.tokens_used > 0:
                    self.budget_manager.record_usage(step.id, step_result.tokens_used)

                # Handle step failure
                if step_result.status == StepStatus.FAILED:
                    action = self._handle_step_failure(
                        step, step_result, result, workflow_id
                    )
                    if action == "abort":
                        break
                    if action == "skip":
                        continue

                # Store outputs in context
                for output_key in step.outputs:
                    if output_key in step_result.output:
                        self._context[output_key] = step_result.output[output_key]
            else:
                # All steps completed
                result.status = "success"

        except Exception as e:
            error = e

        self._finalize_workflow(result, workflow, workflow_id, error)
        return result

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

        # Execute steps
        error = None
        try:
            for step in workflow.steps[start_index:]:
                # Check budget before execution
                if self.budget_manager and not self.budget_manager.can_allocate(
                    step.params.get("estimated_tokens", 1000)
                ):
                    result.status = "failed"
                    result.error = "Token budget exceeded"
                    break

                step_result = await self._execute_step_async(step, workflow_id)
                result.steps.append(step_result)
                result.total_tokens += step_result.tokens_used
                result.total_duration_ms += step_result.duration_ms

                # Record tokens in budget manager
                if self.budget_manager and step_result.tokens_used > 0:
                    self.budget_manager.record_usage(step.id, step_result.tokens_used)

                # Handle step failure
                if step_result.status == StepStatus.FAILED:
                    action = await self._handle_step_failure_async(
                        step, step_result, result, workflow_id
                    )
                    if action == "abort":
                        break
                    if action == "skip":
                        continue

                # Store outputs in context
                for output_key in step.outputs:
                    if output_key in step_result.output:
                        self._context[output_key] = step_result.output[output_key]
            else:
                # All steps completed
                result.status = "success"

        except Exception as e:
            error = e

        self._finalize_workflow(result, workflow, workflow_id, error)
        return result

    async def _execute_step_async(
        self, step: StepConfig, workflow_id: str = None
    ) -> StepResult:
        """Execute a single workflow step asynchronously."""
        start_time = time.time()
        result = StepResult(step_id=step.id, status=StepStatus.PENDING)

        # Check condition
        if step.condition and not step.condition.evaluate(self._context):
            result.status = StepStatus.SKIPPED
            return result

        # Validate input contract if applicable
        role = step.params.get("role")
        if self.contract_validator and role:
            try:
                input_data = step.params.get("input", {})
                self.contract_validator.validate_input(role, input_data, self._context)
            except Exception as e:
                result.status = StepStatus.FAILED
                result.error = f"Input validation failed: {e}"
                return result

        # Execute with retries
        handler = self._handlers.get(step.type)
        if not handler:
            result.status = StepStatus.FAILED
            result.error = f"Unknown step type: {step.type}"
            return result

        # Check circuit breaker if configured
        cb_key = step.circuit_breaker_key or step.type
        cb = _circuit_breakers.get(cb_key)
        if cb and cb.is_open:
            result.status = StepStatus.FAILED
            result.error = f"Circuit breaker open for {cb_key}"
            logger.warning(f"Step '{step.id}' skipped: circuit breaker open")
            return result

        last_error = None
        for attempt in range(step.max_retries + 1):
            result.retries = attempt
            result.status = StepStatus.RUNNING

            try:
                # Create checkpoint before execution
                if self.checkpoint_manager and workflow_id:
                    with self.checkpoint_manager.stage(
                        step.id,
                        input_data=step.params,
                        workflow_id=workflow_id,
                    ) as ctx:
                        # Run handler in executor to avoid blocking event loop
                        loop = asyncio.get_event_loop()
                        if cb:
                            output = await loop.run_in_executor(
                                None, cb.call, handler, step, self._context
                            )
                        else:
                            output = await loop.run_in_executor(
                                None, handler, step, self._context
                            )
                        ctx.output_data = output
                        ctx.tokens_used = output.get("tokens_used", 0)
                else:
                    # Run handler in executor to avoid blocking event loop
                    loop = asyncio.get_event_loop()
                    if cb:
                        output = await loop.run_in_executor(
                            None, cb.call, handler, step, self._context
                        )
                    else:
                        output = await loop.run_in_executor(
                            None, handler, step, self._context
                        )

                # Validate output contract if applicable
                if self.contract_validator and role:
                    self.contract_validator.validate_output(role, output)

                result.status = StepStatus.SUCCESS
                result.output = output
                result.tokens_used = output.get("tokens_used", 0)
                break

            except CircuitBreakerError as e:
                # Circuit breaker opened during execution
                result.status = StepStatus.FAILED
                result.error = str(e)
                break

            except Exception as e:
                last_error = str(e)
                if attempt < step.max_retries:
                    await asyncio.sleep(min(2**attempt, 30))  # Exponential backoff
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

        # Check condition
        if step.condition and not step.condition.evaluate(self._context):
            result.status = StepStatus.SKIPPED
            return result

        # Validate input contract if applicable
        role = step.params.get("role")
        if self.contract_validator and role:
            try:
                input_data = step.params.get("input", {})
                self.contract_validator.validate_input(role, input_data, self._context)
            except Exception as e:
                result.status = StepStatus.FAILED
                result.error = f"Input validation failed: {e}"
                return result

        # Execute with retries
        handler = self._handlers.get(step.type)
        if not handler:
            result.status = StepStatus.FAILED
            result.error = f"Unknown step type: {step.type}"
            return result

        # Check circuit breaker if configured
        cb_key = step.circuit_breaker_key or step.type
        cb = _circuit_breakers.get(cb_key)
        if cb and cb.is_open:
            result.status = StepStatus.FAILED
            result.error = f"Circuit breaker open for {cb_key}"
            logger.warning(f"Step '{step.id}' skipped: circuit breaker open")
            return result

        last_error = None
        for attempt in range(step.max_retries + 1):
            result.retries = attempt
            result.status = StepStatus.RUNNING

            try:
                # Create checkpoint before execution
                if self.checkpoint_manager and workflow_id:
                    with self.checkpoint_manager.stage(
                        step.id,
                        input_data=step.params,
                        workflow_id=workflow_id,
                    ) as ctx:
                        # Use circuit breaker if configured
                        if cb:
                            output = cb.call(handler, step, self._context)
                        else:
                            output = handler(step, self._context)
                        ctx.output_data = output
                        ctx.tokens_used = output.get("tokens_used", 0)
                else:
                    # Use circuit breaker if configured
                    if cb:
                        output = cb.call(handler, step, self._context)
                    else:
                        output = handler(step, self._context)

                # Validate output contract if applicable
                if self.contract_validator and role:
                    self.contract_validator.validate_output(role, output)

                result.status = StepStatus.SUCCESS
                result.output = output
                result.tokens_used = output.get("tokens_used", 0)
                break

            except CircuitBreakerError as e:
                # Circuit breaker opened during execution
                result.status = StepStatus.FAILED
                result.error = str(e)
                break

            except Exception as e:
                last_error = str(e)
                if attempt < step.max_retries:
                    time.sleep(min(2**attempt, 30))  # Exponential backoff
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

    def _execute_parallel(self, step: StepConfig, context: dict) -> dict:
        """Execute parallel sub-steps using ParallelExecutor.

        Params:
            steps: List of sub-step configurations
            strategy: "threading" | "asyncio" (default: "threading")
            max_workers: int (default: 4)
            fail_fast: bool - if True, abort on first failure (default: False)

        Checkpointing:
            Each sub-step is checkpointed with stage name "{parent_step_id}.{sub_step_id}"
            using checkpoint_now() for thread safety.
        """
        sub_steps = step.params.get("steps", [])
        strategy_str = step.params.get("strategy", "threading")
        max_workers = step.params.get("max_workers", 4)
        fail_fast = step.params.get("fail_fast", False)

        if not sub_steps:
            return {"parallel_results": {}, "tokens_used": 0}

        # Map strategy string to enum
        strategy_map = {
            "threading": ParallelStrategy.THREADING,
            "asyncio": ParallelStrategy.ASYNCIO,
            "process": ParallelStrategy.PROCESS,
        }
        strategy = strategy_map.get(strategy_str, ParallelStrategy.THREADING)

        # Create executor
        executor = ParallelExecutor(
            strategy=strategy,
            max_workers=max_workers,
            timeout=step.timeout_seconds,
        )

        # Parse sub-steps and collect dependencies
        parsed_steps: dict[str, StepConfig] = {}
        for sub_step_data in sub_steps:
            sub_step = StepConfig.from_dict(sub_step_data)
            parsed_steps[sub_step.id] = sub_step

        # Shared state for results and context updates
        results: dict[str, dict] = {}
        total_tokens = 0
        first_error: Exception | None = None
        context_updates: dict[str, any] = {}

        # Parent step ID for compound checkpoint stage names
        parent_step_id = step.id

        def make_handler(sub_step: StepConfig):
            """Create a handler closure for a sub-step with retry support."""

            def handler():
                nonlocal total_tokens, first_error, context_updates

                # Track timing for checkpoint (across all retries)
                start_time = time.time()
                stage_name = f"{parent_step_id}.{sub_step.id}"
                output = None
                error_msg = None
                tokens_used = 0
                retries_used = 0
                max_retries = sub_step.max_retries
                last_exception = None

                try:
                    for attempt in range(max_retries + 1):
                        try:
                            # Check budget before each attempt if configured
                            estimated_tokens = sub_step.params.get(
                                "estimated_tokens", 1000
                            )
                            if self.budget_manager:
                                if not self.budget_manager.can_allocate(
                                    estimated_tokens, agent_id=stage_name
                                ):
                                    raise RuntimeError(
                                        f"Budget exceeded for sub-step '{sub_step.id}'"
                                    )

                            # Get current context snapshot plus any updates
                            step_context = context.copy()
                            step_context.update(context_updates)

                            # Get the appropriate handler for this step type
                            step_handler = self._handlers.get(sub_step.type)
                            if not step_handler:
                                raise ValueError(f"Unknown step type: {sub_step.type}")

                            # Execute the step
                            output = step_handler(sub_step, step_context)

                            # Track tokens
                            tokens_used = output.get("tokens_used", 0)
                            total_tokens += tokens_used

                            # Store outputs in context updates for dependent steps
                            for output_key in sub_step.outputs:
                                if output_key in output:
                                    context_updates[output_key] = output[output_key]

                            # Success - add retries info
                            output["retries"] = retries_used
                            error_msg = None
                            last_exception = None
                            break

                        except Exception as e:
                            error_msg = str(e)
                            last_exception = e
                            retries_used = attempt + 1
                            if attempt < max_retries:
                                # Exponential backoff (same formula as main executor)
                                time.sleep(min(2**attempt, 30))
                            # Continue to finally block after last attempt

                    # Re-raise if all retries exhausted
                    if last_exception is not None:
                        raise last_exception

                    return output

                finally:
                    # Record final state after all retries complete
                    duration_ms = int((time.time() - start_time) * 1000)

                    # Record budget usage for sub-step (thread-safe)
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

                    # Checkpoint the sub-step (thread-safe via checkpoint_now)
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

            return handler

        # Create parallel tasks
        tasks = []
        for sub_step_id, sub_step in parsed_steps.items():
            task = ParallelTask(
                id=sub_step_id,
                step_id=sub_step_id,
                handler=make_handler(sub_step),
                dependencies=sub_step.depends_on,
            )
            tasks.append(task)

        # Callbacks for completion and error handling
        def on_complete(task_id: str, result: any):
            results[task_id] = result

        def on_error(task_id: str, error: Exception):
            nonlocal first_error
            results[task_id] = {"error": str(error)}
            if first_error is None:
                first_error = error

        # Execute in parallel
        try:
            parallel_result = executor.execute_parallel(
                tasks=tasks,
                on_complete=on_complete,
                on_error=on_error,
                fail_fast=fail_fast,
            )
        except ValueError as e:
            # Dependency resolution error (circular deps, deadlock)
            raise RuntimeError(f"Parallel execution failed: {e}")

        # Check for failures if fail_fast mode
        if fail_fast and first_error is not None:
            raise RuntimeError(f"Parallel step failed: {first_error}")

        # Merge successful outputs back into main context
        self._context.update(context_updates)

        # Calculate total retries from results
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
        """
        prompt = step.params.get("prompt", "")
        role = step.params.get("role", "builder")
        model = step.params.get("model", "claude-sonnet-4-20250514")
        max_tokens = step.params.get("max_tokens", 4096)
        system_prompt = step.params.get("system_prompt")

        # Substitute context variables in prompt
        for key, value in context.items():
            if isinstance(value, str):
                prompt = prompt.replace(f"${{{key}}}", value)

        # Dry run mode - return mock response
        if self.dry_run:
            return {
                "role": role,
                "prompt": prompt,
                "response": f"[DRY RUN] Claude {role} would process: {prompt[:100]}...",
                "tokens_used": step.params.get("estimated_tokens", 1000),
                "model": model,
                "dry_run": True,
            }

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
            raise RuntimeError(
                f"Claude API error: {result.get('error', 'Unknown error')}"
            )

        # Estimate tokens (actual count would require API response metadata)
        response_text = result.get("output", "")
        estimated_tokens = len(response_text) // 4 + len(prompt) // 4

        return {
            "role": role,
            "prompt": prompt,
            "response": response_text,
            "tokens_used": estimated_tokens,
            "model": model,
        }

    def _execute_openai(self, step: StepConfig, context: dict) -> dict:
        """Execute an OpenAI step using the OpenAI API.

        Params:
            prompt: The prompt to send
            model: OpenAI model to use (default: gpt-4o-mini)
            system_prompt: Optional system prompt
            temperature: Sampling temperature (default: 0.7)
            max_tokens: Maximum tokens in response (optional)
        """
        prompt = step.params.get("prompt", "")
        model = step.params.get("model", "gpt-4o-mini")
        system_prompt = step.params.get("system_prompt")
        temperature = step.params.get("temperature", 0.7)
        max_tokens = step.params.get("max_tokens")

        # Substitute context variables in prompt
        for key, value in context.items():
            if isinstance(value, str):
                prompt = prompt.replace(f"${{{key}}}", value)

        # Dry run mode - return mock response
        if self.dry_run:
            return {
                "model": model,
                "prompt": prompt,
                "response": f"[DRY RUN] OpenAI {model} would process: {prompt[:100]}...",
                "tokens_used": step.params.get("estimated_tokens", 1000),
                "dry_run": True,
            }

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
            raise RuntimeError(f"OpenAI API error: {e}")

        # Estimate tokens (actual count would require API response metadata)
        estimated_tokens = len(response_text) // 4 + len(prompt) // 4

        return {
            "model": model,
            "prompt": prompt,
            "response": response_text,
            "tokens_used": estimated_tokens,
        }

    def get_context(self) -> dict:
        """Get current execution context."""
        return self._context.copy()

    def set_context(self, context: dict) -> None:
        """Set execution context."""
        self._context = context.copy()
