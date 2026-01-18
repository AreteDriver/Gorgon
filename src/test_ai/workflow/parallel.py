"""Parallel execution support for workflows."""

from __future__ import annotations

import asyncio
import concurrent.futures
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable


class ParallelStrategy(Enum):
    """Strategy for parallel execution."""

    THREADING = "threading"
    ASYNCIO = "asyncio"
    PROCESS = "process"


@dataclass
class ParallelTask:
    """A task to be executed in parallel."""

    id: str
    step_id: str
    handler: Callable
    args: tuple = ()
    kwargs: dict = field(default_factory=dict)
    dependencies: list[str] = field(default_factory=list)
    result: Any = None
    error: Exception | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None

    @property
    def duration_ms(self) -> int | None:
        """Get execution duration in milliseconds."""
        if self.started_at and self.completed_at:
            return int((self.completed_at - self.started_at).total_seconds() * 1000)
        return None

    @property
    def is_ready(self) -> bool:
        """Check if all dependencies are satisfied."""
        return len(self.dependencies) == 0


@dataclass
class ParallelResult:
    """Result of parallel execution."""

    tasks: dict[str, ParallelTask] = field(default_factory=dict)
    successful: list[str] = field(default_factory=list)
    failed: list[str] = field(default_factory=list)
    total_duration_ms: int = 0

    @property
    def all_succeeded(self) -> bool:
        """Check if all tasks succeeded."""
        return len(self.failed) == 0

    def get_result(self, task_id: str) -> Any:
        """Get result for a specific task."""
        if task_id in self.tasks:
            return self.tasks[task_id].result
        return None

    def get_error(self, task_id: str) -> Exception | None:
        """Get error for a specific task."""
        if task_id in self.tasks:
            return self.tasks[task_id].error
        return None


