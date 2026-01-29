"""Pydantic models for MCP connectors."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class MCPServerStatus(str, Enum):
    """MCP server connection status."""

    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    ERROR = "error"
    CONNECTING = "connecting"
    NOT_CONFIGURED = "not_configured"


class MCPServerType(str, Enum):
    """MCP server connection type."""

    SSE = "sse"
    STDIO = "stdio"
    WEBSOCKET = "websocket"


class MCPAuthType(str, Enum):
    """MCP authentication type."""

    NONE = "none"
    BEARER = "bearer"
    API_KEY = "api_key"
    OAUTH = "oauth"


class MCPTool(BaseModel):
    """MCP tool definition."""

    name: str
    description: str
    inputSchema: dict = Field(default_factory=dict)


class MCPResource(BaseModel):
    """MCP resource definition."""

    uri: str
    name: str
    mimeType: Optional[str] = None
    description: Optional[str] = None


class MCPServer(BaseModel):
    """MCP server registration."""

    model_config = ConfigDict(use_enum_values=True)

    id: str
    name: str
    url: str
    type: MCPServerType = MCPServerType.SSE
    status: MCPServerStatus = MCPServerStatus.NOT_CONFIGURED
    description: Optional[str] = None
    authType: MCPAuthType = MCPAuthType.NONE
    credentialId: Optional[str] = None
    tools: list[MCPTool] = Field(default_factory=list)
    resources: list[MCPResource] = Field(default_factory=list)
    lastConnected: Optional[datetime] = None
    error: Optional[str] = None
    createdAt: datetime = Field(default_factory=datetime.now)
    updatedAt: datetime = Field(default_factory=datetime.now)


class MCPServerCreateInput(BaseModel):
    """Input for creating an MCP server registration."""

    model_config = ConfigDict(use_enum_values=True)

    name: str
    url: str
    type: MCPServerType = MCPServerType.SSE
    authType: MCPAuthType = MCPAuthType.NONE
    credentialId: Optional[str] = None
    description: Optional[str] = None


class MCPServerUpdateInput(BaseModel):
    """Input for updating an MCP server registration."""

    model_config = ConfigDict(use_enum_values=True)

    name: Optional[str] = None
    url: Optional[str] = None
    type: Optional[MCPServerType] = None
    authType: Optional[MCPAuthType] = None
    credentialId: Optional[str] = None
    description: Optional[str] = None


class CredentialType(str, Enum):
    """Credential type."""

    BEARER = "bearer"
    API_KEY = "api_key"
    OAUTH = "oauth"


class Credential(BaseModel):
    """Stored credential (value never exposed)."""

    model_config = ConfigDict(use_enum_values=True)

    id: str
    name: str
    type: CredentialType
    service: str
    createdAt: datetime = Field(default_factory=datetime.now)
    lastUsed: Optional[datetime] = None


class CredentialCreateInput(BaseModel):
    """Input for creating a credential."""

    model_config = ConfigDict(use_enum_values=True)

    name: str
    type: CredentialType
    service: str
    value: str  # The actual credential value (will be encrypted)


class MCPConnectionTestResult(BaseModel):
    """Result of testing an MCP connection."""

    success: bool
    error: Optional[str] = None
    tools: list[MCPTool] = Field(default_factory=list)
    resources: list[MCPResource] = Field(default_factory=list)
