"""MCP server and credential endpoints."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Header

from test_ai import api_state as state
from test_ai.api_errors import AUTH_RESPONSES, CRUD_RESPONSES, bad_request, not_found
from test_ai.api_routes.auth import verify_auth
from test_ai.mcp.models import (
    CredentialCreateInput,
    MCPServerCreateInput,
    MCPServerUpdateInput,
)

router = APIRouter()


# ---------------------------------------------------------------------------
# MCP Servers
# ---------------------------------------------------------------------------


@router.get("/mcp/servers", responses=AUTH_RESPONSES)
def list_mcp_servers(authorization: Optional[str] = Header(None)):
    """List all registered MCP servers."""
    verify_auth(authorization)
    servers = state.mcp_manager.list_servers()
    return [s.model_dump(mode="json") for s in servers]


@router.get("/mcp/servers/{server_id}", responses=CRUD_RESPONSES)
def get_mcp_server(server_id: str, authorization: Optional[str] = Header(None)):
    """Get a specific MCP server by ID."""
    verify_auth(authorization)
    server = state.mcp_manager.get_server(server_id)
    if not server:
        raise not_found("MCP Server", server_id)
    return server.model_dump(mode="json")


@router.post("/mcp/servers", responses=CRUD_RESPONSES)
def create_mcp_server(
    data: MCPServerCreateInput, authorization: Optional[str] = Header(None)
):
    """Register a new MCP server."""
    verify_auth(authorization)
    try:
        server = state.mcp_manager.create_server(data)
        return server.model_dump(mode="json")
    except ValueError as e:
        raise bad_request(str(e))


@router.put("/mcp/servers/{server_id}", responses=CRUD_RESPONSES)
def update_mcp_server(
    server_id: str,
    data: MCPServerUpdateInput,
    authorization: Optional[str] = Header(None),
):
    """Update an MCP server registration."""
    verify_auth(authorization)
    server = state.mcp_manager.update_server(server_id, data)
    if not server:
        raise not_found("MCP Server", server_id)
    return server.model_dump(mode="json")


@router.delete("/mcp/servers/{server_id}", responses=CRUD_RESPONSES)
def delete_mcp_server(server_id: str, authorization: Optional[str] = Header(None)):
    """Delete an MCP server registration."""
    verify_auth(authorization)
    if state.mcp_manager.delete_server(server_id):
        return {"status": "success"}
    raise not_found("MCP Server", server_id)


@router.post("/mcp/servers/{server_id}/test", responses=CRUD_RESPONSES)
def test_mcp_connection(server_id: str, authorization: Optional[str] = Header(None)):
    """Test connection to an MCP server."""
    verify_auth(authorization)
    server = state.mcp_manager.get_server(server_id)
    if not server:
        raise not_found("MCP Server", server_id)

    result = state.mcp_manager.test_connection(server_id)
    return {
        "success": result.success,
        "error": result.error,
        "tools": [t.model_dump() for t in result.tools],
        "resources": [r.model_dump() for r in result.resources],
    }


@router.get("/mcp/servers/{server_id}/tools", responses=CRUD_RESPONSES)
def get_mcp_server_tools(server_id: str, authorization: Optional[str] = Header(None)):
    """Get tools available on an MCP server."""
    verify_auth(authorization)
    server = state.mcp_manager.get_server(server_id)
    if not server:
        raise not_found("MCP Server", server_id)
    return [t.model_dump() for t in server.tools]


# ---------------------------------------------------------------------------
# Credentials
# ---------------------------------------------------------------------------


@router.get("/credentials", responses=AUTH_RESPONSES)
def list_credentials(authorization: Optional[str] = Header(None)):
    """List all credentials (values not exposed)."""
    verify_auth(authorization)
    credentials = state.mcp_manager.list_credentials()
    return [c.model_dump(mode="json") for c in credentials]


@router.get("/credentials/{credential_id}", responses=CRUD_RESPONSES)
def get_credential(credential_id: str, authorization: Optional[str] = Header(None)):
    """Get a specific credential by ID (value not exposed)."""
    verify_auth(authorization)
    credential = state.mcp_manager.get_credential(credential_id)
    if not credential:
        raise not_found("Credential", credential_id)
    return credential.model_dump(mode="json")


@router.post("/credentials", responses=CRUD_RESPONSES)
def create_credential(
    data: CredentialCreateInput, authorization: Optional[str] = Header(None)
):
    """Create a new credential (encrypted at rest)."""
    verify_auth(authorization)
    try:
        credential = state.mcp_manager.create_credential(data)
        return credential.model_dump(mode="json")
    except ValueError as e:
        raise bad_request(str(e))


@router.delete("/credentials/{credential_id}", responses=CRUD_RESPONSES)
def delete_credential(credential_id: str, authorization: Optional[str] = Header(None)):
    """Delete a credential."""
    verify_auth(authorization)
    if state.mcp_manager.delete_credential(credential_id):
        return {"status": "success"}
    raise not_found("Credential", credential_id)