class ParallelExecutor:
    """Executes workflow steps in parallel when possible.

    Analyzes step dependencies and executes independent steps
    concurrently for improved performance.
    """

    def __init__(
        self,
        strategy: ParallelStrategy = ParallelStrategy.THREADING,
        max_workers: int = 4,
        timeout: float = 300.0,
    ):
        """Initialize parallel executor.

        Args:
            strategy: Execution strategy to use
            max_workers: Maximum concurrent workers
            timeout: Default timeout in seconds
        """
        self.strategy = strategy
        self.max_workers = max_workers
        self.timeout = timeout

    def analyze_dependencies(
        self,
        steps: list[dict],
    ) -> dict[str, list[str]]:
        """Analyze step dependencies to find parallelizable groups.

        Args:
            steps: List of step configurations

        Returns:
            Dictionary mapping step_id to list of dependency step_ids
        """
        dependencies: dict[str, list[str]] = {}

        for step in steps:
            step_id = step.get("id", "")
            deps = step.get("depends_on", [])

            if isinstance(deps, str):
                deps = [deps]

            dependencies[step_id] = deps

        return dependencies

    def find_parallel_groups(
        self,
        dependencies: dict[str, list[str]],
    ) -> list[set[str]]:
        """Find groups of steps that can execute in parallel.

        Args:
            dependencies: Step dependency mapping

        Returns:
            List of sets, each containing step_ids that can run together
        """
        groups: list[set[str]] = []
        completed: set[str] = set()
        remaining = set(dependencies.keys())

        while remaining:
            # Find all steps whose dependencies are satisfied
            ready = {
                step_id
                for step_id in remaining
                if all(dep in completed for dep in dependencies[step_id])
            }

            if not ready:
                # Circular dependency or missing dependency
                raise ValueError(
                    f"Cannot resolve dependencies for: {remaining}. "
                    "Check for circular dependencies."
                )

            groups.append(ready)
            completed.update(ready)
            remaining -= ready

        return groups

    def execute_parallel(
        self,
        tasks: list[ParallelTask],
        on_complete: Callable[[str, Any], None] | None = None,
        on_error: Callable[[str, Exception], None] | None = None,
    ) -> ParallelResult:
        """Execute tasks in parallel.

        Args:
            tasks: List of tasks to execute
            on_complete: Callback when task completes
            on_error: Callback when task fails

        Returns:
            ParallelResult with all task outcomes
        """
        if self.strategy == ParallelStrategy.THREADING:
            return self._execute_threaded(tasks, on_complete, on_error)
        elif self.strategy == ParallelStrategy.ASYNCIO:
            return asyncio.run(self._execute_async(tasks, on_complete, on_error))
        elif self.strategy == ParallelStrategy.PROCESS:
            return self._execute_multiprocess(tasks, on_complete, on_error)
        else:
            raise ValueError(f"Unknown strategy: {self.strategy}")

    def _execute_threaded(
        self,
        tasks: list[ParallelTask],
        on_complete: Callable[[str, Any], None] | None,
        on_error: Callable[[str, Exception], None] | None,
    ) -> ParallelResult:
        """Execute tasks using thread pool."""
        result = ParallelResult()
        start_time = datetime.utcnow()

        # Build dependency graph
        pending = {t.id: t for t in tasks}
        completed_ids: set[str] = set()

        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            while pending:
                # Find ready tasks
                ready = [
                    task for task in pending.values()
                    if all(dep in completed_ids for dep in task.dependencies)
                ]

                if not ready:
                    if pending:
                        raise ValueError("Deadlock: no tasks ready but some pending")
                    break

                # Submit ready tasks
                futures = {}
                for task in ready:
                    task.started_at = datetime.utcnow()
                    future = executor.submit(task.handler, *task.args, **task.kwargs)
                    futures[future] = task

                # Wait for completion
                for future in concurrent.futures.as_completed(futures, timeout=self.timeout):
                    task = futures[future]
                    task.completed_at = datetime.utcnow()

                    try:
                        task.result = future.result()
                        result.successful.append(task.id)
                        if on_complete:
                            on_complete(task.id, task.result)
                    except Exception as e:
                        task.error = e
                        result.failed.append(task.id)
                        if on_error:
                            on_error(task.id, e)

                    result.tasks[task.id] = task
                    completed_ids.add(task.id)
                    del pending[task.id]

        result.total_duration_ms = int(
            (datetime.utcnow() - start_time).total_seconds() * 1000
        )
        return result

    async def _execute_async(
        self,
        tasks: list[ParallelTask],
        on_complete: Callable[[str, Any], None] | None,
        on_error: Callable[[str, Exception], None] | None,
    ) -> ParallelResult:
        """Execute tasks using asyncio."""
        result = ParallelResult()
        start_time = datetime.utcnow()

        pending = {t.id: t for t in tasks}
        completed_ids: set[str] = set()

        while pending:
            ready = [
                task for task in pending.values()
                if all(dep in completed_ids for dep in task.dependencies)
            ]

            if not ready:
                if pending:
                    raise ValueError("Deadlock: no tasks ready but some pending")
                break

            # Create async tasks
            async def run_task(task: ParallelTask) -> tuple[str, Any, Exception | None]:
                task.started_at = datetime.utcnow()
                try:
                    if asyncio.iscoroutinefunction(task.handler):
                        res = await task.handler(*task.args, **task.kwargs)
                    else:
                        # Run sync function in executor
                        loop = asyncio.get_event_loop()
                        res = await loop.run_in_executor(
                            None, lambda: task.handler(*task.args, **task.kwargs)
                        )
                    task.completed_at = datetime.utcnow()
                    return task.id, res, None
                except Exception as e:
                    task.completed_at = datetime.utcnow()
                    return task.id, None, e

            # Run all ready tasks concurrently
            semaphore = asyncio.Semaphore(self.max_workers)

            async def bounded_run(task: ParallelTask):
                async with semaphore:
                    return await asyncio.wait_for(run_task(task), timeout=self.timeout)

            results_list = await asyncio.gather(
                *[bounded_run(task) for task in ready],
                return_exceptions=True,
            )

            for item in results_list:
                if isinstance(item, Exception):
                    # Timeout or other gather error
                    continue

                task_id, res, err = item
                task = pending[task_id]
                task.result = res
                task.error = err

                if err:
                    result.failed.append(task_id)
                    if on_error:
                        on_error(task_id, err)
                else:
                    result.successful.append(task_id)
                    if on_complete:
                        on_complete(task_id, res)

                result.tasks[task_id] = task
                completed_ids.add(task_id)
                del pending[task_id]

        result.total_duration_ms = int(
            (datetime.utcnow() - start_time).total_seconds() * 1000
        )
        return result

    def _execute_multiprocess(
        self,
        tasks: list[ParallelTask],
        on_complete: Callable[[str, Any], None] | None,
        on_error: Callable[[str, Exception], None] | None,
    ) -> ParallelResult:
        """Execute tasks using process pool.

        Note: Handlers must be picklable for multiprocessing.
        """
        result = ParallelResult()
        start_time = datetime.utcnow()

        pending = {t.id: t for t in tasks}
        completed_ids: set[str] = set()

        with concurrent.futures.ProcessPoolExecutor(max_workers=self.max_workers) as executor:
            while pending:
                ready = [
                    task for task in pending.values()
                    if all(dep in completed_ids for dep in task.dependencies)
                ]

                if not ready:
                    if pending:
                        raise ValueError("Deadlock: no tasks ready but some pending")
                    break

                futures = {}
                for task in ready:
                    task.started_at = datetime.utcnow()
                    future = executor.submit(task.handler, *task.args, **task.kwargs)
                    futures[future] = task

                for future in concurrent.futures.as_completed(futures, timeout=self.timeout):
                    task = futures[future]
                    task.completed_at = datetime.utcnow()

                    try:
                        task.result = future.result()
                        result.successful.append(task.id)
                        if on_complete:
                            on_complete(task.id, task.result)
                    except Exception as e:
                        task.error = e
                        result.failed.append(task.id)
                        if on_error:
                            on_error(task.id, e)

                    result.tasks[task.id] = task
                    completed_ids.add(task.id)
                    del pending[task.id]

        result.total_duration_ms = int(
            (datetime.utcnow() - start_time).total_seconds() * 1000
        )
        return result


def execute_steps_parallel(
    steps: list[dict],
    handler: Callable[[dict], Any],
    max_workers: int = 4,
    strategy: ParallelStrategy = ParallelStrategy.THREADING,
) -> ParallelResult:
    """Convenience function to execute workflow steps in parallel.

    Args:
        steps: List of step configurations with 'id' and optional 'depends_on'
        handler: Function to execute each step
        max_workers: Maximum concurrent workers
        strategy: Execution strategy

    Returns:
        ParallelResult with outcomes

    Example:
        >>> steps = [
        ...     {"id": "fetch", "url": "..."},
        ...     {"id": "parse", "depends_on": ["fetch"]},
        ...     {"id": "validate", "depends_on": ["fetch"]},
        ...     {"id": "save", "depends_on": ["parse", "validate"]},
        ... ]
        >>> result = execute_steps_parallel(steps, execute_step)
    """
    executor = ParallelExecutor(strategy=strategy, max_workers=max_workers)

    # Analyze dependencies
    deps = executor.analyze_dependencies(steps)

    # Create tasks
    tasks = [
        ParallelTask(
            id=step["id"],
            step_id=step["id"],
            handler=handler,
            args=(step,),
            dependencies=deps.get(step["id"], []),
        )
        for step in steps
    ]

    return executor.execute_parallel(tasks)
