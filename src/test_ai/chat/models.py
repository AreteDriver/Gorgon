"""Chat data models."""

from __future__ import annotations

import json
from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class ChatMode(str, Enum):
    """Chat operation mode."""

    ASSISTANT = "assistant"  # General assistance
    SELF_IMPROVE = "self_improve"  # Gorgon self-improvement


class MessageRole(str, Enum):
    """Message author role."""

    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class ChatMessage(BaseModel):
    """A chat message."""

    id: str
    session_id: str
    role: MessageRole
    content: str
    agent: str | None = None
    job_id: str | None = None
    token_count: int | None = None
    created_at: datetime = Field(default_factory=datetime.now)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def from_db_row(cls, row: dict) -> ChatMessage:
        """Create from database row."""
        metadata = row.get("metadata")
        if metadata and isinstance(metadata, str):
            metadata = json.loads(metadata)
        return cls(
            id=row["id"],
            session_id=row["session_id"],
            role=MessageRole(row["role"]),
            content=row["content"],
            agent=row.get("agent"),
            job_id=row.get("job_id"),
            token_count=row.get("token_count"),
            created_at=datetime.fromisoformat(row["created_at"])
            if isinstance(row["created_at"], str)
            else row["created_at"],
            metadata=metadata or {},
        )


class ChatSession(BaseModel):
    """A chat session."""

    id: str
    title: str = "New Chat"
    project_path: str | None = None
    mode: ChatMode = ChatMode.ASSISTANT
    status: str = "active"
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    metadata: dict[str, Any] = Field(default_factory=dict)
    messages: list[ChatMessage] = Field(default_factory=list)

    @classmethod
    def from_db_row(cls, row: dict) -> ChatSession:
        """Create from database row."""
        metadata = row.get("metadata")
        if metadata and isinstance(metadata, str):
            metadata = json.loads(metadata)

        created_at = row.get("created_at")
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at)

        updated_at = row.get("updated_at")
        if isinstance(updated_at, str):
            updated_at = datetime.fromisoformat(updated_at)

        return cls(
            id=row["id"],
            title=row.get("title", "New Chat"),
            project_path=row.get("project_path"),
            mode=ChatMode(row.get("mode", "assistant")),
            status=row.get("status", "active"),
            created_at=created_at or datetime.now(),
            updated_at=updated_at or datetime.now(),
            metadata=metadata or {},
        )


# API Request/Response models


class CreateSessionRequest(BaseModel):
    """Request to create a new chat session."""

    title: str | None = None
    project_path: str | None = None
    mode: ChatMode = ChatMode.ASSISTANT


class SendMessageRequest(BaseModel):
    """Request to send a message."""

    content: str = Field(..., min_length=1, max_length=100000)


class ChatSessionResponse(BaseModel):
    """Chat session response."""

    id: str
    title: str
    project_path: str | None
    mode: ChatMode
    status: str
    created_at: datetime
    updated_at: datetime
    message_count: int = 0


class ChatSessionDetailResponse(ChatSessionResponse):
    """Chat session with messages."""

    messages: list[ChatMessage]


class ChatMessageResponse(BaseModel):
    """Chat message response."""

    id: str
    session_id: str
    role: MessageRole
    content: str
    agent: str | None
    job_id: str | None
    created_at: datetime


class StreamChunk(BaseModel):
    """A streaming response chunk."""

    type: str  # 'text', 'agent', 'job', 'done', 'error'
    content: str | None = None
    agent: str | None = None
    job_id: str | None = None
    error: str | None = None
