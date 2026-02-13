"""Prompt template endpoints."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Header

from test_ai import api_state as state
from test_ai.api_errors import AUTH_RESPONSES, CRUD_RESPONSES, internal_error, not_found
from test_ai.api_routes.auth import verify_auth
from test_ai.prompts import PromptTemplate

router = APIRouter()


@router.get("/prompts", responses=AUTH_RESPONSES)
def list_prompts(authorization: Optional[str] = Header(None)):
    """List all prompt templates."""
    verify_auth(authorization)
    return state.prompt_manager.list_templates()


@router.get("/prompts/{template_id}", responses=CRUD_RESPONSES)
def get_prompt(template_id: str, authorization: Optional[str] = Header(None)):
    """Get a specific prompt template."""
    verify_auth(authorization)
    template = state.prompt_manager.load_template(template_id)

    if not template:
        raise not_found("Template", template_id)

    return template


@router.post("/prompts", responses=CRUD_RESPONSES)
def create_prompt(
    template: PromptTemplate, authorization: Optional[str] = Header(None)
):
    """Create a new prompt template."""
    verify_auth(authorization)

    if state.prompt_manager.save_template(template):
        return {"status": "success", "template_id": template.id}

    raise internal_error("Failed to save template")


@router.delete("/prompts/{template_id}", responses=CRUD_RESPONSES)
def delete_prompt(template_id: str, authorization: Optional[str] = Header(None)):
    """Delete a prompt template."""
    verify_auth(authorization)

    if state.prompt_manager.delete_template(template_id):
        return {"status": "success"}

    raise not_found("Template", template_id)
