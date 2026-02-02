"""Tests for chat module."""

from __future__ import annotations

import pytest
from datetime import datetime

from test_ai.chat.models import (
    ChatMessage,
    ChatSession,
    ChatMode,
    MessageRole,
    CreateSessionRequest,
    SendMessageRequest,
    ChatSessionResponse,
    StreamChunk,
)


class TestChatModels:
    """Tests for chat data models."""

    def test_chat_mode_enum(self):
        """Test ChatMode enum values."""
        assert ChatMode.ASSISTANT == "assistant"
        assert ChatMode.SELF_IMPROVE == "self_improve"

    def test_message_role_enum(self):
        """Test MessageRole enum values."""
        assert MessageRole.USER == "user"
        assert MessageRole.ASSISTANT == "assistant"
        assert MessageRole.SYSTEM == "system"

    def test_chat_message_creation(self):
        """Test ChatMessage model creation."""
        msg = ChatMessage(
            id="msg-123",
            session_id="sess-456",
            role=MessageRole.USER,
            content="Hello, world!",
        )
        assert msg.id == "msg-123"
        assert msg.session_id == "sess-456"
        assert msg.role == MessageRole.USER
        assert msg.content == "Hello, world!"
        assert msg.agent is None
        assert msg.job_id is None
        assert msg.metadata == {}

    def test_chat_message_with_agent(self):
        """Test ChatMessage with agent attribution."""
        msg = ChatMessage(
            id="msg-123",
            session_id="sess-456",
            role=MessageRole.ASSISTANT,
            content="I'll help you with that.",
            agent="planner",
            token_count=42,
        )
        assert msg.agent == "planner"
        assert msg.token_count == 42

    def test_chat_message_from_db_row(self):
        """Test ChatMessage.from_db_row()."""
        row = {
            "id": "msg-abc",
            "session_id": "sess-xyz",
            "role": "user",
            "content": "Test message",
            "agent": None,
            "job_id": None,
            "token_count": 10,
            "created_at": "2026-01-15T10:30:00",
            "metadata": '{"key": "value"}',
        }
        msg = ChatMessage.from_db_row(row)
        assert msg.id == "msg-abc"
        assert msg.role == MessageRole.USER
        assert msg.metadata == {"key": "value"}
        assert msg.created_at == datetime(2026, 1, 15, 10, 30, 0)

    def test_chat_message_from_db_row_no_metadata(self):
        """Test ChatMessage.from_db_row() with no metadata."""
        row = {
            "id": "msg-abc",
            "session_id": "sess-xyz",
            "role": "assistant",
            "content": "Response",
            "created_at": datetime(2026, 1, 15, 10, 30, 0),
            "metadata": None,
        }
        msg = ChatMessage.from_db_row(row)
        assert msg.metadata == {}

    def test_chat_session_creation(self):
        """Test ChatSession model creation."""
        session = ChatSession(
            id="sess-123",
            title="Test Session",
            mode=ChatMode.ASSISTANT,
        )
        assert session.id == "sess-123"
        assert session.title == "Test Session"
        assert session.mode == ChatMode.ASSISTANT
        assert session.status == "active"
        assert session.messages == []

    def test_chat_session_with_project_path(self):
        """Test ChatSession with project path."""
        session = ChatSession(
            id="sess-123",
            title="Project Chat",
            project_path="/home/user/project",
            mode=ChatMode.SELF_IMPROVE,
        )
        assert session.project_path == "/home/user/project"
        assert session.mode == ChatMode.SELF_IMPROVE

    def test_chat_session_from_db_row(self):
        """Test ChatSession.from_db_row()."""
        row = {
            "id": "sess-abc",
            "title": "Test Session",
            "project_path": None,
            "mode": "assistant",
            "status": "active",
            "created_at": "2026-01-15T10:00:00",
            "updated_at": "2026-01-15T11:00:00",
            "metadata": '{"version": 1}',
        }
        session = ChatSession.from_db_row(row)
        assert session.id == "sess-abc"
        assert session.mode == ChatMode.ASSISTANT
        assert session.metadata == {"version": 1}

    def test_create_session_request(self):
        """Test CreateSessionRequest model."""
        req = CreateSessionRequest(
            title="My Chat",
            mode=ChatMode.SELF_IMPROVE,
        )
        assert req.title == "My Chat"
        assert req.mode == ChatMode.SELF_IMPROVE
        assert req.project_path is None

    def test_create_session_request_defaults(self):
        """Test CreateSessionRequest default values."""
        req = CreateSessionRequest()
        assert req.title is None
        assert req.mode == ChatMode.ASSISTANT
        assert req.project_path is None

    def test_send_message_request(self):
        """Test SendMessageRequest model."""
        req = SendMessageRequest(content="Hello!")
        assert req.content == "Hello!"

    def test_send_message_request_validation(self):
        """Test SendMessageRequest content validation."""
        # Empty content should fail
        with pytest.raises(ValueError):
            SendMessageRequest(content="")

    def test_chat_session_response(self):
        """Test ChatSessionResponse model."""
        resp = ChatSessionResponse(
            id="sess-123",
            title="Test",
            project_path=None,
            mode=ChatMode.ASSISTANT,
            status="active",
            created_at=datetime.now(),
            updated_at=datetime.now(),
            message_count=5,
        )
        assert resp.message_count == 5

    def test_stream_chunk(self):
        """Test StreamChunk model."""
        # Text chunk
        chunk = StreamChunk(type="text", content="Hello")
        assert chunk.type == "text"
        assert chunk.content == "Hello"

        # Agent chunk
        chunk = StreamChunk(type="agent", agent="planner")
        assert chunk.type == "agent"
        assert chunk.agent == "planner"

        # Error chunk
        chunk = StreamChunk(type="error", error="Something went wrong")
        assert chunk.type == "error"
        assert chunk.error == "Something went wrong"

        # Done chunk
        chunk = StreamChunk(type="done")
        assert chunk.type == "done"


# Note: ChatSessionManager tests require more complex mocking
# of the database backend. Skipping for now - the model tests
# provide good coverage of the data structures.
