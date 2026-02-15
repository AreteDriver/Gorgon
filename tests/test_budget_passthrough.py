"""Tests for TODO 3 — Session Budget Passthrough (Jidoka Pattern).

Tests budget context generation, daily limit enforcement,
prompt injection (executor + supervisor), CLI daily command,
and bot /budget command.
"""

from __future__ import annotations

import asyncio
import os
import shutil
import sys
import tempfile
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, "src")

from test_ai.budget.manager import BudgetConfig, BudgetManager
from test_ai.messaging.base import BotMessage, BotUser, MessagePlatform


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def backend():
    """Create a temp SQLite backend with migration 010 applied."""
    from test_ai.state.backends import SQLiteBackend

    tmpdir = tempfile.mkdtemp()
    try:
        db_path = os.path.join(tmpdir, "test.db")
        b = SQLiteBackend(db_path=db_path)
        migration_path = os.path.join(
            os.path.dirname(__file__), "..", "migrations", "010_task_history.sql"
        )
        sql = open(migration_path).read()
        b.executescript(sql)
        yield b
        b.close()
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


@pytest.fixture
def store(backend):
    """Create a TaskStore with the test backend."""
    from test_ai.db import TaskStore

    return TaskStore(backend)


# =============================================================================
# TestBudgetContext
# =============================================================================


class TestBudgetContext:
    """Tests for BudgetManager.get_budget_context()."""

    def test_returns_formatted_context(self):
        bm = BudgetManager(config=BudgetConfig(total_budget=100000))
        ctx = bm.get_budget_context()
        assert "[Budget Constraint]" in ctx
        assert "100,000" in ctx
        assert "concise" in ctx.lower()

    def test_shows_remaining_after_usage(self):
        bm = BudgetManager(config=BudgetConfig(total_budget=100000))
        bm.record_usage("agent", 40000)
        ctx = bm.get_budget_context()
        assert "60,000" in ctx  # remaining
        assert "100,000" in ctx  # total

    def test_empty_when_unlimited(self):
        bm = BudgetManager(config=BudgetConfig(total_budget=0))
        assert bm.get_budget_context() == ""

    def test_empty_when_negative(self):
        bm = BudgetManager(config=BudgetConfig(total_budget=-1))
        assert bm.get_budget_context() == ""


# =============================================================================
# TestDailyTokenLimit
# =============================================================================


class TestDailyTokenLimit:
    """Tests for daily_token_limit field on BudgetConfig."""

    def test_default_disabled(self):
        config = BudgetConfig()
        assert config.daily_token_limit == 0

    def test_can_set(self):
        config = BudgetConfig(daily_token_limit=50000)
        assert config.daily_token_limit == 50000


# =============================================================================
# TestDailyBudgetCheck
# =============================================================================


class TestDailyBudgetCheck:
    """Tests for daily limit enforcement in _check_budget_exceeded."""

    def _make_executor(self, daily_limit=0):
        """Create a minimal executor with budget_manager."""
        from test_ai.workflow.executor import WorkflowExecutor

        bm = BudgetManager(
            config=BudgetConfig(total_budget=1000000, daily_token_limit=daily_limit)
        )
        executor = WorkflowExecutor.__new__(WorkflowExecutor)
        executor.budget_manager = bm
        executor.dry_run = False
        executor.memory_manager = None
        executor.feedback_engine = None
        executor.emit_callback = None
        return executor

    def _make_step_and_result(self):
        from test_ai.workflow.loader import StepConfig
        from test_ai.workflow.executor_results import ExecutionResult

        step = StepConfig(
            id="step-1",
            type="claude_code",
            params={"estimated_tokens": 100},
        )
        result = ExecutionResult(workflow_name="wf-1")
        return step, result

    def test_daily_limit_blocks_when_exceeded(self, store):
        executor = self._make_executor(daily_limit=5000)
        step, result = self._make_step_and_result()

        # Insert enough daily usage
        today = datetime.now().strftime("%Y-%m-%d")
        store.backend.execute(
            "INSERT INTO budget_log (date, agent_role, task_count, total_tokens, total_cost_usd) "
            "VALUES (?, ?, ?, ?, ?)",
            (today, "builder", 5, 6000, 0.50),
        )

        with patch("test_ai.db.get_task_store", return_value=store):
            exceeded = executor._check_budget_exceeded(step, result)
        assert exceeded is True
        assert "Daily" in result.error

    def test_daily_limit_passes_when_under(self, store):
        executor = self._make_executor(daily_limit=50000)
        step, result = self._make_step_and_result()

        today = datetime.now().strftime("%Y-%m-%d")
        store.backend.execute(
            "INSERT INTO budget_log (date, agent_role, task_count, total_tokens, total_cost_usd) "
            "VALUES (?, ?, ?, ?, ?)",
            (today, "builder", 2, 1000, 0.10),
        )

        with patch("test_ai.db.get_task_store", return_value=store):
            exceeded = executor._check_budget_exceeded(step, result)
        assert exceeded is False

    def test_daily_limit_disabled_when_zero(self):
        executor = self._make_executor(daily_limit=0)
        step, result = self._make_step_and_result()
        exceeded = executor._check_budget_exceeded(step, result)
        assert exceeded is False

    def test_daily_check_error_does_not_crash(self):
        executor = self._make_executor(daily_limit=5000)
        step, result = self._make_step_and_result()

        with patch(
            "test_ai.db.get_task_store", side_effect=RuntimeError("DB unavailable")
        ):
            exceeded = executor._check_budget_exceeded(step, result)
        assert exceeded is False  # Graceful degradation

    def test_daily_sums_across_agents(self, store):
        executor = self._make_executor(daily_limit=10000)
        step, result = self._make_step_and_result()

        today = datetime.now().strftime("%Y-%m-%d")
        store.backend.execute(
            "INSERT INTO budget_log (date, agent_role, task_count, total_tokens, total_cost_usd) "
            "VALUES (?, ?, ?, ?, ?)",
            (today, "builder", 3, 6000, 0.30),
        )
        store.backend.execute(
            "INSERT INTO budget_log (date, agent_role, task_count, total_tokens, total_cost_usd) "
            "VALUES (?, ?, ?, ?, ?)",
            (today, "tester", 2, 5000, 0.20),
        )

        with patch("test_ai.db.get_task_store", return_value=store):
            exceeded = executor._check_budget_exceeded(step, result)
        assert exceeded is True


