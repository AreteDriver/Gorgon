"""Shared mutable state for API modules.

All module-level globals live here so that both the lifespan (in api.py)
and route modules can reference the same objects.  Route modules should
import this *module* (not individual names) so they see lifespan updates:

    from test_ai import api_state as state
    state.schedule_manager.list_schedules()
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Optional

from slowapi import Limiter
from slowapi.util import get_remote_address

if TYPE_CHECKING:
    from test_ai.budget import PersistentBudgetManager
    from test_ai.db import TaskStore
    from test_ai.executions import ExecutionManager
    from test_ai.jobs import JobManager
    from test_ai.mcp import MCPConnectorManager
    from test_ai.scheduler import ScheduleManager
    from test_ai.settings import SettingsManager
    from test_ai.webhooks import WebhookManager
    from test_ai.webhooks.webhook_delivery import WebhookDeliveryManager
    from test_ai.websocket import Broadcaster, ConnectionManager
    from test_ai.workflow import WorkflowVersionManager

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Rate limiter
# ---------------------------------------------------------------------------
limiter = Limiter(key_func=get_remote_address)

# ---------------------------------------------------------------------------
# Eagerly-initialized components (created at import time)
# ---------------------------------------------------------------------------
from test_ai.api_clients import OpenAIClient  # noqa: E402
from test_ai.config import get_settings  # noqa: E402
from test_ai.orchestrator.workflow_engine_adapter import WorkflowEngineAdapter  # noqa: E402
from test_ai.prompts import PromptTemplateManager  # noqa: E402
from test_ai.workflow.executor import WorkflowExecutor  # noqa: E402

workflow_engine = WorkflowEngineAdapter()
prompt_manager = PromptTemplateManager()
openai_client = OpenAIClient()
yaml_workflow_executor = WorkflowExecutor()
YAML_WORKFLOWS_DIR = get_settings().base_dir / "workflows"

# ---------------------------------------------------------------------------
# Managers (initialized in lifespan)
# ---------------------------------------------------------------------------
schedule_manager: Optional[ScheduleManager] = None
webhook_manager: Optional[WebhookManager] = None
delivery_manager: Optional[WebhookDeliveryManager] = None
job_manager: Optional[JobManager] = None
version_manager: Optional[WorkflowVersionManager] = None
execution_manager: Optional[ExecutionManager] = None
mcp_manager: Optional[MCPConnectorManager] = None
settings_manager: Optional[SettingsManager] = None
budget_manager: Optional[PersistentBudgetManager] = None
task_store: Optional[TaskStore] = None

# ---------------------------------------------------------------------------
# WebSocket components (initialized in lifespan)
# ---------------------------------------------------------------------------
ws_manager: Optional[ConnectionManager] = None
ws_broadcaster: Optional[Broadcaster] = None

# ---------------------------------------------------------------------------
# Application health state
# ---------------------------------------------------------------------------
_app_state: dict = {
    "ready": False,
    "shutting_down": False,
    "start_time": None,
    "active_requests": 0,
}
_state_lock = asyncio.Lock()


async def increment_active_requests() -> None:
    """Increment active request counter."""
    async with _state_lock:
        _app_state["active_requests"] += 1


async def decrement_active_requests() -> None:
    """Decrement active request counter."""
    async with _state_lock:
        _app_state["active_requests"] -= 1
