"""Workflow Executor with Contract Validation and State Persistence."""

from __future__ import annotations

import subprocess
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable

from .loader import WorkflowConfig, StepConfig

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
    started_at: datetime = field(default_factory=datetime.utcnow)
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
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
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
    ):
        """Initialize executor.

        Args:
            checkpoint_manager: Optional CheckpointManager for state persistence
            contract_validator: Optional ContractValidator for contract validation
            budget_manager: Optional BudgetManager for token tracking
            dry_run: If True, use mock responses instead of real API calls
        """
        self.checkpoint_manager = checkpoint_manager
        self.contract_validator = contract_validator
        self.budget_manager = budget_manager
        self.dry_run = dry_run
        self._handlers: dict[str, StepHandler] = {
            "shell": self._execute_shell,
            "checkpoint": self._execute_checkpoint,
            "parallel": self._execute_parallel,
            "claude_code": self._execute_claude_code,
            "openai": self._execute_openai,
        }
        self._context: dict = {}

    def register_handler(self, step_type: str, handler: StepHandler) -> None:
        """Register a custom step handler.

        Args:
            step_type: Step type name
            handler: Function that takes (StepConfig, context) and returns output dict
        """
        self._handlers[step_type] = handler

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

        # Validate required inputs
        for input_name, input_spec in workflow.inputs.items():
            if input_spec.get("required", False) and input_name not in self._context:
                if "default" in input_spec:
                    self._context[input_name] = input_spec["default"]
                else:
                    result.status = "failed"
                    result.error = f"Missing required input: {input_name}"
                    return result

        # Start workflow in checkpoint manager
        workflow_id = None
        if self.checkpoint_manager:
            workflow_id = self.checkpoint_manager.start_workflow(
                workflow.name,
                config={"inputs": self._context},
            )

        # Find resume point
        start_index = 0
        if resume_from:
            for i, step in enumerate(workflow.steps):
                if step.id == resume_from:
                    start_index = i
                    break

        # Execute steps
        try:
            for i, step in enumerate(workflow.steps[start_index:], start=start_index):
                # Check budget before execution
                if self.budget_manager:
                    if not self.budget_manager.can_allocate(step.params.get("estimated_tokens", 1000)):
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
                    if step.on_failure == "abort":
                        result.status = "failed"
                        result.error = f"Step '{step.id}' failed: {step_result.error}"
                        break
                    elif step.on_failure == "skip":
                        continue

                # Store outputs in context
                for output_key in step.outputs:
                    if output_key in step_result.output:
                        self._context[output_key] = step_result.output[output_key]

            else:
                # All steps completed
                result.status = "success"

        except Exception as e:
            result.status = "failed"
            result.error = str(e)
            if self.checkpoint_manager and workflow_id:
                self.checkpoint_manager.fail_workflow(str(e), workflow_id)
        else:
            if self.checkpoint_manager and workflow_id:
                if result.status == "success":
                    self.checkpoint_manager.complete_workflow(workflow_id)
                else:
                    self.checkpoint_manager.fail_workflow(result.error or "Unknown error", workflow_id)

        # Collect workflow outputs
        for output_name in workflow.outputs:
            if output_name in self._context:
                result.outputs[output_name] = self._context[output_name]

        result.completed_at = datetime.utcnow()
        result.total_duration_ms = int(
            (result.completed_at - result.started_at).total_seconds() * 1000
        )

        return result

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
                        output = handler(step, self._context)
                        ctx.output_data = output
                        ctx.tokens_used = output.get("tokens_used", 0)
                else:
                    output = handler(step, self._context)

                # Validate output contract if applicable
                if self.contract_validator and role:
                    self.contract_validator.validate_output(role, output)

                result.status = StepStatus.SUCCESS
                result.output = output
                result.tokens_used = output.get("tokens_used", 0)
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

    def _execute_shell(self, step: StepConfig, context: dict) -> dict:
        """Execute a shell command step."""
        command = step.params.get("command", "")
        if not command:
            raise ValueError("Shell step requires 'command' parameter")

        # Substitute context variables
        for key, value in context.items():
            command = command.replace(f"${{{key}}}", str(value))

        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=step.timeout_seconds,
        )

        if result.returncode != 0 and not step.params.get("allow_failure", False):
            raise RuntimeError(f"Command failed with code {result.returncode}: {result.stderr}")

        return {
            "stdout": result.stdout,
            "stderr": result.stderr,
            "returncode": result.returncode,
        }

    def _execute_checkpoint(self, step: StepConfig, context: dict) -> dict:
        """Create a checkpoint (no-op if no checkpoint manager)."""
        return {"checkpoint": step.id}

    def _execute_parallel(self, step: StepConfig, context: dict) -> dict:
        """Execute parallel sub-steps.

        Note: Actual parallel execution would require async/threading.
        This is a placeholder that executes sequentially.
        """
        sub_steps = step.params.get("steps", [])
        results = {}

        for sub_step_data in sub_steps:
            sub_step = StepConfig.from_dict(sub_step_data)
            handler = self._handlers.get(sub_step.type)
            if handler:
                try:
                    output = handler(sub_step, context)
                    results[sub_step.id] = output
                except Exception as e:
                    results[sub_step.id] = {"error": str(e)}

        return {"parallel_results": results}

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
            raise RuntimeError("Claude Code client not available. Check API key configuration.")

        if not client.is_configured():
            raise RuntimeError("Claude Code client not configured. Set ANTHROPIC_API_KEY.")

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
            raise RuntimeError(f"Claude API error: {result.get('error', 'Unknown error')}")

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
            raise RuntimeError("OpenAI client not available. Check API key configuration.")

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
