"""Execution manager for workflow execution tracking."""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from .models import (
    Execution,
    ExecutionLog,
    ExecutionMetrics,
    ExecutionStatus,
    LogLevel,
    PaginatedResponse,
)

if TYPE_CHECKING:
    from test_ai.state.backends import DatabaseBackend

logger = logging.getLogger(__name__)


class ExecutionManager:
    """Manages workflow execution lifecycle and persistence."""

    def __init__(self, backend: "DatabaseBackend"):
        """Initialize the execution manager.

        Args:
            backend: Database backend for persistence
        """
        self.backend = backend

    def create_execution(
        self,
        workflow_id: str,
        workflow_name: str,
        variables: dict | None = None,
    ) -> Execution:
        """Create a new execution record.

        Args:
            workflow_id: ID of the workflow being executed
            workflow_name: Human-readable workflow name
            variables: Input variables for the execution

        Returns:
            Created Execution instance
        """
        execution_id = str(uuid.uuid4())
        now = datetime.now()
        variables = variables or {}

        execution = Execution(
            id=execution_id,
            workflow_id=workflow_id,
            workflow_name=workflow_name,
            status=ExecutionStatus.PENDING,
            variables=variables,
            created_at=now,
        )

        with self.backend.transaction():
            self.backend.execute(
                """
                INSERT INTO executions (
                    id, workflow_id, workflow_name, status, variables, created_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    execution_id,
                    workflow_id,
                    workflow_name,
                    ExecutionStatus.PENDING.value,
                    json.dumps(variables),
                    now.isoformat(),
                ),
            )

            # Create metrics record
            self.backend.execute(
                """
                INSERT INTO execution_metrics (execution_id)
                VALUES (?)
                """,
                (execution_id,),
            )

        logger.info(f"Created execution {execution_id} for workflow {workflow_id}")
        return execution

    def get_execution(self, execution_id: str) -> Execution | None:
        """Get an execution by ID.

        Args:
            execution_id: Execution ID

        Returns:
            Execution instance or None if not found
        """
        row = self.backend.fetchone(
            "SELECT * FROM executions WHERE id = ?",
            (execution_id,),
        )

        if not row:
            return None

        return self._row_to_execution(row)

    def list_executions(
        self,
        page: int = 1,
        page_size: int = 20,
        status: ExecutionStatus | None = None,
        workflow_id: str | None = None,
    ) -> PaginatedResponse[Execution]:
        """List executions with pagination and filtering.

        Args:
            page: Page number (1-indexed)
            page_size: Number of items per page
            status: Filter by status
            workflow_id: Filter by workflow ID

        Returns:
            Paginated response with executions
        """
        # Build query conditions
        conditions = []
        params: list = []

        if status:
            conditions.append("status = ?")
            params.append(status.value)

        if workflow_id:
            conditions.append("workflow_id = ?")
            params.append(workflow_id)

        where_clause = " AND ".join(conditions) if conditions else "1=1"

        # Get total count
        count_row = self.backend.fetchone(
            f"SELECT COUNT(*) as count FROM executions WHERE {where_clause}",
            tuple(params),
        )
        total = count_row["count"] if count_row else 0

        # Get paginated results
        offset = (page - 1) * page_size
        rows = self.backend.fetchall(
            f"""
            SELECT * FROM executions
            WHERE {where_clause}
            ORDER BY created_at DESC
            LIMIT ? OFFSET ?
            """,
            tuple(params + [page_size, offset]),
        )

        executions = [self._row_to_execution(row) for row in rows]

        return PaginatedResponse.create(
            data=executions,
            total=total,
            page=page,
            page_size=page_size,
        )

    def start_execution(self, execution_id: str) -> Execution | None:
        """Mark an execution as started.

        Args:
            execution_id: Execution ID

        Returns:
            Updated Execution or None if not found
        """
        now = datetime.now()

        with self.backend.transaction():
            self.backend.execute(
                """
                UPDATE executions
                SET status = ?, started_at = ?
                WHERE id = ? AND status = ?
                """,
                (
                    ExecutionStatus.RUNNING.value,
                    now.isoformat(),
                    execution_id,
                    ExecutionStatus.PENDING.value,
                ),
            )

        self.add_log(execution_id, LogLevel.INFO, "Execution started")
        return self.get_execution(execution_id)

    def pause_execution(self, execution_id: str) -> Execution | None:
        """Pause a running execution.

        Args:
            execution_id: Execution ID

        Returns:
            Updated Execution or None if not found/not pausable
        """
        with self.backend.transaction():
            self.backend.execute(
                """
                UPDATE executions
                SET status = ?
                WHERE id = ? AND status = ?
                """,
                (
                    ExecutionStatus.PAUSED.value,
                    execution_id,
                    ExecutionStatus.RUNNING.value,
                ),
            )

        self.add_log(execution_id, LogLevel.INFO, "Execution paused")
        return self.get_execution(execution_id)

    def resume_execution(self, execution_id: str) -> Execution | None:
        """Resume a paused execution.

        Args:
            execution_id: Execution ID

        Returns:
            Updated Execution or None if not found/not resumable
        """
        with self.backend.transaction():
            self.backend.execute(
                """
                UPDATE executions
                SET status = ?
                WHERE id = ? AND status = ?
                """,
                (
                    ExecutionStatus.RUNNING.value,
                    execution_id,
                    ExecutionStatus.PAUSED.value,
                ),
            )

        self.add_log(execution_id, LogLevel.INFO, "Execution resumed")
        return self.get_execution(execution_id)

    def cancel_execution(self, execution_id: str) -> bool:
        """Cancel an execution.

        Args:
            execution_id: Execution ID

        Returns:
            True if cancelled, False otherwise
        """
        now = datetime.now()

        with self.backend.transaction():
            cursor = self.backend.execute(
                """
                UPDATE executions
                SET status = ?, completed_at = ?
                WHERE id = ? AND status IN (?, ?, ?)
                """,
                (
                    ExecutionStatus.CANCELLED.value,
                    now.isoformat(),
                    execution_id,
                    ExecutionStatus.PENDING.value,
                    ExecutionStatus.RUNNING.value,
                    ExecutionStatus.PAUSED.value,
                ),
            )

        if cursor.rowcount > 0:
            self.add_log(execution_id, LogLevel.INFO, "Execution cancelled")
            return True
        return False

    def complete_execution(
        self,
        execution_id: str,
        error: str | None = None,
    ) -> Execution | None:
        """Mark an execution as completed or failed.

        Args:
            execution_id: Execution ID
            error: Error message if failed

        Returns:
            Updated Execution or None if not found
        """
        now = datetime.now()
        status = ExecutionStatus.FAILED if error else ExecutionStatus.COMPLETED

        with self.backend.transaction():
            self.backend.execute(
                """
                UPDATE executions
                SET status = ?, completed_at = ?, error = ?, progress = 100
                WHERE id = ?
                """,
                (
                    status.value,
                    now.isoformat(),
                    error,
                    execution_id,
                ),
            )

        if error:
            self.add_log(execution_id, LogLevel.ERROR, f"Execution failed: {error}")
        else:
            self.add_log(execution_id, LogLevel.INFO, "Execution completed")

        return self.get_execution(execution_id)

    def update_progress(
        self,
        execution_id: str,
        progress: int,
        current_step: str | None = None,
    ) -> None:
        """Update execution progress.

        Args:
            execution_id: Execution ID
            progress: Progress percentage (0-100)
            current_step: Current step ID
        """
        with self.backend.transaction():
            if current_step:
                self.backend.execute(
                    """
                    UPDATE executions
                    SET progress = ?, current_step = ?
                    WHERE id = ?
                    """,
                    (progress, current_step, execution_id),
                )
            else:
                self.backend.execute(
                    """
                    UPDATE executions
                    SET progress = ?
                    WHERE id = ?
                    """,
                    (progress, execution_id),
                )

    def update_variables(self, execution_id: str, variables: dict) -> None:
        """Update execution variables (runtime state).

        Args:
            execution_id: Execution ID
            variables: Updated variables dict
        """
        with self.backend.transaction():
            self.backend.execute(
                """
                UPDATE executions
                SET variables = ?
                WHERE id = ?
                """,
                (json.dumps(variables), execution_id),
            )

    def save_checkpoint(self, execution_id: str, checkpoint_id: str) -> None:
        """Save a checkpoint for resume capability.

        Args:
            execution_id: Execution ID
            checkpoint_id: Checkpoint identifier
        """
        with self.backend.transaction():
            self.backend.execute(
                """
                UPDATE executions
                SET checkpoint_id = ?
                WHERE id = ?
                """,
                (checkpoint_id, execution_id),
            )

        self.add_log(
            execution_id,
            LogLevel.DEBUG,
            f"Checkpoint saved: {checkpoint_id}",
        )

    def add_log(
        self,
        execution_id: str,
        level: LogLevel,
        message: str,
        step_id: str | None = None,
        metadata: dict | None = None,
    ) -> None:
        """Add a log entry to an execution.

        Args:
            execution_id: Execution ID
            level: Log level
            message: Log message
            step_id: Associated step ID
            metadata: Additional metadata
        """
        now = datetime.now()

        with self.backend.transaction():
            self.backend.execute(
                """
                INSERT INTO execution_logs (
                    execution_id, timestamp, level, message, step_id, metadata
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    execution_id,
                    now.isoformat(),
                    level.value,
                    message,
                    step_id,
                    json.dumps(metadata) if metadata else None,
                ),
            )

    def get_logs(
        self,
        execution_id: str,
        limit: int = 100,
        level: LogLevel | None = None,
    ) -> list[ExecutionLog]:
        """Get logs for an execution.

        Args:
            execution_id: Execution ID
            limit: Maximum number of logs to return
            level: Filter by log level

        Returns:
            List of ExecutionLog entries
        """
        if level:
            rows = self.backend.fetchall(
                """
                SELECT * FROM execution_logs
                WHERE execution_id = ? AND level = ?
                ORDER BY timestamp DESC
                LIMIT ?
                """,
                (execution_id, level.value, limit),
            )
        else:
            rows = self.backend.fetchall(
                """
                SELECT * FROM execution_logs
                WHERE execution_id = ?
                ORDER BY timestamp DESC
                LIMIT ?
                """,
                (execution_id, limit),
            )

        return [self._row_to_log(row) for row in rows]

    def update_metrics(
        self,
        execution_id: str,
        tokens: int = 0,
        cost_cents: int = 0,
        duration_ms: int = 0,
        steps_completed: int = 0,
        steps_failed: int = 0,
    ) -> None:
        """Update execution metrics (incremental).

        Args:
            execution_id: Execution ID
            tokens: Tokens to add
            cost_cents: Cost in cents to add
            duration_ms: Duration in ms to add
            steps_completed: Steps completed to add
            steps_failed: Steps failed to add
        """
        with self.backend.transaction():
            self.backend.execute(
                """
                UPDATE execution_metrics
                SET total_tokens = total_tokens + ?,
                    total_cost_cents = total_cost_cents + ?,
                    duration_ms = duration_ms + ?,
                    steps_completed = steps_completed + ?,
                    steps_failed = steps_failed + ?
                WHERE execution_id = ?
                """,
                (
                    tokens,
                    cost_cents,
                    duration_ms,
                    steps_completed,
                    steps_failed,
                    execution_id,
                ),
            )

    def get_metrics(self, execution_id: str) -> ExecutionMetrics | None:
        """Get metrics for an execution.

        Args:
            execution_id: Execution ID

        Returns:
            ExecutionMetrics or None if not found
        """
        row = self.backend.fetchone(
            "SELECT * FROM execution_metrics WHERE execution_id = ?",
            (execution_id,),
        )

        if not row:
            return None

        return ExecutionMetrics(
            execution_id=row["execution_id"],
            total_tokens=row["total_tokens"],
            total_cost_cents=row["total_cost_cents"],
            duration_ms=row["duration_ms"],
            steps_completed=row["steps_completed"],
            steps_failed=row["steps_failed"],
        )

    def delete_execution(self, execution_id: str) -> bool:
        """Delete an execution and its associated data.

        Args:
            execution_id: Execution ID

        Returns:
            True if deleted, False if not found
        """
        with self.backend.transaction():
            # Cascade delete handles logs and metrics
            cursor = self.backend.execute(
                "DELETE FROM executions WHERE id = ?",
                (execution_id,),
            )

        return cursor.rowcount > 0

    def cleanup_old_executions(self, max_age_hours: int = 168) -> int:
        """Delete old completed/failed/cancelled executions.

        Args:
            max_age_hours: Maximum age in hours (default 7 days)

        Returns:
            Number of deleted executions
        """
        with self.backend.transaction():
            cursor = self.backend.execute(
                """
                DELETE FROM executions
                WHERE status IN (?, ?, ?)
                AND datetime(completed_at) < datetime('now', ? || ' hours')
                """,
                (
                    ExecutionStatus.COMPLETED.value,
                    ExecutionStatus.FAILED.value,
                    ExecutionStatus.CANCELLED.value,
                    f"-{max_age_hours}",
                ),
            )

        count = cursor.rowcount
        if count > 0:
            logger.info(f"Cleaned up {count} old executions")
        return count

    def _row_to_execution(self, row: dict) -> Execution:
        """Convert a database row to an Execution instance."""
        variables = {}
        if row.get("variables"):
            try:
                variables = json.loads(row["variables"])
            except (json.JSONDecodeError, TypeError):
                pass

        return Execution(
            id=row["id"],
            workflow_id=row["workflow_id"],
            workflow_name=row["workflow_name"],
            status=ExecutionStatus(row["status"]),
            started_at=self._parse_datetime(row.get("started_at")),
            completed_at=self._parse_datetime(row.get("completed_at")),
            current_step=row.get("current_step"),
            progress=row.get("progress", 0),
            checkpoint_id=row.get("checkpoint_id"),
            variables=variables,
            error=row.get("error"),
            created_at=self._parse_datetime(row.get("created_at")) or datetime.now(),
        )

    def _row_to_log(self, row: dict) -> ExecutionLog:
        """Convert a database row to an ExecutionLog instance."""
        metadata = None
        if row.get("metadata"):
            try:
                metadata = json.loads(row["metadata"])
            except (json.JSONDecodeError, TypeError):
                pass

        return ExecutionLog(
            id=row.get("id"),
            execution_id=row["execution_id"],
            timestamp=self._parse_datetime(row.get("timestamp")) or datetime.now(),
            level=LogLevel(row["level"]),
            message=row["message"],
            step_id=row.get("step_id"),
            metadata=metadata,
        )

    def _parse_datetime(self, value: str | None) -> datetime | None:
        """Parse datetime from ISO format string."""
        if not value:
            return None
        try:
            return datetime.fromisoformat(value)
        except (ValueError, TypeError):
            return None
