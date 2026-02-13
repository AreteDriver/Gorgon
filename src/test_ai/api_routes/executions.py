"""Execution management endpoints."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Header

from test_ai import api_state as state
from test_ai.api_errors import (
    AUTH_RESPONSES,
    CRUD_RESPONSES,
    bad_request,
    internal_error,
    not_found,
)
from test_ai.api_routes.auth import verify_auth

router = APIRouter()


@router.get("/executions", responses=AUTH_RESPONSES)
def list_executions(
    page: int = 1,
    page_size: int = 20,
    status: Optional[str] = None,
    workflow_id: Optional[str] = None,
    authorization: Optional[str] = Header(None),
):
    """List workflow executions with pagination."""
    verify_auth(authorization)

    from test_ai.executions import ExecutionStatus

    status_filter = None
    if status:
        try:
            status_filter = ExecutionStatus(status)
        except ValueError:
            raise bad_request(
                f"Invalid status: {status}",
                {"valid_statuses": [s.value for s in ExecutionStatus]},
            )

    result = state.execution_manager.list_executions(
        page=page,
        page_size=page_size,
        status=status_filter,
        workflow_id=workflow_id,
    )
    return {
        "data": [e.model_dump(mode="json") for e in result.data],
        "total": result.total,
        "page": result.page,
        "page_size": result.page_size,
        "total_pages": result.total_pages,
    }


@router.get("/executions/{execution_id}", responses=CRUD_RESPONSES)
def get_execution(execution_id: str, authorization: Optional[str] = Header(None)):
    """Get a specific execution by ID."""
    verify_auth(authorization)

    execution = state.execution_manager.get_execution(execution_id)
    if not execution:
        raise not_found("Execution", execution_id)

    execution.logs = state.execution_manager.get_logs(execution_id, limit=50)
    execution.metrics = state.execution_manager.get_metrics(execution_id)

    return execution.model_dump(mode="json")


@router.get("/executions/{execution_id}/logs", responses=CRUD_RESPONSES)
def get_execution_logs(
    execution_id: str,
    limit: int = 100,
    level: Optional[str] = None,
    authorization: Optional[str] = Header(None),
):
    """Get logs for an execution."""
    verify_auth(authorization)

    from test_ai.executions import LogLevel

    execution = state.execution_manager.get_execution(execution_id)
    if not execution:
        raise not_found("Execution", execution_id)

    level_filter = None
    if level:
        try:
            level_filter = LogLevel(level)
        except ValueError:
            raise bad_request(
                f"Invalid level: {level}",
                {"valid_levels": [lvl.value for lvl in LogLevel]},
            )

    logs = state.execution_manager.get_logs(
        execution_id, limit=limit, level=level_filter
    )
    return [log.model_dump(mode="json") for log in logs]


@router.post("/executions/{execution_id}/pause", responses=CRUD_RESPONSES)
def pause_execution(execution_id: str, authorization: Optional[str] = Header(None)):
    """Pause a running execution."""
    verify_auth(authorization)

    execution = state.execution_manager.get_execution(execution_id)
    if not execution:
        raise not_found("Execution", execution_id)

    from test_ai.executions import ExecutionStatus

    if execution.status != ExecutionStatus.RUNNING:
        raise bad_request(
            f"Cannot pause execution in {execution.status.value} status",
            {"execution_id": execution_id, "current_status": execution.status.value},
        )

    updated = state.execution_manager.pause_execution(execution_id)
    return {
        "status": "success",
        "execution_id": execution_id,
        "execution_status": updated.status.value if updated else "unknown",
    }


@router.post("/executions/{execution_id}/resume", responses=CRUD_RESPONSES)
def resume_execution(execution_id: str, authorization: Optional[str] = Header(None)):
    """Resume a paused execution."""
    verify_auth(authorization)

    execution = state.execution_manager.get_execution(execution_id)
    if not execution:
        raise not_found("Execution", execution_id)

    from test_ai.executions import ExecutionStatus

    if execution.status != ExecutionStatus.PAUSED:
        raise bad_request(
            f"Cannot resume execution in {execution.status.value} status",
            {"execution_id": execution_id, "current_status": execution.status.value},
        )

    updated = state.execution_manager.resume_execution(execution_id)
    return {
        "status": "success",
        "execution_id": execution_id,
        "execution_status": updated.status.value if updated else "unknown",
    }


@router.post("/executions/{execution_id}/cancel", responses=CRUD_RESPONSES)
def cancel_execution(execution_id: str, authorization: Optional[str] = Header(None)):
    """Cancel a running or paused execution."""
    verify_auth(authorization)

    execution = state.execution_manager.get_execution(execution_id)
    if not execution:
        raise not_found("Execution", execution_id)

    if state.execution_manager.cancel_execution(execution_id):
        return {"status": "success", "message": "Execution cancelled"}

    raise bad_request(
        f"Cannot cancel execution in {execution.status.value} status",
        {"execution_id": execution_id, "current_status": execution.status.value},
    )


@router.delete("/executions/{execution_id}", responses=CRUD_RESPONSES)
def delete_execution(execution_id: str, authorization: Optional[str] = Header(None)):
    """Delete an execution (must be completed/failed/cancelled)."""
    verify_auth(authorization)

    execution = state.execution_manager.get_execution(execution_id)
    if not execution:
        raise not_found("Execution", execution_id)

    from test_ai.executions import ExecutionStatus

    if execution.status in (
        ExecutionStatus.PENDING,
        ExecutionStatus.RUNNING,
        ExecutionStatus.PAUSED,
    ):
        raise bad_request(
            f"Cannot delete execution in {execution.status.value} status",
            {"execution_id": execution_id, "current_status": execution.status.value},
        )

    if state.execution_manager.delete_execution(execution_id):
        return {"status": "success"}

    raise internal_error("Failed to delete execution")


@router.post("/executions/cleanup")
def cleanup_executions(
    max_age_hours: int = 168, authorization: Optional[str] = Header(None)
):
    """Remove old completed/failed/cancelled executions (default 7 days)."""
    verify_auth(authorization)
    deleted = state.execution_manager.cleanup_old_executions(max_age_hours)
    return {"status": "success", "deleted": deleted}
