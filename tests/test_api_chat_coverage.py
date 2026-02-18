"""Coverage tests for dashboard routes, chat router, and chat session manager.

Targets:
  - src/test_ai/api_routes/dashboard.py
  - src/test_ai/chat/router.py
  - src/test_ai/chat/session_manager.py
"""

from __future__ import annotations

import asyncio
import os
import sys
import tempfile
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from test_ai.chat.models import (
    ChatMode,
    MessageRole,
)
from test_ai.chat.session_manager import ChatSessionManager
from test_ai.state.backends import SQLiteBackend

# The chat __init__.py exports `router` (the APIRouter instance), which shadows
# the module. Use sys.modules to get the actual module.
__import__("test_ai.chat.router")
chat_router_mod = sys.modules["test_ai.chat.router"]


# ============================================================================
# Helpers
# ============================================================================


def _insert(backend: SQLiteBackend, query: str, params: tuple = ()) -> None:
    """Insert data and commit so other threads (TestClient) can see it."""
    backend.execute(query, params)
    backend._get_conn().commit()


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def sqlite_backend():
    """Create a temporary SQLite backend with chat + dashboard tables.

    Uses a shared connection across all threads (overrides thread-local)
    to avoid 'database is locked' errors when TestClient runs async
    endpoints in AnyIO worker threads.
    """
    import sqlite3

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test_chat.db")
        backend = SQLiteBackend(db_path=db_path)

        schema = """
        CREATE TABLE IF NOT EXISTS chat_sessions (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL DEFAULT 'New Chat',
            project_path TEXT,
            mode TEXT NOT NULL DEFAULT 'assistant',
            status TEXT NOT NULL DEFAULT 'active',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            metadata TEXT
        );

        CREATE TABLE IF NOT EXISTS chat_messages (
            id TEXT PRIMARY KEY,
            session_id TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            agent TEXT,
            job_id TEXT,
            token_count INTEGER,
            created_at TEXT NOT NULL,
            metadata TEXT,
            FOREIGN KEY (session_id) REFERENCES chat_sessions(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS chat_session_jobs (
            session_id TEXT NOT NULL,
            job_id TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (session_id, job_id)
        );

        CREATE TABLE IF NOT EXISTS executions (
            id TEXT PRIMARY KEY,
            workflow_id TEXT NOT NULL,
            workflow_name TEXT,
            status TEXT NOT NULL DEFAULT 'pending',
            started_at TEXT,
            completed_at TEXT,
            current_step TEXT,
            progress INTEGER DEFAULT 0,
            checkpoint_id TEXT,
            variables TEXT DEFAULT '{}',
            error TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS execution_metrics (
            execution_id TEXT PRIMARY KEY,
            total_tokens INTEGER DEFAULT 0,
            total_cost_cents INTEGER DEFAULT 0,
            duration_ms INTEGER DEFAULT 0,
            steps_completed INTEGER DEFAULT 0,
            steps_failed INTEGER DEFAULT 0,
            FOREIGN KEY (execution_id) REFERENCES executions(id)
        );
        """
        backend.executescript(schema)

        # Share a single connection across all threads to avoid
        # 'database is locked' when TestClient uses AnyIO worker threads.
        shared_conn = sqlite3.connect(
            str(backend.db_path),
            check_same_thread=False,
            isolation_level=None,  # autocommit
        )
        shared_conn.row_factory = sqlite3.Row
        backend._get_conn = lambda: shared_conn  # type: ignore[assignment]

        yield backend
        shared_conn.close()


# ============================================================================
# ChatSessionManager tests
# ============================================================================


class TestChatSessionManager:
    """Tests for ChatSessionManager CRUD operations."""

    def _make_manager(self, backend: SQLiteBackend) -> ChatSessionManager:
        return ChatSessionManager(backend)

    def test_create_session_defaults(self, sqlite_backend: SQLiteBackend):
        """Test creating a session with default values."""
        mgr = self._make_manager(sqlite_backend)
        session = mgr.create_session()

        assert session.id is not None
        assert session.title == "New Chat"
        assert session.mode == ChatMode.ASSISTANT
        assert session.status == "active"
        assert session.project_path is None
        assert session.metadata == {}

    def test_create_session_with_all_params(self, sqlite_backend: SQLiteBackend):
        """Test creating a session with all parameters."""
        mgr = self._make_manager(sqlite_backend)
        session = mgr.create_session(
            title="My Session",
            project_path="/tmp/project",
            mode=ChatMode.SELF_IMPROVE,
            metadata={"allowed_paths": ["/tmp/extra"]},
        )

        assert session.title == "My Session"
        assert session.project_path == "/tmp/project"
        assert session.mode == ChatMode.SELF_IMPROVE
        assert session.filesystem_enabled is True
        assert session.allowed_paths == ["/tmp/extra"]

    def test_create_session_no_project_path(self, sqlite_backend: SQLiteBackend):
        """Test filesystem_enabled is False when no project_path."""
        mgr = self._make_manager(sqlite_backend)
        session = mgr.create_session(title="No Project")

        assert session.filesystem_enabled is False
        assert session.allowed_paths == []

    def test_get_session(self, sqlite_backend: SQLiteBackend):
        """Test retrieving a session by ID."""
        mgr = self._make_manager(sqlite_backend)
        created = mgr.create_session(title="Find Me")

        found = mgr.get_session(created.id)
        assert found is not None
        assert found.id == created.id
        assert found.title == "Find Me"

    def test_get_session_not_found(self, sqlite_backend: SQLiteBackend):
        """Test retrieving a non-existent session returns None."""
        mgr = self._make_manager(sqlite_backend)
        assert mgr.get_session("nonexistent-id") is None

    def test_get_session_with_messages(self, sqlite_backend: SQLiteBackend):
        """Test getting a session with its messages."""
        mgr = self._make_manager(sqlite_backend)
        session = mgr.create_session(title="With Messages")

        mgr.add_message(session.id, MessageRole.USER, "Hello")
        mgr.add_message(session.id, MessageRole.ASSISTANT, "Hi there")

        result = mgr.get_session_with_messages(session.id)
        assert result is not None
        assert len(result.messages) == 2
        assert result.messages[0].content == "Hello"
        assert result.messages[1].content == "Hi there"

    def test_get_session_with_messages_not_found(self, sqlite_backend: SQLiteBackend):
        """Test getting messages for non-existent session returns None."""
        mgr = self._make_manager(sqlite_backend)
        assert mgr.get_session_with_messages("nope") is None

    def test_list_sessions_no_filter(self, sqlite_backend: SQLiteBackend):
        """Test listing sessions without status filter."""
        mgr = self._make_manager(sqlite_backend)
        mgr.create_session(title="Session 1")
        mgr.create_session(title="Session 2")

        sessions = mgr.list_sessions()
        assert len(sessions) == 2

    def test_list_sessions_with_status_filter(self, sqlite_backend: SQLiteBackend):
        """Test listing sessions with status filter."""
        mgr = self._make_manager(sqlite_backend)
        s1 = mgr.create_session(title="Active Session")
        mgr.create_session(title="Another Active")

        # Archive one
        mgr.update_session(s1.id, status="archived")

        active_sessions = mgr.list_sessions(status="active")
        assert len(active_sessions) == 1
        assert active_sessions[0].title == "Another Active"

    def test_list_sessions_with_limit_offset(self, sqlite_backend: SQLiteBackend):
        """Test listing sessions with limit and offset."""
        mgr = self._make_manager(sqlite_backend)
        for i in range(5):
            mgr.create_session(title=f"Session {i}")

        page = mgr.list_sessions(limit=2, offset=0)
        assert len(page) == 2

        page2 = mgr.list_sessions(limit=2, offset=2)
        assert len(page2) == 2

    def test_update_session_title(self, sqlite_backend: SQLiteBackend):
        """Test updating session title."""
        mgr = self._make_manager(sqlite_backend)
        session = mgr.create_session(title="Old Title")

        updated = mgr.update_session(session.id, title="New Title")
        assert updated is not None
        assert updated.title == "New Title"

    def test_update_session_status(self, sqlite_backend: SQLiteBackend):
        """Test updating session status."""
        mgr = self._make_manager(sqlite_backend)
        session = mgr.create_session(title="Test")

        updated = mgr.update_session(session.id, status="archived")
        assert updated is not None
        assert updated.status == "archived"

    def test_update_session_no_changes(self, sqlite_backend: SQLiteBackend):
        """Test updating session with no changes returns original."""
        mgr = self._make_manager(sqlite_backend)
        session = mgr.create_session(title="Unchanged")

        result = mgr.update_session(session.id)
        assert result is not None
        assert result.title == "Unchanged"

    def test_update_session_not_found(self, sqlite_backend: SQLiteBackend):
        """Test updating a non-existent session returns None."""
        mgr = self._make_manager(sqlite_backend)
        assert mgr.update_session("nope", title="X") is None

    def test_delete_session(self, sqlite_backend: SQLiteBackend):
        """Test deleting a session."""
        mgr = self._make_manager(sqlite_backend)
        session = mgr.create_session(title="Delete Me")

        assert mgr.delete_session(session.id) is True
        assert mgr.get_session(session.id) is None

    def test_delete_session_not_found(self, sqlite_backend: SQLiteBackend):
        """Test deleting a non-existent session returns False."""
        mgr = self._make_manager(sqlite_backend)
        assert mgr.delete_session("nonexistent") is False

    def test_add_message_basic(self, sqlite_backend: SQLiteBackend):
        """Test adding a basic message."""
        mgr = self._make_manager(sqlite_backend)
        session = mgr.create_session(title="Message Test")

        msg = mgr.add_message(session.id, MessageRole.USER, "Hello world")
        assert msg.id is not None
        assert msg.session_id == session.id
        assert msg.role == MessageRole.USER
        assert msg.content == "Hello world"

    def test_add_message_with_all_fields(self, sqlite_backend: SQLiteBackend):
        """Test adding a message with all optional fields."""
        mgr = self._make_manager(sqlite_backend)
        session = mgr.create_session(title="Full Message")

        msg = mgr.add_message(
            session_id=session.id,
            role=MessageRole.ASSISTANT,
            content="Generated response",
            agent="planner",
            job_id="job-123",
            token_count=150,
            metadata={"model": "gpt-4"},
        )
        assert msg.agent == "planner"
        assert msg.job_id == "job-123"
        assert msg.token_count == 150
        assert msg.metadata == {"model": "gpt-4"}

    def test_get_messages_basic(self, sqlite_backend: SQLiteBackend):
        """Test retrieving messages for a session."""
        mgr = self._make_manager(sqlite_backend)
        session = mgr.create_session()

        mgr.add_message(session.id, MessageRole.USER, "First")
        mgr.add_message(session.id, MessageRole.ASSISTANT, "Second")
        mgr.add_message(session.id, MessageRole.USER, "Third")

        messages = mgr.get_messages(session.id)
        assert len(messages) == 3
        assert messages[0].content == "First"
        assert messages[2].content == "Third"

    def test_get_messages_with_limit(self, sqlite_backend: SQLiteBackend):
        """Test retrieving messages with a limit."""
        mgr = self._make_manager(sqlite_backend)
        session = mgr.create_session()

        for i in range(5):
            mgr.add_message(session.id, MessageRole.USER, f"Message {i}")

        messages = mgr.get_messages(session.id, limit=3)
        assert len(messages) == 3

    def test_get_messages_with_before_id(self, sqlite_backend: SQLiteBackend):
        """Test retrieving messages before a specific message."""
        mgr = self._make_manager(sqlite_backend)
        session = mgr.create_session()

        mgr.add_message(session.id, MessageRole.USER, "First")
        mgr.add_message(session.id, MessageRole.USER, "Second")
        msg3 = mgr.add_message(session.id, MessageRole.USER, "Third")

        messages = mgr.get_messages(session.id, before_id=msg3.id)
        # Should get messages before msg3
        assert len(messages) >= 1

    def test_get_messages_before_id_not_found(self, sqlite_backend: SQLiteBackend):
        """Test get_messages with non-existent before_id returns empty."""
        mgr = self._make_manager(sqlite_backend)
        session = mgr.create_session()
        mgr.add_message(session.id, MessageRole.USER, "Hi")

        messages = mgr.get_messages(session.id, before_id="nonexistent")
        assert messages == []

    def test_link_job(self, sqlite_backend: SQLiteBackend):
        """Test linking a job to a session."""
        mgr = self._make_manager(sqlite_backend)
        session = mgr.create_session()

        mgr.link_job(session.id, "job-abc")
        mgr.link_job(session.id, "job-def")

        jobs = mgr.get_session_jobs(session.id)
        assert "job-abc" in jobs
        assert "job-def" in jobs

    def test_link_job_idempotent(self, sqlite_backend: SQLiteBackend):
        """Test that linking the same job twice doesn't duplicate."""
        mgr = self._make_manager(sqlite_backend)
        session = mgr.create_session()

        mgr.link_job(session.id, "job-dup")
        mgr.link_job(session.id, "job-dup")

        jobs = mgr.get_session_jobs(session.id)
        assert jobs.count("job-dup") == 1

    def test_get_message_count(self, sqlite_backend: SQLiteBackend):
        """Test counting messages in a session."""
        mgr = self._make_manager(sqlite_backend)
        session = mgr.create_session()

        assert mgr.get_message_count(session.id) == 0

        mgr.add_message(session.id, MessageRole.USER, "One")
        mgr.add_message(session.id, MessageRole.ASSISTANT, "Two")

        assert mgr.get_message_count(session.id) == 2

    def test_generate_title_from_message(self, sqlite_backend: SQLiteBackend):
        """Test title generation from first user message."""
        mgr = self._make_manager(sqlite_backend)
        session = mgr.create_session()

        mgr.add_message(session.id, MessageRole.USER, "Short message")

        title = mgr.generate_title(session.id)
        assert title == "Short message"

    def test_generate_title_truncation(self, sqlite_backend: SQLiteBackend):
        """Test title generation truncates long messages."""
        mgr = self._make_manager(sqlite_backend)
        session = mgr.create_session()

        long_msg = "A" * 100
        mgr.add_message(session.id, MessageRole.USER, long_msg)

        title = mgr.generate_title(session.id)
        assert len(title) == 53  # 50 chars + "..."
        assert title.endswith("...")

    def test_generate_title_no_messages(self, sqlite_backend: SQLiteBackend):
        """Test title generation with no user messages returns default."""
        mgr = self._make_manager(sqlite_backend)
        session = mgr.create_session()

        title = mgr.generate_title(session.id)
        assert title == "New Chat"

    def test_update_session_title_and_status(self, sqlite_backend: SQLiteBackend):
        """Test updating both title and status simultaneously."""
        mgr = self._make_manager(sqlite_backend)
        session = mgr.create_session(title="Original")

        updated = mgr.update_session(session.id, title="New", status="archived")
        assert updated is not None
        assert updated.title == "New"
        assert updated.status == "archived"


