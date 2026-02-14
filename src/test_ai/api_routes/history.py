"""Task history endpoints — list tasks, agent stats, budget rollups."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Header, Query

from test_ai import api_state as state
from test_ai.api_errors import AUTH_RESPONSES, not_found
from test_ai.api_routes.auth import verify_auth

router = APIRouter()


@router.get("/history", responses=AUTH_RESPONSES)
def list_history(
    status: Optional[str] = Query(None, description="Filter by status"),
    agent_role: Optional[str] = Query(None, description="Filter by agent role"),
    limit: int = Query(20, ge=1, le=500, description="Max results"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    authorization: Optional[str] = Header(None),
):
    """List task history with optional filters."""
    verify_auth(authorization)

    tasks = state.task_store.query_tasks(
        status=status, agent_role=agent_role, limit=limit, offset=offset
    )
    return tasks


@router.get("/history/summary", responses=AUTH_RESPONSES)
def get_history_summary(authorization: Optional[str] = Header(None)):
    """Get overall summary stats."""
    verify_auth(authorization)

    return state.task_store.get_summary()


@router.get("/history/stats", responses=AUTH_RESPONSES)
def get_history_stats(
    agent: Optional[str] = Query(None, description="Filter by agent role"),
    authorization: Optional[str] = Header(None),
):
    """Get agent performance statistics."""
    verify_auth(authorization)

    return state.task_store.get_agent_stats(agent_role=agent)


@router.get("/history/budget", responses=AUTH_RESPONSES)
def get_history_budget(
    days: int = Query(7, ge=1, le=365, description="Number of days"),
    agent: Optional[str] = Query(None, description="Filter by agent role"),
    authorization: Optional[str] = Header(None),
):
    """Get daily budget rollups."""
    verify_auth(authorization)

    return state.task_store.get_daily_budget(days=days, agent_role=agent)


@router.get("/history/{task_id}", responses=AUTH_RESPONSES)
def get_history_task(
    task_id: int,
    authorization: Optional[str] = Header(None),
):
    """Get a single task by ID."""
    verify_auth(authorization)

    task = state.task_store.get_task(task_id)
    if not task:
        raise not_found("Task", str(task_id))
    return task
