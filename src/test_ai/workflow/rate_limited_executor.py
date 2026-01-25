"""Rate-limited parallel execution for AI workflows.

Provides per-provider rate limiting to prevent 429 errors during
parallel agent execution.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable

from .parallel import (
    ParallelExecutor,
    ParallelStrategy,
    ParallelTask,
    ParallelResult,
)

logger = logging.getLogger(__name__)


@dataclass
class ProviderRateLimits:
    """Rate limit configuration for providers.

    Default limits are conservative to prevent 429 errors:
    - Anthropic: ~60 RPM = 5 concurrent safe with headroom
    - OpenAI: ~90 RPM = 8 concurrent safe with headroom
    """

    anthropic: int = 5
    openai: int = 8
    default: int = 10


class RateLimitedParallelExecutor(ParallelExecutor):
    """Parallel executor with per-provider rate limiting.

    Extends ParallelExecutor to add semaphore-based rate limiting
    for AI provider calls, preventing 429 rate limit errors during
    parallel execution.

    Usage:
        executor = RateLimitedParallelExecutor(
            strategy=ParallelStrategy.ASYNCIO,
            max_workers=4,
            provider_limits={"anthropic": 3, "openai": 5},
        )

        # Tasks with provider metadata
        tasks = [
            ParallelTask(id="t1", handler=agent_fn, kwargs={"provider": "anthropic"}),
            ParallelTask(id="t2", handler=agent_fn, kwargs={"provider": "openai"}),
        ]

        result = await executor.execute_parallel_rate_limited(tasks)
    """

    def __init__(
        self,
        strategy: ParallelStrategy = ParallelStrategy.ASYNCIO,
        max_workers: int = 4,
        timeout: float = 300.0,
        provider_limits: dict[str, int] | None = None,
    ):
        """Initialize rate-limited parallel executor.

        Args:
            strategy: Execution strategy (asyncio recommended for rate limiting)
            max_workers: Maximum concurrent workers overall
            timeout: Default timeout in seconds
            provider_limits: Dict of provider name -> max concurrent calls
        """
        super().__init__(strategy, max_workers, timeout)

        # Set up per-provider limits
        defaults = ProviderRateLimits()
        limits = provider_limits or {}

        self._provider_limits = {
            "anthropic": limits.get("anthropic", defaults.anthropic),
            "openai": limits.get("openai", defaults.openai),
            "default": limits.get("default", defaults.default),
        }

        # Semaphores are created lazily in async context
        self._semaphores: dict[str, asyncio.Semaphore] | None = None

    def _get_semaphores(self) -> dict[str, asyncio.Semaphore]:
        """Get or create semaphores for rate limiting.

        Must be called from async context.
        """
        if self._semaphores is None:
            self._semaphores = {
                name: asyncio.Semaphore(limit)
                for name, limit in self._provider_limits.items()
            }
        return self._semaphores

    def _get_provider_for_task(self, task: ParallelTask) -> str:
        """Determine which provider a task uses.

        Checks task kwargs and handler for provider hints.
        """
        # Check explicit provider in kwargs
        provider = task.kwargs.get("provider")
        if provider:
            return provider.lower()

        # Check step_type hint
        step_type = task.kwargs.get("step_type", "").lower()
        if "claude" in step_type or "anthropic" in step_type:
            return "anthropic"
        if "openai" in step_type or "gpt" in step_type:
            return "openai"

        # Check handler name or docstring for hints
        handler_name = getattr(task.handler, "__name__", "").lower()
        if "claude" in handler_name or "anthropic" in handler_name:
            return "anthropic"
        if "openai" in handler_name or "gpt" in handler_name:
            return "openai"

        return "default"

    async def _run_task_with_rate_limit(
        self,
        task: ParallelTask,
        semaphores: dict[str, asyncio.Semaphore],
    ) -> tuple[str, Any, Exception | None]:
        """Execute a task with rate limiting based on its provider.

        Args:
            task: Task to execute
            semaphores: Provider semaphores for rate limiting

        Returns:
            Tuple of (task_id, result, error)
        """
        provider = self._get_provider_for_task(task)
        semaphore = semaphores.get(provider, semaphores["default"])

        task.started_at = datetime.now(timezone.utc)
        logger.debug(
            f"Task {task.id} waiting for {provider} semaphore "
            f"(available: {semaphore._value})"  # noqa: SLF001
        )

        async with semaphore:
            logger.debug(f"Task {task.id} acquired {provider} semaphore")
            try:
                if asyncio.iscoroutinefunction(task.handler):
                    result = await task.handler(*task.args, **task.kwargs)
                else:
                    loop = asyncio.get_event_loop()
                    result = await loop.run_in_executor(
                        None, lambda: task.handler(*task.args, **task.kwargs)
                    )
                task.completed_at = datetime.now(timezone.utc)
                return task.id, result, None
            except asyncio.CancelledError:
                task.completed_at = datetime.now(timezone.utc)
                raise
            except Exception as e:
                task.completed_at = datetime.now(timezone.utc)
                logger.warning(f"Task {task.id} failed: {e}")
                return task.id, None, e

    async def execute_parallel_rate_limited(
        self,
        tasks: list[ParallelTask],
        on_complete: Callable[[str, Any], None] | None = None,
        on_error: Callable[[str, Exception], None] | None = None,
        fail_fast: bool = False,
    ) -> ParallelResult:
        """Execute tasks in parallel with per-provider rate limiting.

        This is the primary method for rate-limited parallel execution.
        Uses asyncio for best rate limiting control.

        Args:
            tasks: List of tasks to execute
            on_complete: Callback when task completes successfully
            on_error: Callback when task fails
            fail_fast: If True, cancel remaining tasks on first failure

        Returns:
            ParallelResult with all task outcomes
        """
        result = ParallelResult()
        start_time = datetime.now(timezone.utc)

        pending = {t.id: t for t in tasks}
        completed_ids: set[str] = set()
        should_cancel = False
        semaphores = self._get_semaphores()

        # Overall concurrency limit
        overall_semaphore = asyncio.Semaphore(self.max_workers)

        async def bounded_run(task: ParallelTask):
            async with overall_semaphore:
                return await asyncio.wait_for(
                    self._run_task_with_rate_limit(task, semaphores),
                    timeout=self.timeout,
                )

        while pending and not should_cancel:
            # Get tasks whose dependencies are satisfied
            ready = self._get_ready_tasks(pending, completed_ids)
            if not ready:
                if pending:
                    raise ValueError("Deadlock: no tasks ready but some pending")
                break

            # Create async tasks for ready parallel tasks
            async_tasks = {
                asyncio.create_task(bounded_run(task)): task for task in ready
            }

            for coro in asyncio.as_completed(async_tasks.keys()):
                try:
                    item = await coro
                except (asyncio.CancelledError, asyncio.TimeoutError, Exception) as e:
                    # Find the task that failed
                    for async_task, ptask in async_tasks.items():
                        if async_task.done() and ptask.id not in completed_ids:
                            ptask.error = e if isinstance(e, Exception) else None
                            result.failed.append(ptask.id)
                            result.tasks[ptask.id] = ptask
                            completed_ids.add(ptask.id)
                            if ptask.id in pending:
                                del pending[ptask.id]
                            if on_error and isinstance(e, Exception):
                                on_error(ptask.id, e)
                    continue

                if item is None:
                    continue

                task_id, res, err = item
                task = pending.get(task_id)
                if not task:
                    continue

                task.result = res
                task.error = err
                result.tasks[task_id] = task

                if err:
                    result.failed.append(task_id)
                    if on_error:
                        on_error(task_id, err)
                    if fail_fast:
                        should_cancel = True
                        # Cancel remaining async tasks
                        for async_task, ptask in async_tasks.items():
                            if ptask.id != task_id and not async_task.done():
                                async_task.cancel()
                                result.cancelled.append(ptask.id)
                                result.tasks[ptask.id] = ptask
                                if ptask.id in pending:
                                    del pending[ptask.id]
                else:
                    result.successful.append(task_id)
                    if on_complete:
                        on_complete(task_id, res)

                completed_ids.add(task_id)
                if task_id in pending:
                    del pending[task_id]

                if should_cancel:
                    break

        # Mark remaining pending tasks as cancelled
        if should_cancel and pending:
            self._cancel_pending_tasks(pending, result)

        result.total_duration_ms = int(
            (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
        )
        return result

    def execute_parallel(
        self,
        tasks: list[ParallelTask],
        on_complete: Callable[[str, Any], None] | None = None,
        on_error: Callable[[str, Exception], None] | None = None,
        fail_fast: bool = False,
    ) -> ParallelResult:
        """Execute tasks in parallel with rate limiting.

        Overrides parent to use rate-limited execution for asyncio strategy.
        Falls back to parent implementation for other strategies.

        Args:
            tasks: List of tasks to execute
            on_complete: Callback when task completes
            on_error: Callback when task fails
            fail_fast: If True, cancel remaining tasks on first failure

        Returns:
            ParallelResult with all task outcomes
        """
        if self.strategy == ParallelStrategy.ASYNCIO:
            return asyncio.run(
                self.execute_parallel_rate_limited(
                    tasks, on_complete, on_error, fail_fast
                )
            )
        # For threading/process, fall back to parent (no async rate limiting)
        logger.warning(
            "Rate limiting is only effective with ASYNCIO strategy. "
            f"Current strategy: {self.strategy}"
        )
        return super().execute_parallel(tasks, on_complete, on_error, fail_fast)

    def get_provider_stats(self) -> dict[str, dict]:
        """Get current stats for provider rate limits.

        Returns:
            Dict with provider name -> {limit, available (if in async context)}
        """
        stats = {}
        for provider, limit in self._provider_limits.items():
            stats[provider] = {"limit": limit}
            if self._semaphores and provider in self._semaphores:
                stats[provider]["available"] = self._semaphores[provider]._value  # noqa: SLF001
        return stats


def create_rate_limited_executor(
    max_workers: int = 4,
    anthropic_concurrent: int = 5,
    openai_concurrent: int = 8,
    timeout: float = 300.0,
) -> RateLimitedParallelExecutor:
    """Create a rate-limited executor with common defaults.

    Args:
        max_workers: Maximum overall concurrent tasks
        anthropic_concurrent: Max concurrent Anthropic API calls
        openai_concurrent: Max concurrent OpenAI API calls
        timeout: Default timeout in seconds

    Returns:
        Configured RateLimitedParallelExecutor
    """
    return RateLimitedParallelExecutor(
        strategy=ParallelStrategy.ASYNCIO,
        max_workers=max_workers,
        timeout=timeout,
        provider_limits={
            "anthropic": anthropic_concurrent,
            "openai": openai_concurrent,
        },
    )