# ============================================================================
# Chat router tests (unit-level, no TestClient needed for some)
# ============================================================================


class TestChatRouterHelpers:
    """Tests for chat router helper functions."""

    def test_get_session_manager_not_initialized(self):
        """Test get_session_manager raises 503 when not initialized."""
        original = chat_router_mod._session_manager
        try:
            chat_router_mod._session_manager = None
            with pytest.raises(HTTPException) as exc_info:
                chat_router_mod.get_session_manager()
            assert exc_info.value.status_code == 503
        finally:
            chat_router_mod._session_manager = original

    def test_get_backend_not_initialized(self):
        """Test get_backend raises 503 when not initialized."""
        original = chat_router_mod._backend
        try:
            chat_router_mod._backend = None
            with pytest.raises(HTTPException) as exc_info:
                chat_router_mod.get_backend()
            assert exc_info.value.status_code == 503
        finally:
            chat_router_mod._backend = original

    def test_init_chat_module(self, sqlite_backend: SQLiteBackend):
        """Test init_chat_module sets up globals correctly."""
        orig_mgr = chat_router_mod._session_manager
        orig_factory = chat_router_mod._supervisor_factory
        orig_backend = chat_router_mod._backend

        try:
            mock_factory = MagicMock()
            chat_router_mod.init_chat_module(sqlite_backend, mock_factory)

            assert chat_router_mod._session_manager is not None
            assert chat_router_mod._supervisor_factory is mock_factory
            assert chat_router_mod._backend is sqlite_backend
        finally:
            chat_router_mod._session_manager = orig_mgr
            chat_router_mod._supervisor_factory = orig_factory
            chat_router_mod._backend = orig_backend

    def test_init_chat_module_no_factory(self, sqlite_backend: SQLiteBackend):
        """Test init_chat_module with no supervisor factory."""
        orig_mgr = chat_router_mod._session_manager
        orig_factory = chat_router_mod._supervisor_factory
        orig_backend = chat_router_mod._backend

        try:
            chat_router_mod.init_chat_module(sqlite_backend)

            assert chat_router_mod._session_manager is not None
            assert chat_router_mod._supervisor_factory is None
            assert chat_router_mod._backend is sqlite_backend
        finally:
            chat_router_mod._session_manager = orig_mgr
            chat_router_mod._supervisor_factory = orig_factory
            chat_router_mod._backend = orig_backend


# ============================================================================
# Chat router API tests (using TestClient)
# ============================================================================


@pytest.fixture
def chat_app(sqlite_backend: SQLiteBackend):
    """Create a FastAPI app with chat router for testing."""
    # Save originals
    orig_mgr = chat_router_mod._session_manager
    orig_factory = chat_router_mod._supervisor_factory
    orig_backend = chat_router_mod._backend

    app = FastAPI()
    app.include_router(chat_router_mod.router)

    chat_router_mod.init_chat_module(sqlite_backend)

    yield app

    # Restore
    chat_router_mod._session_manager = orig_mgr
    chat_router_mod._supervisor_factory = orig_factory
    chat_router_mod._backend = orig_backend


@pytest.fixture
def chat_client(chat_app: FastAPI):
    """Create a test client for the chat app."""
    return TestClient(chat_app)


