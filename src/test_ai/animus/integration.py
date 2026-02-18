"""Gorgon-as-Animus-Integration bridge.

Exposes Gorgon's workflow orchestration capabilities as an Animus
integration, conforming to the BaseIntegration ABC pattern:
    connect(credentials) -> bool
    disconnect() -> bool
    verify() -> bool
    get_tools() -> list[dict]
"""

from __future__ import annotations

import logging
from typing import Any

from .config import AnimusBridgeConfig
from .identity import IdentityStore
from .memory_bridge import AnimusMemoryProvider
from .safety_bridge import SafetyGuardBridge

logger = logging.getLogger(__name__)


class GorgonIntegration:
    """Registers Gorgon as an integration in Animus.

    Exposes workflow execution, job management, and agent delegation
    as tools that Animus's CognitiveLayer can invoke. Manages the
    lifecycle of the Gorgon connection (API or in-process).

    When connected, Animus can:
    - Execute Gorgon workflows
    - Check job status
    - List available workflows
    - Delegate complex multi-step tasks to Gorgon's agent pipeline
    """

    name: str = "gorgon"
    display_name: str = "Gorgon Orchestrator"
    auth_type: str = "api_key"

    def __init__(
        self,
        config: AnimusBridgeConfig | None = None,
        identity_store: IdentityStore | None = None,
        memory_provider: AnimusMemoryProvider | None = None,
        safety_guard: SafetyGuardBridge | None = None,
    ):
        self.config = config or AnimusBridgeConfig()
        self.identity_store = identity_store
        self.memory_provider = memory_provider
        self.safety_guard = safety_guard
        self._connected = False
        self._executor = None

    @property
    def is_connected(self) -> bool:
        """Whether the integration is currently connected."""
        return self._connected

    async def connect(self, credentials: dict[str, Any] | None = None) -> bool:
        """Connect to Gorgon (initialize the workflow executor).

        For in-process usage, this sets up the WorkflowExecutor
        with Animus-aware memory and safety hooks.
        """
        try:
            from test_ai.workflow.executor_core import WorkflowExecutor

            # Build memory manager if memory provider is available
            memory_manager = None
            if self.memory_provider:
                from test_ai.state.agent_context import WorkflowMemoryManager
                from test_ai.state.agent_memory import AgentMemory

                memory_manager = WorkflowMemoryManager(
                    memory=AgentMemory(db_path=self.config.memory_db_path),
                )

            self._executor = WorkflowExecutor(
                memory_manager=memory_manager,
            )
            self._connected = True
            logger.info("Gorgon integration connected")
            return True

        except Exception as e:
            logger.error("Failed to connect Gorgon integration: %s", e)
            self._connected = False
            return False

    async def disconnect(self) -> bool:
        """Disconnect from Gorgon."""
        self._executor = None
        self._connected = False
        logger.info("Gorgon integration disconnected")
        return True

    async def verify(self) -> bool:
        """Verify the connection is healthy."""
        if not self._connected or self._executor is None:
            return False

        # Verify executor is functional
        try:
            # Check that the executor has its handlers registered
            return bool(self._executor._handlers)
        except Exception:
            return False

    def get_tools(self) -> list[dict[str, Any]]:
        """Return the tools Gorgon exposes to Animus.

        These conform to Animus's Tool schema so its CognitiveLayer
        can invoke them via the tool-use loop.
        """
        return [
            {
                "name": "gorgon_execute_workflow",
                "description": (
                    "Execute a multi-agent workflow through Gorgon's orchestration "
                    "engine. Handles agent delegation, budget control, checkpointing, "
                    "and quality gates."
                ),
                "parameters": {
                    "workflow_path": {
                        "type": "string",
                        "description": "Path to workflow YAML file",
                        "required": True,
                    },
                    "variables": {
                        "type": "object",
                        "description": "Variables to pass to the workflow",
                        "required": False,
                    },
                    "dry_run": {
                        "type": "boolean",
                        "description": "If true, simulate execution without calling APIs",
                        "required": False,
                    },
                },
            },
            {
                "name": "gorgon_list_workflows",
                "description": "List available workflow definitions.",
                "parameters": {},
            },
            {
                "name": "gorgon_agent_delegate",
                "description": (
                    "Delegate a task to a specific Gorgon agent role "
                    "(planner, builder, tester, reviewer, architect, documenter)."
                ),
                "parameters": {
                    "role": {
                        "type": "string",
                        "description": "Agent role to delegate to",
                        "required": True,
                    },
                    "task": {
                        "type": "string",
                        "description": "Task description for the agent",
                        "required": True,
                    },
                    "context": {
                        "type": "string",
                        "description": "Additional context for the agent",
                        "required": False,
                    },
                },
            },
        ]

    async def execute_tool(
        self, tool_name: str, params: dict[str, Any]
    ) -> dict[str, Any]:
        """Execute a tool by name with parameters.

        Called by Animus's CognitiveLayer when it invokes a Gorgon tool.
        """
        if not self._connected:
            return {"error": "Gorgon integration not connected"}

        # Safety check before execution
        if self.safety_guard:
            action = {
                "description": f"Execute Gorgon tool: {tool_name}",
                "tool": tool_name,
                "params": params,
            }
            allowed, reason = self.safety_guard.check_action(action)
            if not allowed:
                return {"error": f"Blocked by safety guard: {reason}"}

        handlers = {
            "gorgon_execute_workflow": self._tool_execute_workflow,
            "gorgon_list_workflows": self._tool_list_workflows,
            "gorgon_agent_delegate": self._tool_agent_delegate,
        }

        handler = handlers.get(tool_name)
        if not handler:
            return {"error": f"Unknown tool: {tool_name}"}

        try:
            result = await handler(params)

            # Store result as memory if configured
            if self.memory_provider and self.config.store_workflow_results:
                from .models import MemoryType

                self.memory_provider.store_workflow_result(
                    workflow_id=params.get("workflow_path", tool_name),
                    agent_id=params.get("role", "gorgon"),
                    content=str(result.get("output", result)),
                    memory_type=MemoryType(self.config.result_memory_type),
                    confidence=self.config.result_confidence,
                    tags=self.config.gorgon_tags,
                )

            return result

        except Exception as e:
            logger.error("Tool execution failed: %s - %s", tool_name, e)
            return {"error": str(e)}

    # --- Tool handlers ---

    async def _tool_execute_workflow(
        self, params: dict[str, Any]
    ) -> dict[str, Any]:
        """Execute a workflow from a YAML file."""
        from test_ai.workflow.loader import load_workflow

        workflow_path = params.get("workflow_path", "")
        variables = params.get("variables", {})
        dry_run = params.get("dry_run", False)

        config = load_workflow(workflow_path)

        # Inject identity context if available
        if self.identity_store:
            identity_ctx = self.identity_store.get_identity_context()
            if identity_ctx:
                variables["_identity_context"] = identity_ctx

        self._executor.dry_run = dry_run
        result = self._executor.execute(config, variables=variables)

        return {
            "success": result.success,
            "output": {
                step_id: {
                    "status": step_result.status.value,
                    "output": step_result.output,
                }
                for step_id, step_result in result.step_results.items()
            },
            "duration_ms": result.duration_ms,
        }

    async def _tool_list_workflows(
        self, params: dict[str, Any]
    ) -> dict[str, Any]:
        """List available workflow files."""
        from pathlib import Path

        workflows_dir = Path("workflows")
        if not workflows_dir.exists():
            return {"workflows": []}

        workflows = []
        for f in sorted(workflows_dir.rglob("*.yaml")):
            workflows.append(str(f))
        for f in sorted(workflows_dir.rglob("*.yml")):
            workflows.append(str(f))

        return {"workflows": workflows}

    async def _tool_agent_delegate(
        self, params: dict[str, Any]
    ) -> dict[str, Any]:
        """Delegate a task to a specific agent role."""
        role = params.get("role", "builder")
        task = params.get("task", "")
        context = params.get("context")

        # Build a single-step workflow for delegation
        from test_ai.workflow.loader import StepConfig, WorkflowConfig

        step = StepConfig(
            id=f"delegate-{role}",
            type="claude_code",
            params={
                "prompt": task,
                "role": role,
                "use_memory": True,
            },
        )

        workflow = WorkflowConfig(
            id=f"animus-delegate-{role}",
            name=f"Animus delegation to {role}",
            steps=[step],
        )

        variables = {}
        if context:
            variables["context"] = context

        # Inject identity context
        if self.identity_store:
            identity_ctx = self.identity_store.get_identity_context()
            if identity_ctx:
                variables["_identity_context"] = identity_ctx

        result = self._executor.execute(workflow, variables=variables)
        step_output = result.step_results.get(f"delegate-{role}")

        return {
            "success": result.success,
            "role": role,
            "output": step_output.output if step_output else None,
        }