# =============================================================================
# TestExecutorPromptInjection
# =============================================================================


class TestExecutorPromptInjection:
    """Tests for budget context injection in executor_ai prompts."""

    def test_budget_context_in_executor_prompt(self):
        """Budget context appears in the prompt sent to Claude."""

        class FakeExecutor:
            dry_run = True
            memory_manager = None
            budget_manager = BudgetManager(config=BudgetConfig(total_budget=80000))

        from test_ai.workflow.executor_ai import AIHandlersMixin
        from test_ai.workflow.loader import StepConfig

        obj = FakeExecutor()
        AIHandlersMixin._execute_claude_code = AIHandlersMixin._execute_claude_code

        step = StepConfig(
            id="s1",
            type="claude_code",
            params={"prompt": "Do something", "use_memory": False},
        )
        result = AIHandlersMixin._execute_claude_code(obj, step, {})
        assert "Budget Constraint" in result["prompt"]
        assert "80,000" in result["prompt"]

    def test_no_budget_context_without_manager(self):
        """No budget context when budget_manager is absent."""

        class FakeExecutor:
            dry_run = True
            memory_manager = None
            # No budget_manager attribute

        from test_ai.workflow.executor_ai import AIHandlersMixin
        from test_ai.workflow.loader import StepConfig

        obj = FakeExecutor()
        step = StepConfig(
            id="s1",
            type="claude_code",
            params={"prompt": "Do something", "use_memory": False},
        )
        result = AIHandlersMixin._execute_claude_code(obj, step, {})
        assert "Budget Constraint" not in result["prompt"]

    def test_no_budget_context_when_unlimited(self):
        """No budget context when total_budget is 0."""

        class FakeExecutor:
            dry_run = True
            memory_manager = None
            budget_manager = BudgetManager(config=BudgetConfig(total_budget=0))

        from test_ai.workflow.executor_ai import AIHandlersMixin
        from test_ai.workflow.loader import StepConfig

        obj = FakeExecutor()
        step = StepConfig(
            id="s1",
            type="claude_code",
            params={"prompt": "Do something", "use_memory": False},
        )
        result = AIHandlersMixin._execute_claude_code(obj, step, {})
        assert "Budget Constraint" not in result["prompt"]


# =============================================================================
# TestBudgetDailyCommand
# =============================================================================