class TestChatSessionEndpoints:
    """Tests for chat session CRUD endpoints."""

    def test_create_session(self, chat_client: TestClient):
        """Test POST /chat/sessions creates a session."""
        resp = chat_client.post(
            "/chat/sessions",
            json={"title": "Test Session", "mode": "assistant"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["title"] == "Test Session"
        assert data["mode"] == "assistant"
        assert data["status"] == "active"
        assert data["message_count"] == 0

    def test_create_session_with_project_path(self, chat_client: TestClient):
        """Test creating a session with project path enables filesystem."""
        resp = chat_client.post(
            "/chat/sessions",
            json={
                "title": "Project Session",
                "project_path": "/tmp/project",
                "filesystem_enabled": True,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["project_path"] == "/tmp/project"
        assert data["filesystem_enabled"] is True

    def test_create_session_fs_disabled(self, chat_client: TestClient):
        """Test creating session with filesystem_enabled=False."""
        resp = chat_client.post(
            "/chat/sessions",
            json={
                "title": "No FS",
                "project_path": "/tmp/proj",
                "filesystem_enabled": False,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["filesystem_enabled"] is False

    def test_create_session_with_allowed_paths(self, chat_client: TestClient):
        """Test creating session stores allowed_paths in metadata."""
        resp = chat_client.post(
            "/chat/sessions",
            json={
                "title": "With Paths",
                "project_path": "/tmp/project",
                "allowed_paths": ["/tmp/extra1", "/tmp/extra2"],
            },
        )
        assert resp.status_code == 200

    def test_list_sessions(self, chat_client: TestClient):
        """Test GET /chat/sessions lists sessions."""
        chat_client.post("/chat/sessions", json={"title": "S1"})
        chat_client.post("/chat/sessions", json={"title": "S2"})

        resp = chat_client.get("/chat/sessions")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 2

    def test_list_sessions_with_status_filter(self, chat_client: TestClient):
        """Test listing sessions with status query parameter."""
        chat_client.post("/chat/sessions", json={"title": "Active"})

        resp = chat_client.get("/chat/sessions?status=active")
        assert resp.status_code == 200
        data = resp.json()
        assert all(s["status"] == "active" for s in data)

    def test_list_sessions_with_pagination(self, chat_client: TestClient):
        """Test listing sessions with limit and offset."""
        for i in range(5):
            chat_client.post("/chat/sessions", json={"title": f"S{i}"})

        resp = chat_client.get("/chat/sessions?limit=2&offset=0")
        assert resp.status_code == 200
        assert len(resp.json()) == 2

    def test_get_session(self, chat_client: TestClient):
        """Test GET /chat/sessions/{id} retrieves session detail."""
        create_resp = chat_client.post("/chat/sessions", json={"title": "Detail"})
        session_id = create_resp.json()["id"]

        resp = chat_client.get(f"/chat/sessions/{session_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == session_id
        assert data["title"] == "Detail"
        assert "messages" in data

    def test_get_session_not_found(self, chat_client: TestClient):
        """Test GET /chat/sessions/{id} returns 404 for missing session."""
        resp = chat_client.get("/chat/sessions/nonexistent-id")
        assert resp.status_code == 404

    def test_update_session(self, chat_client: TestClient):
        """Test PATCH /chat/sessions/{id} updates session."""
        create_resp = chat_client.post("/chat/sessions", json={"title": "Old"})
        session_id = create_resp.json()["id"]

        resp = chat_client.patch(
            f"/chat/sessions/{session_id}",
            json={"title": "Updated Title"},
        )
        assert resp.status_code == 200
        assert resp.json()["title"] == "Updated Title"

    def test_update_session_status(self, chat_client: TestClient):
        """Test PATCH /chat/sessions/{id} updates status."""
        create_resp = chat_client.post("/chat/sessions", json={"title": "Archivable"})
        session_id = create_resp.json()["id"]

        resp = chat_client.patch(
            f"/chat/sessions/{session_id}",
            json={"status": "archived"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "archived"

    def test_update_session_not_found(self, chat_client: TestClient):
        """Test PATCH returns 404 for non-existent session."""
        resp = chat_client.patch(
            "/chat/sessions/nope",
            json={"title": "X"},
        )
        assert resp.status_code == 404

    def test_delete_session(self, chat_client: TestClient):
        """Test DELETE /chat/sessions/{id} deletes session."""
        create_resp = chat_client.post("/chat/sessions", json={"title": "Delete Me"})
        session_id = create_resp.json()["id"]

        resp = chat_client.delete(f"/chat/sessions/{session_id}")
        assert resp.status_code == 200
        assert resp.json() == {"status": "deleted"}

        # Verify it's gone
        get_resp = chat_client.get(f"/chat/sessions/{session_id}")
        assert get_resp.status_code == 404

    def test_delete_session_not_found(self, chat_client: TestClient):
        """Test DELETE returns 404 for non-existent session."""
        resp = chat_client.delete("/chat/sessions/nonexistent")
        assert resp.status_code == 404


class TestChatMessageEndpoints:
    """Tests for chat message endpoints."""

    def _create_session(self, client: TestClient) -> str:
        resp = client.post("/chat/sessions", json={"title": "Msg Test"})
        return resp.json()["id"]

    def test_send_message_no_supervisor(self, chat_client: TestClient):
        """Test sending a message when no supervisor is configured."""
        session_id = self._create_session(chat_client)

        resp = chat_client.post(
            f"/chat/sessions/{session_id}/messages",
            json={"content": "Hello there"},
        )
        assert resp.status_code == 200
        # SSE response
        body = resp.text
        assert "data:" in body
        assert "not configured" in body or "done" in body

    def test_send_message_session_not_found(self, chat_client: TestClient):
        """Test sending a message to non-existent session returns 404."""
        resp = chat_client.post(
            "/chat/sessions/nonexistent/messages",
            json={"content": "Hello"},
        )
        assert resp.status_code == 404

    def test_send_message_with_supervisor_factory(self, sqlite_backend: SQLiteBackend):
        """Test sending a message with a supervisor factory configured."""
        orig_mgr = chat_router_mod._session_manager
        orig_factory = chat_router_mod._supervisor_factory
        orig_backend = chat_router_mod._backend

        try:
            # Create a mock supervisor that yields chunks
            mock_supervisor = MagicMock()

            async def mock_process_message(**kwargs):
                yield {"type": "text", "content": "Hello from AI", "agent": "planner"}
                yield {"type": "done"}

            mock_supervisor.process_message = mock_process_message

            def factory(mode=None, session=None, backend=None):
                return mock_supervisor

            chat_router_mod.init_chat_module(sqlite_backend, factory)

            app = FastAPI()
            app.include_router(chat_router_mod.router)
            client = TestClient(app)

            # Create a session
            create_resp = client.post("/chat/sessions", json={"title": "AI Chat"})
            session_id = create_resp.json()["id"]

            # Send a message
            resp = client.post(
                f"/chat/sessions/{session_id}/messages",
                json={"content": "Tell me something"},
            )
            assert resp.status_code == 200
            body = resp.text
            assert "Hello from AI" in body
        finally:
            chat_router_mod._session_manager = orig_mgr
            chat_router_mod._supervisor_factory = orig_factory
            chat_router_mod._backend = orig_backend

    def test_send_message_supervisor_error(self, sqlite_backend: SQLiteBackend):
        """Test supervisor error during message processing is handled."""
        orig_mgr = chat_router_mod._session_manager
        orig_factory = chat_router_mod._supervisor_factory
        orig_backend = chat_router_mod._backend

        try:
            mock_supervisor = MagicMock()

            async def mock_process_message(**kwargs):
                raise RuntimeError("AI exploded")
                yield  # Make it a generator  # noqa: RUF028

            mock_supervisor.process_message = mock_process_message

            def factory(mode=None, session=None, backend=None):
                return mock_supervisor

            chat_router_mod.init_chat_module(sqlite_backend, factory)

            app = FastAPI()
            app.include_router(chat_router_mod.router)
            client = TestClient(app)

            create_resp = client.post("/chat/sessions", json={"title": "Error Test"})
            session_id = create_resp.json()["id"]

            resp = client.post(
                f"/chat/sessions/{session_id}/messages",
                json={"content": "Break things"},
            )
            assert resp.status_code == 200
            body = resp.text
            assert "error" in body.lower()
        finally:
            chat_router_mod._session_manager = orig_mgr
            chat_router_mod._supervisor_factory = orig_factory
            chat_router_mod._backend = orig_backend

    def test_send_message_auto_generates_title(self, sqlite_backend: SQLiteBackend):
        """Test that first message auto-generates session title."""
        orig_mgr = chat_router_mod._session_manager
        orig_factory = chat_router_mod._supervisor_factory
        orig_backend = chat_router_mod._backend

        try:
            chat_router_mod.init_chat_module(sqlite_backend)

            app = FastAPI()
            app.include_router(chat_router_mod.router)
            client = TestClient(app)

            create_resp = client.post("/chat/sessions", json={"title": "New Chat"})
            session_id = create_resp.json()["id"]

            # Send first message (triggers title generation)
            client.post(
                f"/chat/sessions/{session_id}/messages",
                json={"content": "My very specific topic question"},
            )

            # Check the session title was updated
            get_resp = client.get(f"/chat/sessions/{session_id}")
            data = get_resp.json()
            assert data["title"] == "My very specific topic question"
        finally:
            chat_router_mod._session_manager = orig_mgr
            chat_router_mod._supervisor_factory = orig_factory
            chat_router_mod._backend = orig_backend


class TestChatCancellation:
    """Tests for chat generation cancellation endpoint."""

    def _create_session(self, client: TestClient) -> str:
        resp = client.post("/chat/sessions", json={"title": "Cancel Test"})
        return resp.json()["id"]

    def test_cancel_no_active_generation(self, chat_client: TestClient):
        """Test cancelling when no generation is active."""
        session_id = self._create_session(chat_client)

        resp = chat_client.post(f"/chat/sessions/{session_id}/cancel")
        assert resp.status_code == 200
        assert resp.json()["status"] == "no_active_generation"

    def test_cancel_session_not_found(self, chat_client: TestClient):
        """Test cancelling on non-existent session returns 404."""
        resp = chat_client.post("/chat/sessions/nonexistent/cancel")
        assert resp.status_code == 404

    def test_cancel_active_generation(self, chat_client: TestClient):
        """Test cancelling an active generation sets the event."""
        session_id = self._create_session(chat_client)

        # Simulate active generation
        cancel_event = asyncio.Event()
        chat_router_mod._active_generations[session_id] = cancel_event

        try:
            resp = chat_client.post(f"/chat/sessions/{session_id}/cancel")
            assert resp.status_code == 200
            assert resp.json()["status"] == "cancelled"
            assert cancel_event.is_set()
        finally:
            chat_router_mod._active_generations.pop(session_id, None)


class TestChatSessionJobs:
    """Tests for chat session job linkage endpoints."""

    def _create_session(self, client: TestClient) -> str:
        resp = client.post("/chat/sessions", json={"title": "Job Test"})
        return resp.json()["id"]

    def test_get_session_jobs_empty(self, chat_client: TestClient):
        """Test getting jobs for a session with no linked jobs."""
        session_id = self._create_session(chat_client)

        with patch("test_ai.api_state.job_manager", None):
            resp = chat_client.get(f"/chat/sessions/{session_id}/jobs")

        assert resp.status_code == 200
        data = resp.json()
        assert data["session_id"] == session_id
        assert data["jobs"] == []
        assert data["job_ids"] == []

    def test_get_session_jobs_not_found(self, chat_client: TestClient):
        """Test getting jobs for non-existent session returns 404."""
        resp = chat_client.get("/chat/sessions/nonexistent/jobs")
        assert resp.status_code == 404

    def test_get_session_jobs_with_job_manager(
        self, chat_client: TestClient, sqlite_backend: SQLiteBackend
    ):
        """Test getting jobs when JobManager is available."""
        session_id = self._create_session(chat_client)

        # Link a job via the manager directly
        mgr = ChatSessionManager(sqlite_backend)
        mgr.link_job(session_id, "job-123")

        mock_job = MagicMock()
        mock_job.id = "job-123"
        mock_job.workflow_id = "wf-456"
        mock_job.status.value = "completed"
        mock_job.created_at = datetime(2026, 1, 1, 0, 0, 0)
        mock_job.started_at = datetime(2026, 1, 1, 0, 0, 1)
        mock_job.completed_at = datetime(2026, 1, 1, 0, 0, 10)
        mock_job.progress = "100%"
        mock_job.error = None

        mock_jm = MagicMock()
        mock_jm.get_job.return_value = mock_job

        with patch("test_ai.api_state.job_manager", mock_jm):
            resp = chat_client.get(f"/chat/sessions/{session_id}/jobs")

        assert resp.status_code == 200
        data = resp.json()
        assert len(data["jobs"]) == 1
        assert data["jobs"][0]["id"] == "job-123"

    def test_get_session_jobs_job_not_found(
        self, chat_client: TestClient, sqlite_backend: SQLiteBackend
    ):
        """Test when linked job ID is not found in JobManager."""
        session_id = self._create_session(chat_client)

        mgr = ChatSessionManager(sqlite_backend)
        mgr.link_job(session_id, "job-gone")

        mock_jm = MagicMock()
        mock_jm.get_job.return_value = None

        with patch("test_ai.api_state.job_manager", mock_jm):
            resp = chat_client.get(f"/chat/sessions/{session_id}/jobs")

        assert resp.status_code == 200
        data = resp.json()
        assert len(data["jobs"]) == 0
        assert "job-gone" in data["job_ids"]


# ============================================================================
# Chat proposal endpoint tests
# ============================================================================


class TestChatProposalEndpoints:
    """Tests for chat edit proposal endpoints."""

    def _create_session_with_project(self, client: TestClient) -> str:
        resp = client.post(
            "/chat/sessions",
            json={"title": "Proposal Test", "project_path": "/tmp/project"},
        )
        return resp.json()["id"]

    def test_list_proposals_session_not_found(self, chat_client: TestClient):
        """Test listing proposals for non-existent session returns 404."""
        resp = chat_client.get("/chat/sessions/nonexistent/proposals")
        assert resp.status_code == 404

    def test_list_proposals_no_project_path(self, chat_client: TestClient):
        """Test listing proposals on session without project_path returns empty."""
        create_resp = chat_client.post("/chat/sessions", json={"title": "No Project"})
        session_id = create_resp.json()["id"]

        resp = chat_client.get(f"/chat/sessions/{session_id}/proposals")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_get_proposal_session_not_found(self, chat_client: TestClient):
        """Test getting a proposal for non-existent session returns 404."""
        resp = chat_client.get("/chat/sessions/nonexistent/proposals/prop-1")
        assert resp.status_code == 404

    def test_approve_proposal_session_not_found(self, chat_client: TestClient):
        """Test approving proposal for non-existent session returns 404."""
        resp = chat_client.post("/chat/sessions/nonexistent/proposals/prop-1/approve")
        assert resp.status_code == 404

    def test_reject_proposal_session_not_found(self, chat_client: TestClient):
        """Test rejecting proposal for non-existent session returns 404."""
        resp = chat_client.post("/chat/sessions/nonexistent/proposals/prop-1/reject")
        assert resp.status_code == 404

    def test_list_proposals_with_project(self, chat_client: TestClient):
        """Test listing proposals on session with project_path."""
        session_id = self._create_session_with_project(chat_client)

        mock_pm = MagicMock()
        mock_pm.get_session_proposals.return_value = []

        with (
            patch("test_ai.tools.proposals.ProposalManager", return_value=mock_pm),
            patch("test_ai.tools.safety.PathValidator"),
        ):
            resp = chat_client.get(f"/chat/sessions/{session_id}/proposals")
            assert resp.status_code == 200
            assert resp.json() == []

    def test_get_proposal_not_found(self, chat_client: TestClient):
        """Test getting a non-existent proposal returns 404."""
        session_id = self._create_session_with_project(chat_client)

        mock_pm = MagicMock()
        mock_pm.get_proposal.return_value = None

        with (
            patch("test_ai.tools.proposals.ProposalManager", return_value=mock_pm),
            patch("test_ai.tools.safety.PathValidator"),
        ):
            resp = chat_client.get(
                f"/chat/sessions/{session_id}/proposals/prop-missing"
            )
            assert resp.status_code == 404

    def test_get_proposal_wrong_session(self, chat_client: TestClient):
        """Test getting a proposal belonging to different session returns 404."""
        session_id = self._create_session_with_project(chat_client)

        mock_proposal = MagicMock()
        mock_proposal.session_id = "other-session"

        mock_pm = MagicMock()
        mock_pm.get_proposal.return_value = mock_proposal

        with (
            patch("test_ai.tools.proposals.ProposalManager", return_value=mock_pm),
            patch("test_ai.tools.safety.PathValidator"),
        ):
            resp = chat_client.get(f"/chat/sessions/{session_id}/proposals/prop-1")
            assert resp.status_code == 404

    def test_approve_proposal_not_found(self, chat_client: TestClient):
        """Test approving non-existent proposal returns 404."""
        session_id = self._create_session_with_project(chat_client)

        mock_pm = MagicMock()
        mock_pm.get_proposal.return_value = None

        with (
            patch("test_ai.tools.proposals.ProposalManager", return_value=mock_pm),
            patch("test_ai.tools.safety.PathValidator"),
        ):
            resp = chat_client.post(
                f"/chat/sessions/{session_id}/proposals/prop-missing/approve"
            )
            assert resp.status_code == 404

    def test_approve_proposal_wrong_session(self, chat_client: TestClient):
        """Test approving proposal from different session returns 404."""
        session_id = self._create_session_with_project(chat_client)

        mock_proposal = MagicMock()
        mock_proposal.session_id = "other-session"

        mock_pm = MagicMock()
        mock_pm.get_proposal.return_value = mock_proposal

        with (
            patch("test_ai.tools.proposals.ProposalManager", return_value=mock_pm),
            patch("test_ai.tools.safety.PathValidator"),
        ):
            resp = chat_client.post(
                f"/chat/sessions/{session_id}/proposals/prop-1/approve"
            )
            assert resp.status_code == 404

    def test_reject_proposal_not_found(self, chat_client: TestClient):
        """Test rejecting non-existent proposal returns 404."""
        session_id = self._create_session_with_project(chat_client)

        mock_pm = MagicMock()
        mock_pm.get_proposal.return_value = None

        with (
            patch("test_ai.tools.proposals.ProposalManager", return_value=mock_pm),
            patch("test_ai.tools.safety.PathValidator"),
        ):
            resp = chat_client.post(
                f"/chat/sessions/{session_id}/proposals/prop-missing/reject"
            )
            assert resp.status_code == 404

    def test_reject_proposal_wrong_session(self, chat_client: TestClient):
        """Test rejecting proposal from different session returns 404."""
        session_id = self._create_session_with_project(chat_client)

        mock_proposal = MagicMock()
        mock_proposal.session_id = "other-session"

        mock_pm = MagicMock()
        mock_pm.get_proposal.return_value = mock_proposal

        with (
            patch("test_ai.tools.proposals.ProposalManager", return_value=mock_pm),
            patch("test_ai.tools.safety.PathValidator"),
        ):
            resp = chat_client.post(
                f"/chat/sessions/{session_id}/proposals/prop-1/reject"
            )
            assert resp.status_code == 404

    def test_approve_proposal_value_error(self, chat_client: TestClient):
        """Test approve raises 400 on ValueError."""
        session_id = self._create_session_with_project(chat_client)

        mock_proposal = MagicMock()
        mock_proposal.session_id = session_id

        mock_pm = MagicMock()
        mock_pm.get_proposal.return_value = mock_proposal
        mock_pm.approve_proposal.side_effect = ValueError("Already approved")

        with (
            patch("test_ai.tools.proposals.ProposalManager", return_value=mock_pm),
            patch("test_ai.tools.safety.PathValidator"),
        ):
            resp = chat_client.post(
                f"/chat/sessions/{session_id}/proposals/prop-1/approve"
            )
            assert resp.status_code == 400

    def test_approve_proposal_generic_error(self, chat_client: TestClient):
        """Test approve raises 500 on generic error."""
        session_id = self._create_session_with_project(chat_client)

        mock_proposal = MagicMock()
        mock_proposal.session_id = session_id

        mock_pm = MagicMock()
        mock_pm.get_proposal.return_value = mock_proposal
        mock_pm.approve_proposal.side_effect = RuntimeError("Disk failure")

        with (
            patch("test_ai.tools.proposals.ProposalManager", return_value=mock_pm),
            patch("test_ai.tools.safety.PathValidator"),
        ):
            resp = chat_client.post(
                f"/chat/sessions/{session_id}/proposals/prop-1/approve"
            )
            assert resp.status_code == 500

    def test_reject_proposal_value_error(self, chat_client: TestClient):
        """Test reject raises 400 on ValueError."""
        session_id = self._create_session_with_project(chat_client)

        mock_proposal = MagicMock()
        mock_proposal.session_id = session_id

        mock_pm = MagicMock()
        mock_pm.get_proposal.return_value = mock_proposal
        mock_pm.reject_proposal.side_effect = ValueError("Already rejected")

        with (
            patch("test_ai.tools.proposals.ProposalManager", return_value=mock_pm),
            patch("test_ai.tools.safety.PathValidator"),
        ):
            resp = chat_client.post(
                f"/chat/sessions/{session_id}/proposals/prop-1/reject"
            )
            assert resp.status_code == 400

    def test_approve_proposal_success(self, chat_client: TestClient):
        """Test successful proposal approval."""
        session_id = self._create_session_with_project(chat_client)

        mock_proposal = MagicMock()
        mock_proposal.session_id = session_id

        approved_proposal = MagicMock()
        approved_proposal.id = "prop-1"
        approved_proposal.session_id = session_id
        approved_proposal.file_path = "src/main.py"
        approved_proposal.description = "Fix bug"
        approved_proposal.status.value = "applied"
        approved_proposal.created_at = datetime(2026, 1, 1, 0, 0, 0)
        approved_proposal.applied_at = datetime(2026, 1, 1, 0, 0, 1)
        approved_proposal.error_message = None

        mock_pm = MagicMock()
        mock_pm.get_proposal.return_value = mock_proposal
        mock_pm.approve_proposal.return_value = approved_proposal

        with (
            patch("test_ai.tools.proposals.ProposalManager", return_value=mock_pm),
            patch("test_ai.tools.safety.PathValidator"),
        ):
            resp = chat_client.post(
                f"/chat/sessions/{session_id}/proposals/prop-1/approve"
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["status"] == "applied"

    def test_reject_proposal_success(self, chat_client: TestClient):
        """Test successful proposal rejection."""
        session_id = self._create_session_with_project(chat_client)

        mock_proposal = MagicMock()
        mock_proposal.session_id = session_id

        rejected_proposal = MagicMock()
        rejected_proposal.id = "prop-1"
        rejected_proposal.session_id = session_id
        rejected_proposal.file_path = "src/main.py"
        rejected_proposal.description = "Fix bug"
        rejected_proposal.status.value = "rejected"
        rejected_proposal.created_at = datetime(2026, 1, 1, 0, 0, 0)
        rejected_proposal.applied_at = None
        rejected_proposal.error_message = None

        mock_pm = MagicMock()
        mock_pm.get_proposal.return_value = mock_proposal
        mock_pm.reject_proposal.return_value = rejected_proposal

        with (
            patch("test_ai.tools.proposals.ProposalManager", return_value=mock_pm),
            patch("test_ai.tools.safety.PathValidator"),
        ):
            resp = chat_client.post(
                f"/chat/sessions/{session_id}/proposals/prop-1/reject"
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["status"] == "rejected"

    def test_get_proposal_success(self, chat_client: TestClient):
        """Test successful proposal retrieval with content."""
        session_id = self._create_session_with_project(chat_client)

        mock_proposal = MagicMock()
        mock_proposal.id = "prop-1"
        mock_proposal.session_id = session_id
        mock_proposal.file_path = "src/main.py"
        mock_proposal.description = "Add logging"
        mock_proposal.status.value = "pending"
        mock_proposal.created_at = datetime(2026, 1, 1, 0, 0, 0)
        mock_proposal.applied_at = None
        mock_proposal.error_message = None
        mock_proposal.old_content = "print('hello')"
        mock_proposal.new_content = "logger.info('hello')"

        mock_pm = MagicMock()
        mock_pm.get_proposal.return_value = mock_proposal

        with (
            patch("test_ai.tools.proposals.ProposalManager", return_value=mock_pm),
            patch("test_ai.tools.safety.PathValidator"),
        ):
            resp = chat_client.get(f"/chat/sessions/{session_id}/proposals/prop-1")
            assert resp.status_code == 200
            data = resp.json()
            assert data["old_content"] == "print('hello')"
            assert data["new_content"] == "logger.info('hello')"

    def test_list_proposals_with_status_filter(self, chat_client: TestClient):
        """Test listing proposals with status filter."""
        session_id = self._create_session_with_project(chat_client)

        mock_pm = MagicMock()
        mock_pm.get_session_proposals.return_value = []

        with (
            patch("test_ai.tools.proposals.ProposalManager", return_value=mock_pm),
            patch("test_ai.tools.safety.PathValidator"),
            patch("test_ai.tools.models.ProposalStatus") as mock_ps,
        ):
            resp = chat_client.get(
                f"/chat/sessions/{session_id}/proposals?status=pending"
            )
            assert resp.status_code == 200
            mock_ps.assert_called_with("pending")

    def test_list_proposals_returns_items(self, chat_client: TestClient):
        """Test listing proposals returns formatted items."""
        session_id = self._create_session_with_project(chat_client)

        mock_p = MagicMock()
        mock_p.id = "prop-1"
        mock_p.session_id = session_id
        mock_p.file_path = "src/x.py"
        mock_p.description = "Change"
        mock_p.status.value = "pending"
        mock_p.created_at = datetime(2026, 1, 1, 0, 0, 0)
        mock_p.applied_at = None
        mock_p.error_message = None

        mock_pm = MagicMock()
        mock_pm.get_session_proposals.return_value = [mock_p]

        with (
            patch("test_ai.tools.proposals.ProposalManager", return_value=mock_pm),
            patch("test_ai.tools.safety.PathValidator"),
        ):
            resp = chat_client.get(f"/chat/sessions/{session_id}/proposals")
            assert resp.status_code == 200
            data = resp.json()
            assert len(data) == 1
            assert data[0]["id"] == "prop-1"


# ============================================================================
# Dashboard route tests
# ============================================================================


@pytest.fixture
def dashboard_app(sqlite_backend: SQLiteBackend):
    """Create a FastAPI app with dashboard router for testing."""
    from test_ai.api_routes.dashboard import router

    app = FastAPI()
    app.include_router(router, prefix="/v1")
    return app


@pytest.fixture
def dashboard_client(
    dashboard_app: FastAPI,
    sqlite_backend: SQLiteBackend,
):
    """Create a test client with dashboard routes and mock auth."""
    with (
        patch("test_ai.api_routes.dashboard.verify_auth"),
        patch(
            "test_ai.api_routes.dashboard.get_database",
            return_value=sqlite_backend,
        ),
    ):
        yield TestClient(dashboard_app)


class TestDashboardAgents:
    """Tests for dashboard agent definition endpoints."""

    def test_list_agents(self, dashboard_client: TestClient):
        """Test GET /agents returns all registered agents."""
        resp = dashboard_client.get("/v1/agents")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) > 0

        # Verify structure
        agent = data[0]
        assert "id" in agent
        assert "name" in agent
        assert "description" in agent
        assert "capabilities" in agent
        assert "icon" in agent
        assert "color" in agent

    def test_list_agents_has_planner(self, dashboard_client: TestClient):
        """Test that planner agent is in the list."""
        resp = dashboard_client.get("/v1/agents")
        data = resp.json()
        ids = [a["id"] for a in data]
        assert "planner" in ids

    def test_get_agent_planner(self, dashboard_client: TestClient):
        """Test GET /agents/planner returns planner definition."""
        resp = dashboard_client.get("/v1/agents/planner")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "planner"
        assert "Brain" in data["icon"]

    def test_get_agent_builder(self, dashboard_client: TestClient):
        """Test GET /agents/builder returns builder definition."""
        resp = dashboard_client.get("/v1/agents/builder")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "builder"

    def test_get_agent_not_found_invalid_role(self, dashboard_client: TestClient):
        """Test GET /agents/invalid returns 404."""
        resp = dashboard_client.get("/v1/agents/nonexistent_role")
        assert resp.status_code == 404

    def test_get_agent_icons_and_colors(self, dashboard_client: TestClient):
        """Test that agents have proper icons and colors."""
        resp = dashboard_client.get("/v1/agents")
        data = resp.json()

        for agent in data:
            assert agent["icon"] is not None
            assert agent["color"] is not None
            assert agent["color"].startswith("#")

    def test_get_agent_capabilities(self, dashboard_client: TestClient):
        """Test that agents have capabilities listed."""
        resp = dashboard_client.get("/v1/agents/planner")
        data = resp.json()
        assert len(data["capabilities"]) > 0
        assert "Task decomposition" in data["capabilities"]


class TestDashboardStats:
    """Tests for dashboard statistics endpoint."""

    def test_get_dashboard_stats_empty(self, dashboard_client: TestClient):
        """Test dashboard stats with no data."""
        with patch("test_ai.api_routes.dashboard.state") as mock_state:
            mock_state.workflow_engine.list_workflows.return_value = []
            resp = dashboard_client.get("/v1/dashboard/stats")

        assert resp.status_code == 200
        data = resp.json()
        assert data["totalWorkflows"] == 0
        assert data["activeExecutions"] == 0
        assert data["completedToday"] == 0
        assert data["failedToday"] == 0
        assert data["totalTokensToday"] == 0
        assert data["totalCostToday"] == 0.0

    def test_get_dashboard_stats_with_workflows(self, dashboard_client: TestClient):
        """Test dashboard stats with workflows present."""
        with patch("test_ai.api_routes.dashboard.state") as mock_state:
            mock_state.workflow_engine.list_workflows.return_value = [
                {"id": "wf1"},
                {"id": "wf2"},
                {"id": "wf3"},
            ]
            resp = dashboard_client.get("/v1/dashboard/stats")

        assert resp.status_code == 200
        data = resp.json()
        assert data["totalWorkflows"] == 3

    def test_get_dashboard_stats_with_active_executions(
        self,
        sqlite_backend: SQLiteBackend,
        dashboard_client: TestClient,
    ):
        """Test dashboard stats counts active executions."""
        _insert(
            sqlite_backend,
            "INSERT INTO executions (id, workflow_id, workflow_name, status, created_at) VALUES (?, ?, ?, ?, ?)",
            ("exec-1", "wf-1", "Test WF", "running", datetime.now().isoformat()),
        )

        with patch("test_ai.api_routes.dashboard.state") as mock_state:
            mock_state.workflow_engine.list_workflows.return_value = []
            resp = dashboard_client.get("/v1/dashboard/stats")

        assert resp.status_code == 200
        data = resp.json()
        assert data["activeExecutions"] == 1

    def test_get_dashboard_stats_completed_and_failed(
        self,
        sqlite_backend: SQLiteBackend,
        dashboard_client: TestClient,
    ):
        """Test dashboard stats counts completed and failed today."""
        now = datetime.now()
        _insert(
            sqlite_backend,
            "INSERT INTO executions (id, workflow_id, workflow_name, status, completed_at, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            ("exec-ok", "wf-1", "OK WF", "completed", now.isoformat(), now.isoformat()),
        )
        _insert(
            sqlite_backend,
            "INSERT INTO executions (id, workflow_id, workflow_name, status, completed_at, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (
                "exec-fail",
                "wf-2",
                "Fail WF",
                "failed",
                now.isoformat(),
                now.isoformat(),
            ),
        )

        with patch("test_ai.api_routes.dashboard.state") as mock_state:
            mock_state.workflow_engine.list_workflows.return_value = []
            resp = dashboard_client.get("/v1/dashboard/stats")

        data = resp.json()
        assert data["completedToday"] == 1
        assert data["failedToday"] == 1

    def test_get_dashboard_stats_tokens(
        self,
        sqlite_backend: SQLiteBackend,
        dashboard_client: TestClient,
    ):
        """Test dashboard stats aggregates token usage."""
        now = datetime.now()
        _insert(
            sqlite_backend,
            "INSERT INTO executions (id, workflow_id, workflow_name, status, created_at) VALUES (?, ?, ?, ?, ?)",
            ("exec-t", "wf-t", "Token WF", "completed", now.isoformat()),
        )
        _insert(
            sqlite_backend,
            "INSERT INTO execution_metrics (execution_id, total_tokens, total_cost_cents) VALUES (?, ?, ?)",
            ("exec-t", 5000, 250),
        )

        with patch("test_ai.api_routes.dashboard.state") as mock_state:
            mock_state.workflow_engine.list_workflows.return_value = []
            resp = dashboard_client.get("/v1/dashboard/stats")

        data = resp.json()
        assert data["totalTokensToday"] == 5000
        assert data["totalCostToday"] == 2.50

    def test_get_dashboard_stats_none_workflows(self, dashboard_client: TestClient):
        """Test dashboard stats handles None from list_workflows."""
        with patch("test_ai.api_routes.dashboard.state") as mock_state:
            mock_state.workflow_engine.list_workflows.return_value = None
            resp = dashboard_client.get("/v1/dashboard/stats")

        data = resp.json()
        assert data["totalWorkflows"] == 0


class TestRecentExecutions:
    """Tests for dashboard recent executions endpoint."""

    def test_recent_executions_empty(self, dashboard_client: TestClient):
        """Test recent executions with no data."""
        mock_result = MagicMock()
        mock_result.data = []

        with patch("test_ai.api_routes.dashboard.state") as mock_state:
            mock_state.execution_manager.list_executions.return_value = mock_result
            resp = dashboard_client.get("/v1/dashboard/recent-executions")

        assert resp.status_code == 200
        assert resp.json() == []

    def test_recent_executions_just_now(self, dashboard_client: TestClient):
        """Test time formatting for executions started seconds ago."""
        mock_exec = MagicMock()
        mock_exec.id = "exec-1"
        mock_exec.workflow_name = "Test WF"
        mock_exec.status.value = "running"
        mock_exec.started_at = datetime.now() - timedelta(seconds=30)

        mock_result = MagicMock()
        mock_result.data = [mock_exec]

        with patch("test_ai.api_routes.dashboard.state") as mock_state:
            mock_state.execution_manager.list_executions.return_value = mock_result
            resp = dashboard_client.get("/v1/dashboard/recent-executions")

        data = resp.json()
        assert len(data) == 1
        assert data[0]["time"] == "just now"

    def test_recent_executions_minutes_ago(self, dashboard_client: TestClient):
        """Test time formatting for executions started minutes ago."""
        mock_exec = MagicMock()
        mock_exec.id = "exec-2"
        mock_exec.workflow_name = "Min WF"
        mock_exec.status.value = "completed"
        mock_exec.started_at = datetime.now() - timedelta(minutes=15)

        mock_result = MagicMock()
        mock_result.data = [mock_exec]

        with patch("test_ai.api_routes.dashboard.state") as mock_state:
            mock_state.execution_manager.list_executions.return_value = mock_result
            resp = dashboard_client.get("/v1/dashboard/recent-executions")

        data = resp.json()
        assert "15 min ago" == data[0]["time"]

    def test_recent_executions_hours_ago(self, dashboard_client: TestClient):
        """Test time formatting for executions started hours ago."""
        mock_exec = MagicMock()
        mock_exec.id = "exec-3"
        mock_exec.workflow_name = "Hour WF"
        mock_exec.status.value = "completed"
        mock_exec.started_at = datetime.now() - timedelta(hours=3)

        mock_result = MagicMock()
        mock_result.data = [mock_exec]

        with patch("test_ai.api_routes.dashboard.state") as mock_state:
            mock_state.execution_manager.list_executions.return_value = mock_result
            resp = dashboard_client.get("/v1/dashboard/recent-executions")

        data = resp.json()
        assert data[0]["time"] == "3 hours ago"

    def test_recent_executions_1_hour_ago(self, dashboard_client: TestClient):
        """Test singular 'hour' formatting."""
        mock_exec = MagicMock()
        mock_exec.id = "exec-4"
        mock_exec.workflow_name = "1h WF"
        mock_exec.status.value = "completed"
        mock_exec.started_at = datetime.now() - timedelta(hours=1, minutes=10)

        mock_result = MagicMock()
        mock_result.data = [mock_exec]

        with patch("test_ai.api_routes.dashboard.state") as mock_state:
            mock_state.execution_manager.list_executions.return_value = mock_result
            resp = dashboard_client.get("/v1/dashboard/recent-executions")

        data = resp.json()
        assert data[0]["time"] == "1 hour ago"

    def test_recent_executions_days_ago(self, dashboard_client: TestClient):
        """Test time formatting for executions started days ago."""
        mock_exec = MagicMock()
        mock_exec.id = "exec-5"
        mock_exec.workflow_name = "Day WF"
        mock_exec.status.value = "completed"
        mock_exec.started_at = datetime.now() - timedelta(days=2)

        mock_result = MagicMock()
        mock_result.data = [mock_exec]

        with patch("test_ai.api_routes.dashboard.state") as mock_state:
            mock_state.execution_manager.list_executions.return_value = mock_result
            resp = dashboard_client.get("/v1/dashboard/recent-executions")

        data = resp.json()
        assert data[0]["time"] == "2 days ago"

    def test_recent_executions_1_day_ago(self, dashboard_client: TestClient):
        """Test singular 'day' formatting."""
        mock_exec = MagicMock()
        mock_exec.id = "exec-6"
        mock_exec.workflow_name = "1d WF"
        mock_exec.status.value = "completed"
        mock_exec.started_at = datetime.now() - timedelta(days=1, hours=2)

        mock_result = MagicMock()
        mock_result.data = [mock_exec]

        with patch("test_ai.api_routes.dashboard.state") as mock_state:
            mock_state.execution_manager.list_executions.return_value = mock_result
            resp = dashboard_client.get("/v1/dashboard/recent-executions")

        data = resp.json()
        assert data[0]["time"] == "1 day ago"

    def test_recent_executions_pending(self, dashboard_client: TestClient):
        """Test time formatting for pending executions (no started_at)."""
        mock_exec = MagicMock()
        mock_exec.id = "exec-7"
        mock_exec.workflow_name = "Pending WF"
        mock_exec.status.value = "pending"
        mock_exec.started_at = None

        mock_result = MagicMock()
        mock_result.data = [mock_exec]

        with patch("test_ai.api_routes.dashboard.state") as mock_state:
            mock_state.execution_manager.list_executions.return_value = mock_result
            resp = dashboard_client.get("/v1/dashboard/recent-executions")

        data = resp.json()
        assert data[0]["time"] == "pending"

    def test_recent_executions_custom_limit(self, dashboard_client: TestClient):
        """Test recent executions with custom limit parameter."""
        mock_result = MagicMock()
        mock_result.data = []

        with patch("test_ai.api_routes.dashboard.state") as mock_state:
            mock_state.execution_manager.list_executions.return_value = mock_result
            resp = dashboard_client.get("/v1/dashboard/recent-executions?limit=10")

        assert resp.status_code == 200
        mock_state.execution_manager.list_executions.assert_called_once_with(
            page=1, page_size=10
        )


class TestDailyUsage:
    """Tests for dashboard daily usage endpoint."""

    def test_daily_usage_default_days(self, dashboard_client: TestClient):
        """Test daily usage returns 7 days by default."""
        resp = dashboard_client.get("/v1/dashboard/usage/daily")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 7

    def test_daily_usage_custom_days(self, dashboard_client: TestClient):
        """Test daily usage with custom days parameter."""
        resp = dashboard_client.get("/v1/dashboard/usage/daily?days=3")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 3

    def test_daily_usage_has_day_names(self, dashboard_client: TestClient):
        """Test daily usage entries have day names."""
        resp = dashboard_client.get("/v1/dashboard/usage/daily")
        data = resp.json()

        valid_days = {"Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"}
        for entry in data:
            assert entry["date"] in valid_days

    def test_daily_usage_with_data(
        self,
        sqlite_backend: SQLiteBackend,
        dashboard_client: TestClient,
    ):
        """Test daily usage aggregates metrics correctly."""
        now = datetime.now()
        _insert(
            sqlite_backend,
            "INSERT INTO executions (id, workflow_id, workflow_name, status, created_at) VALUES (?, ?, ?, ?, ?)",
            ("exec-u", "wf-u", "Usage WF", "completed", now.isoformat()),
        )
        _insert(
            sqlite_backend,
            "INSERT INTO execution_metrics (execution_id, total_tokens, total_cost_cents) VALUES (?, ?, ?)",
            ("exec-u", 1000, 50),
        )

        resp = dashboard_client.get("/v1/dashboard/usage/daily")
        data = resp.json()

        # At least one day should have non-zero tokens
        has_data = any(d["tokens"] > 0 for d in data)
        assert has_data


class TestAgentUsage:
    """Tests for dashboard agent usage endpoint."""

    def test_agent_usage_empty(self, dashboard_client: TestClient):
        """Test agent usage returns defaults when no data."""
        resp = dashboard_client.get("/v1/dashboard/usage/by-agent")
        assert resp.status_code == 200
        data = resp.json()
        # Should return default empty agents
        assert len(data) == 5
        agents = [d["agent"] for d in data]
        assert "Planner" in agents
        assert "Builder" in agents

    def test_agent_usage_with_plan_workflow(
        self,
        sqlite_backend: SQLiteBackend,
        dashboard_client: TestClient,
    ):
        """Test agent usage categorizes plan-like workflows."""
        now = datetime.now()
        _insert(
            sqlite_backend,
            "INSERT INTO executions (id, workflow_id, workflow_name, status, created_at) VALUES (?, ?, ?, ?, ?)",
            ("exec-p", "wf-p", "Plan Feature", "completed", now.isoformat()),
        )
        _insert(
            sqlite_backend,
            "INSERT INTO execution_metrics (execution_id, total_tokens, total_cost_cents) VALUES (?, ?, ?)",
            ("exec-p", 3000, 150),
        )

        resp = dashboard_client.get("/v1/dashboard/usage/by-agent")
        data = resp.json()
        planner = next((d for d in data if d["agent"] == "Planner"), None)
        assert planner is not None
        assert planner["tokens"] == 3000

    def test_agent_usage_with_test_workflow(
        self,
        sqlite_backend: SQLiteBackend,
        dashboard_client: TestClient,
    ):
        """Test agent usage categorizes test-like workflows."""
        now = datetime.now()
        _insert(
            sqlite_backend,
            "INSERT INTO executions (id, workflow_id, workflow_name, status, created_at) VALUES (?, ?, ?, ?, ?)",
            ("exec-t", "wf-t", "Test Coverage", "completed", now.isoformat()),
        )
        _insert(
            sqlite_backend,
            "INSERT INTO execution_metrics (execution_id, total_tokens, total_cost_cents) VALUES (?, ?, ?)",
            ("exec-t", 2000, 100),
        )

        resp = dashboard_client.get("/v1/dashboard/usage/by-agent")
        data = resp.json()
        tester = next((d for d in data if d["agent"] == "Tester"), None)
        assert tester is not None
        assert tester["tokens"] == 2000

    def test_agent_usage_with_review_workflow(
        self,
        sqlite_backend: SQLiteBackend,
        dashboard_client: TestClient,
    ):
        """Test agent usage categorizes review-like workflows."""
        now = datetime.now()
        _insert(
            sqlite_backend,
            "INSERT INTO executions (id, workflow_id, workflow_name, status, created_at) VALUES (?, ?, ?, ?, ?)",
            ("exec-r", "wf-r", "PR Review", "completed", now.isoformat()),
        )
        _insert(
            sqlite_backend,
            "INSERT INTO execution_metrics (execution_id, total_tokens, total_cost_cents) VALUES (?, ?, ?)",
            ("exec-r", 1500, 75),
        )

        resp = dashboard_client.get("/v1/dashboard/usage/by-agent")
        data = resp.json()
        reviewer = next((d for d in data if d["agent"] == "Reviewer"), None)
        assert reviewer is not None
        assert reviewer["tokens"] == 1500

    def test_agent_usage_with_build_workflow(
        self,
        sqlite_backend: SQLiteBackend,
        dashboard_client: TestClient,
    ):
        """Test agent usage categorizes build/implement/code workflows."""
        now = datetime.now()
        _insert(
            sqlite_backend,
            "INSERT INTO executions (id, workflow_id, workflow_name, status, created_at) VALUES (?, ?, ?, ?, ?)",
            ("exec-b", "wf-b", "Build Feature", "completed", now.isoformat()),
        )
        _insert(
            sqlite_backend,
            "INSERT INTO execution_metrics (execution_id, total_tokens, total_cost_cents) VALUES (?, ?, ?)",
            ("exec-b", 4000, 200),
        )

        resp = dashboard_client.get("/v1/dashboard/usage/by-agent")
        data = resp.json()
        builder = next((d for d in data if d["agent"] == "Builder"), None)
        assert builder is not None
        assert builder["tokens"] == 4000

    def test_agent_usage_with_doc_workflow(
        self,
        sqlite_backend: SQLiteBackend,
        dashboard_client: TestClient,
    ):
        """Test agent usage categorizes doc-like workflows."""
        now = datetime.now()
        _insert(
            sqlite_backend,
            "INSERT INTO executions (id, workflow_id, workflow_name, status, created_at) VALUES (?, ?, ?, ?, ?)",
            ("exec-d", "wf-d", "Document API", "completed", now.isoformat()),
        )
        _insert(
            sqlite_backend,
            "INSERT INTO execution_metrics (execution_id, total_tokens, total_cost_cents) VALUES (?, ?, ?)",
            ("exec-d", 500, 25),
        )

        resp = dashboard_client.get("/v1/dashboard/usage/by-agent")
        data = resp.json()
        documenter = next((d for d in data if d["agent"] == "Documenter"), None)
        assert documenter is not None
        assert documenter["tokens"] == 500

    def test_agent_usage_uncategorized_to_builder(
        self,
        sqlite_backend: SQLiteBackend,
        dashboard_client: TestClient,
    ):
        """Test agent usage defaults uncategorized workflows to builder."""
        now = datetime.now()
        _insert(
            sqlite_backend,
            "INSERT INTO executions (id, workflow_id, workflow_name, status, created_at) VALUES (?, ?, ?, ?, ?)",
            ("exec-x", "wf-x", "Random Stuff", "completed", now.isoformat()),
        )
        _insert(
            sqlite_backend,
            "INSERT INTO execution_metrics (execution_id, total_tokens, total_cost_cents) VALUES (?, ?, ?)",
            ("exec-x", 1000, 50),
        )

        resp = dashboard_client.get("/v1/dashboard/usage/by-agent")
        data = resp.json()
        builder = next((d for d in data if d["agent"] == "Builder"), None)
        assert builder is not None
        assert builder["tokens"] >= 1000

    def test_agent_usage_analysis_maps_to_planner(
        self,
        sqlite_backend: SQLiteBackend,
        dashboard_client: TestClient,
    ):
        """Test agent usage 'analysis' keyword maps to planner."""
        now = datetime.now()
        _insert(
            sqlite_backend,
            "INSERT INTO executions (id, workflow_id, workflow_name, status, created_at) VALUES (?, ?, ?, ?, ?)",
            ("exec-a", "wf-a", "Data Analysis", "completed", now.isoformat()),
        )
        _insert(
            sqlite_backend,
            "INSERT INTO execution_metrics (execution_id, total_tokens, total_cost_cents) VALUES (?, ?, ?)",
            ("exec-a", 2500, 125),
        )

        resp = dashboard_client.get("/v1/dashboard/usage/by-agent")
        data = resp.json()
        planner = next((d for d in data if d["agent"] == "Planner"), None)
        assert planner is not None
        assert planner["tokens"] == 2500

    def test_agent_usage_null_workflow_name(
        self,
        sqlite_backend: SQLiteBackend,
        dashboard_client: TestClient,
    ):
        """Test agent usage handles null workflow_name gracefully."""
        now = datetime.now()
        _insert(
            sqlite_backend,
            "INSERT INTO executions (id, workflow_id, workflow_name, status, created_at) VALUES (?, ?, ?, ?, ?)",
            ("exec-null", "wf-null", None, "completed", now.isoformat()),
        )
        _insert(
            sqlite_backend,
            "INSERT INTO execution_metrics (execution_id, total_tokens, total_cost_cents) VALUES (?, ?, ?)",
            ("exec-null", 100, 5),
        )

        # Should not crash
        resp = dashboard_client.get("/v1/dashboard/usage/by-agent")
        assert resp.status_code == 200


class TestDashboardBudget:
    """Tests for dashboard budget endpoint."""

    def test_budget_empty(self, dashboard_client: TestClient):
        """Test budget returns zeros when no data."""
        resp = dashboard_client.get("/v1/dashboard/budget")
        assert resp.status_code == 200
        data = resp.json()
        assert data["totalBudget"] == 100.0
        assert data["totalUsed"] == 0.0
        assert data["percentUsed"] == 0.0
        assert len(data["byAgent"]) == 4
        assert data["alert"] is None

    def test_budget_with_plan_costs(
        self,
        sqlite_backend: SQLiteBackend,
        dashboard_client: TestClient,
    ):
        """Test budget categorizes plan workflows to Planner."""
        now = datetime.now()
        _insert(
            sqlite_backend,
            "INSERT INTO executions (id, workflow_id, workflow_name, status, created_at) VALUES (?, ?, ?, ?, ?)",
            ("exec-bp", "wf-bp", "Plan Phase", "completed", now.isoformat()),
        )
        _insert(
            sqlite_backend,
            "INSERT INTO execution_metrics (execution_id, total_tokens, total_cost_cents) VALUES (?, ?, ?)",
            ("exec-bp", 1000, 500),
        )

        resp = dashboard_client.get("/v1/dashboard/budget")
        data = resp.json()
        planner = next((a for a in data["byAgent"] if a["agent"] == "Planner"), None)
        assert planner is not None
        assert planner["used"] == 5.0

    def test_budget_with_review_costs(
        self,
        sqlite_backend: SQLiteBackend,
        dashboard_client: TestClient,
    ):
        """Test budget categorizes review workflows to Reviewer."""
        now = datetime.now()
        _insert(
            sqlite_backend,
            "INSERT INTO executions (id, workflow_id, workflow_name, status, created_at) VALUES (?, ?, ?, ?, ?)",
            ("exec-br", "wf-br", "PR Review", "completed", now.isoformat()),
        )
        _insert(
            sqlite_backend,
            "INSERT INTO execution_metrics (execution_id, total_tokens, total_cost_cents) VALUES (?, ?, ?)",
            ("exec-br", 500, 200),
        )

        resp = dashboard_client.get("/v1/dashboard/budget")
        data = resp.json()
        reviewer = next((a for a in data["byAgent"] if a["agent"] == "Reviewer"), None)
        assert reviewer is not None
        assert reviewer["used"] == 2.0

    def test_budget_with_test_costs(
        self,
        sqlite_backend: SQLiteBackend,
        dashboard_client: TestClient,
    ):
        """Test budget categorizes test workflows to Tester."""
        now = datetime.now()
        _insert(
            sqlite_backend,
            "INSERT INTO executions (id, workflow_id, workflow_name, status, created_at) VALUES (?, ?, ?, ?, ?)",
            ("exec-bt", "wf-bt", "Test Suite", "completed", now.isoformat()),
        )
        _insert(
            sqlite_backend,
            "INSERT INTO execution_metrics (execution_id, total_tokens, total_cost_cents) VALUES (?, ?, ?)",
            ("exec-bt", 300, 100),
        )

        resp = dashboard_client.get("/v1/dashboard/budget")
        data = resp.json()
        tester = next((a for a in data["byAgent"] if a["agent"] == "Tester"), None)
        assert tester is not None
        assert tester["used"] == 1.0

    def test_budget_default_to_builder(
        self,
        sqlite_backend: SQLiteBackend,
        dashboard_client: TestClient,
    ):
        """Test budget defaults uncategorized workflows to Builder."""
        now = datetime.now()
        _insert(
            sqlite_backend,
            "INSERT INTO executions (id, workflow_id, workflow_name, status, created_at) VALUES (?, ?, ?, ?, ?)",
            ("exec-bb", "wf-bb", "Random Workflow", "completed", now.isoformat()),
        )
        _insert(
            sqlite_backend,
            "INSERT INTO execution_metrics (execution_id, total_tokens, total_cost_cents) VALUES (?, ?, ?)",
            ("exec-bb", 200, 100),
        )

        resp = dashboard_client.get("/v1/dashboard/budget")
        data = resp.json()
        builder = next((a for a in data["byAgent"] if a["agent"] == "Builder"), None)
        assert builder is not None
        assert builder["used"] == 1.0

    def test_budget_alert_over_80_percent(
        self,
        sqlite_backend: SQLiteBackend,
        dashboard_client: TestClient,
    ):
        """Test budget alert triggers at 80% of agent limit."""
        now = datetime.now()
        # Tester limit is $15. Insert $13 worth (86%)
        _insert(
            sqlite_backend,
            "INSERT INTO executions (id, workflow_id, workflow_name, status, created_at) VALUES (?, ?, ?, ?, ?)",
            ("exec-alert", "wf-alert", "Test Heavy", "completed", now.isoformat()),
        )
        _insert(
            sqlite_backend,
            "INSERT INTO execution_metrics (execution_id, total_tokens, total_cost_cents) VALUES (?, ?, ?)",
            ("exec-alert", 10000, 1300),
        )

        resp = dashboard_client.get("/v1/dashboard/budget")
        data = resp.json()
        assert data["alert"] is not None
        assert "Tester" in data["alert"]
        assert "86%" in data["alert"]

    def test_budget_percent_used_calculation(
        self,
        sqlite_backend: SQLiteBackend,
        dashboard_client: TestClient,
    ):
        """Test budget percent used is calculated correctly."""
        now = datetime.now()
        # $10 of $100 total = 10%
        _insert(
            sqlite_backend,
            "INSERT INTO executions (id, workflow_id, workflow_name, status, created_at) VALUES (?, ?, ?, ?, ?)",
            ("exec-pct", "wf-pct", "Some Work", "completed", now.isoformat()),
        )
        _insert(
            sqlite_backend,
            "INSERT INTO execution_metrics (execution_id, total_tokens, total_cost_cents) VALUES (?, ?, ?)",
            ("exec-pct", 5000, 1000),
        )

        resp = dashboard_client.get("/v1/dashboard/budget")
        data = resp.json()
        assert data["totalUsed"] == 10.0
        assert data["percentUsed"] == 10.0

    def test_budget_analysis_maps_to_planner(
        self,
        sqlite_backend: SQLiteBackend,
        dashboard_client: TestClient,
    ):
        """Test budget 'analysis' keyword maps to planner."""
        now = datetime.now()
        _insert(
            sqlite_backend,
            "INSERT INTO executions (id, workflow_id, workflow_name, status, created_at) VALUES (?, ?, ?, ?, ?)",
            ("exec-ba", "wf-ba", "Data Analysis", "completed", now.isoformat()),
        )
        _insert(
            sqlite_backend,
            "INSERT INTO execution_metrics (execution_id, total_tokens, total_cost_cents) VALUES (?, ?, ?)",
            ("exec-ba", 200, 100),
        )

        resp = dashboard_client.get("/v1/dashboard/budget")
        data = resp.json()
        planner = next((a for a in data["byAgent"] if a["agent"] == "Planner"), None)
        assert planner is not None
        assert planner["used"] == 1.0

    def test_budget_null_workflow_name(
        self,
        sqlite_backend: SQLiteBackend,
        dashboard_client: TestClient,
    ):
        """Test budget handles null workflow_name gracefully."""
        now = datetime.now()
        _insert(
            sqlite_backend,
            "INSERT INTO executions (id, workflow_id, workflow_name, status, created_at) VALUES (?, ?, ?, ?, ?)",
            ("exec-bn", "wf-bn", None, "completed", now.isoformat()),
        )
        _insert(
            sqlite_backend,
            "INSERT INTO execution_metrics (execution_id, total_tokens, total_cost_cents) VALUES (?, ?, ?)",
            ("exec-bn", 100, 50),
        )

        resp = dashboard_client.get("/v1/dashboard/budget")
        assert resp.status_code == 200


class TestGetProposalManager:
    """Tests for _get_proposal_manager helper in chat router."""

    def test_get_proposal_manager_no_session(self):
        """Test _get_proposal_manager raises 404 when session not found."""
        orig_mgr = chat_router_mod._session_manager
        orig_backend = chat_router_mod._backend

        try:
            mock_mgr = MagicMock()
            mock_mgr.get_session.return_value = None
            chat_router_mod._session_manager = mock_mgr
            chat_router_mod._backend = MagicMock()

            with pytest.raises(HTTPException) as exc_info:
                chat_router_mod._get_proposal_manager("nonexistent")
            assert exc_info.value.status_code == 404
        finally:
            chat_router_mod._session_manager = orig_mgr
            chat_router_mod._backend = orig_backend

    def test_get_proposal_manager_no_project_path(self, sqlite_backend: SQLiteBackend):
        """Test _get_proposal_manager raises 400 when no project path."""
        orig_mgr = chat_router_mod._session_manager
        orig_backend = chat_router_mod._backend

        try:
            mock_session = MagicMock()
            mock_session.project_path = None

            mock_mgr = MagicMock()
            mock_mgr.get_session.return_value = mock_session
            chat_router_mod._session_manager = mock_mgr
            chat_router_mod._backend = sqlite_backend

            with pytest.raises(HTTPException) as exc_info:
                chat_router_mod._get_proposal_manager("sess-1")
            assert exc_info.value.status_code == 400
        finally:
            chat_router_mod._session_manager = orig_mgr
            chat_router_mod._backend = orig_backend

    def test_get_proposal_manager_security_error(self, sqlite_backend: SQLiteBackend):
        """Test _get_proposal_manager raises 400 on SecurityError."""
        orig_mgr = chat_router_mod._session_manager
        orig_backend = chat_router_mod._backend

        try:
            mock_session = MagicMock()
            mock_session.project_path = "/tmp/project"
            mock_session.allowed_paths = []

            mock_mgr = MagicMock()
            mock_mgr.get_session.return_value = mock_session
            chat_router_mod._session_manager = mock_mgr
            chat_router_mod._backend = sqlite_backend

            from test_ai.tools.safety import SecurityError

            with patch(
                "test_ai.tools.safety.PathValidator",
                side_effect=SecurityError("Bad path"),
            ):
                with pytest.raises(HTTPException) as exc_info:
                    chat_router_mod._get_proposal_manager("sess-1")
                assert exc_info.value.status_code == 400
        finally:
            chat_router_mod._session_manager = orig_mgr
            chat_router_mod._backend = orig_backend
