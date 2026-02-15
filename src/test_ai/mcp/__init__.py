"""MCP (Model Context Protocol) connector management.

Provides registration, storage, connection testing, and tool execution
for MCP servers.
"""

from .client import HAS_MCP_SDK, MCPClientError, call_mcp_tool
from .manager import MCPConnectorManager
from .models import (
    MCPServer,
    MCPServerCreateInput,
    MCPServerStatus,
    MCPTool,
    MCPResource,
    Credential,
    CredentialCreateInput,
)

__all__ = [
    "HAS_MCP_SDK",
    "MCPClientError",
    "call_mcp_tool",
    "MCPConnectorManager",
    "MCPServer",
    "MCPServerCreateInput",
    "MCPServerStatus",
    "MCPTool",
    "MCPResource",
    "Credential",
    "CredentialCreateInput",
]