class TestBudgetDailyCommand:
    """Tests for 'budget daily' CLI command."""

    def test_daily_shows_table(self, store):
        today = datetime.now().strftime("%Y-%m-%d")
        store.backend.execute(
            "INSERT INTO budget_log (date, agent_role, task_count, total_tokens, total_cost_usd) "
            "VALUES (?, ?, ?, ?, ?)",
            (today, "builder", 5, 12000, 1.20),
        )

        from typer.testing import CliRunner
        from test_ai.cli.commands.budget import budget_app
        import typer

        app = typer.Typer()
        app.add_typer(budget_app)

        runner = CliRunner()
        with patch("test_ai.db.get_task_store", return_value=store):
            result = runner.invoke(app, ["daily"])
        assert result.exit_code == 0
        assert "12,000" in result.output

    def test_daily_empty(self, store):
        from typer.testing import CliRunner
        from test_ai.cli.commands.budget import budget_app
        import typer

        app = typer.Typer()
        app.add_typer(budget_app)

        runner = CliRunner()
        with patch("test_ai.db.get_task_store", return_value=store):
            result = runner.invoke(app, ["daily"])
        assert result.exit_code == 0
        assert "No daily budget data" in result.output

    def test_daily_agent_filter(self, store):
        today = datetime.now().strftime("%Y-%m-%d")
        store.backend.execute(
            "INSERT INTO budget_log (date, agent_role, task_count, total_tokens, total_cost_usd) "
            "VALUES (?, ?, ?, ?, ?)",
            (today, "builder", 3, 8000, 0.80),
        )
        store.backend.execute(
            "INSERT INTO budget_log (date, agent_role, task_count, total_tokens, total_cost_usd) "
            "VALUES (?, ?, ?, ?, ?)",
            (today, "tester", 2, 4000, 0.40),
        )

        from typer.testing import CliRunner
        from test_ai.cli.commands.budget import budget_app
        import typer

        app = typer.Typer()
        app.add_typer(budget_app)

        runner = CliRunner()
        with patch("test_ai.db.get_task_store", return_value=store):
            result = runner.invoke(app, ["daily", "--agent", "builder"])
        assert result.exit_code == 0
        assert "8,000" in result.output

    def test_daily_json_output(self, store):
        today = datetime.now().strftime("%Y-%m-%d")
        store.backend.execute(
            "INSERT INTO budget_log (date, agent_role, task_count, total_tokens, total_cost_usd) "
            "VALUES (?, ?, ?, ?, ?)",
            (today, "builder", 3, 8000, 0.80),
        )

        from typer.testing import CliRunner
        from test_ai.cli.commands.budget import budget_app
        import typer
        import json

        app = typer.Typer()
        app.add_typer(budget_app)

        runner = CliRunner()
        with patch("test_ai.db.get_task_store", return_value=store):
            result = runner.invoke(app, ["daily", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert len(data) == 1
        assert data[0]["total_tokens"] == 8000


# =============================================================================
# TestBotBudgetCommand
# =============================================================================


class TestBotBudgetCommand:
    """Tests for /budget bot command."""

    def _make_message(self):
        user = BotUser(
            id="u1",
            platform=MessagePlatform.TELEGRAM,
            username="testuser",
            is_admin=False,
        )
        return BotMessage(
            id="msg-1",
            platform=MessagePlatform.TELEGRAM,
            user=user,
            content="/budget",
            chat_id="chat-1",
        )

    def _make_handler(self):
        from test_ai.messaging.handler import MessageHandler

        session_mgr = MagicMock()
        return MessageHandler(session_manager=session_mgr)

    def test_budget_command_returns_daily_spend(self, store):
        today = datetime.now().strftime("%Y-%m-%d")
        store.backend.execute(
            "INSERT INTO budget_log (date, agent_role, task_count, total_tokens, total_cost_usd) "
            "VALUES (?, ?, ?, ?, ?)",
            (today, "builder", 5, 15000, 1.50),
        )

        handler = self._make_handler()
        msg = self._make_message()
        with patch("test_ai.db.get_task_store", return_value=store):
            result = asyncio.run(handler.handle_command(msg, "budget", []))
        assert "15,000" in result
        assert "Today" in result

    def test_budget_command_empty_db(self, store):
        handler = self._make_handler()
        msg = self._make_message()
        with patch("test_ai.db.get_task_store", return_value=store):
            result = asyncio.run(handler.handle_command(msg, "budget", []))
        assert "No budget data" in result

    def test_budget_command_error_fallback(self):
        handler = self._make_handler()
        msg = self._make_message()
        with patch("test_ai.db.get_task_store", side_effect=RuntimeError("DB error")):
            result = asyncio.run(handler.handle_command(msg, "budget", []))
        assert "unavailable" in result.lower()

    def test_budget_registered_in_handlers(self):
        handler = self._make_handler()
        msg = self._make_message()
        # handle_command for unknown command returns None
        result = asyncio.run(handler.handle_command(msg, "unknown_cmd_xyz", []))
        assert result is None
        # budget should return something (not None)
        with patch("test_ai.db.get_task_store", side_effect=RuntimeError("DB error")):
            result = asyncio.run(handler.handle_command(msg, "budget", []))
        assert result is not None
