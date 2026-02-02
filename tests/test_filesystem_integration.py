"""Integration tests for filesystem tools with supervisor and API."""

import json
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from test_ai.agents.supervisor import SupervisorAgent
from test_ai.chat.models import ChatMessage, ChatMode, ChatSession, MessageRole
from test_ai.tools.models import ProposalStatus
from test_ai.tools.proposals import ProposalManager
from test_ai.tools.safety import PathValidator
from test_ai.tools.filesystem import FilesystemTools


class TestSupervisorToolIntegration:
    """Tests for supervisor tool call parsing and execution."""

    @pytest.fixture
    def mock_provider(self):
        """Create a mock LLM provider."""
        provider = MagicMock()
        provider.complete = AsyncMock()
        return provider

    @pytest.fixture
    def temp_project(self, tmp_path: Path):
        """Create a temporary project directory."""
        # Create some test files
        (tmp_path / "main.py").write_text("def main():\n    pass")
        (tmp_path / "utils.py").write_text("def helper():\n    return 42")
        src = tmp_path / "src"
        src.mkdir()
        (src / "module.py").write_text("class MyClass:\n    pass")
        return tmp_path

    @pytest.fixture
    def session_with_project(self, temp_project: Path):
        """Create a chat session with project path."""
        return ChatSession(
            id="test-session-123",
            title="Test Session",
            project_path=str(temp_project),
            mode=ChatMode.ASSISTANT,
            filesystem_enabled=True,
        )

    @pytest.fixture
    def mock_backend(self):
        """Create a mock database backend."""
        backend = MagicMock()
        backend.adapt_query = lambda q: q
        backend.execute = MagicMock()
        backend.fetchone = MagicMock(return_value=None)
        backend.fetchall = MagicMock(return_value=[])
        return backend

    def test_parse_single_tool_call(self, mock_provider):
        """Test parsing a single tool call from response."""
        supervisor = SupervisorAgent(mock_provider)

        response = '''Let me check the files.

<tool_call>
{"tool": "list_files", "path": "."}
</tool_call>

I'll analyze the results.'''

        tool_calls = supervisor._parse_tool_calls(response)

        assert len(tool_calls) == 1
        assert tool_calls[0]["tool"] == "list_files"
        assert tool_calls[0]["path"] == "."

    def test_parse_multiple_tool_calls(self, mock_provider):
        """Test parsing multiple tool calls from response."""
        supervisor = SupervisorAgent(mock_provider)

        response = '''<tool_call>
{"tool": "get_structure"}
</tool_call>

Now let me read a file:

<tool_call>
{"tool": "read_file", "path": "main.py"}
</tool_call>'''

        tool_calls = supervisor._parse_tool_calls(response)

        assert len(tool_calls) == 2
        assert tool_calls[0]["tool"] == "get_structure"
        assert tool_calls[1]["tool"] == "read_file"
        assert tool_calls[1]["path"] == "main.py"

    def test_parse_invalid_json_ignored(self, mock_provider):
        """Test that invalid JSON in tool calls is gracefully ignored."""
        supervisor = SupervisorAgent(mock_provider)

        response = '''<tool_call>
{"tool": "list_files", invalid json here}
</tool_call>

<tool_call>
{"tool": "read_file", "path": "valid.py"}
</tool_call>'''

        tool_calls = supervisor._parse_tool_calls(response)

        assert len(tool_calls) == 1
        assert tool_calls[0]["tool"] == "read_file"

    @pytest.mark.asyncio
    async def test_execute_read_file_tool(
        self, mock_provider, session_with_project, mock_backend, temp_project
    ):
        """Test executing a read_file tool call."""
        supervisor = SupervisorAgent(
            mock_provider,
            session=session_with_project,
            backend=mock_backend,
        )

        tool_call = {"tool": "read_file", "path": "main.py"}
        result = await supervisor._execute_tool_call(tool_call)

        assert result["tool"] == "read_file"
        assert result["success"] is True
        assert "data" in result
        assert "def main()" in result["data"]["content"]

    @pytest.mark.asyncio
    async def test_execute_list_files_tool(
        self, mock_provider, session_with_project, mock_backend, temp_project
    ):
        """Test executing a list_files tool call."""
        supervisor = SupervisorAgent(
            mock_provider,
            session=session_with_project,
            backend=mock_backend,
        )

        tool_call = {"tool": "list_files", "path": ".", "pattern": "*.py"}
        result = await supervisor._execute_tool_call(tool_call)

        assert result["tool"] == "list_files"
        assert result["success"] is True
        assert result["data"]["total_files"] == 2  # main.py, utils.py

    @pytest.mark.asyncio
    async def test_execute_search_code_tool(
        self, mock_provider, session_with_project, mock_backend, temp_project
    ):
        """Test executing a search_code tool call."""
        supervisor = SupervisorAgent(
            mock_provider,
            session=session_with_project,
            backend=mock_backend,
        )

        tool_call = {"tool": "search_code", "pattern": "def"}
        result = await supervisor._execute_tool_call(tool_call)

        assert result["tool"] == "search_code"
        assert result["success"] is True
        assert result["data"]["total_matches"] >= 2  # main(), helper()

    @pytest.mark.asyncio
    async def test_execute_get_structure_tool(
        self, mock_provider, session_with_project, mock_backend, temp_project
    ):
        """Test executing a get_structure tool call."""
        supervisor = SupervisorAgent(
            mock_provider,
            session=session_with_project,
            backend=mock_backend,
        )

        tool_call = {"tool": "get_structure"}
        result = await supervisor._execute_tool_call(tool_call)

        assert result["tool"] == "get_structure"
        assert result["success"] is True
        assert result["data"]["total_files"] >= 3
        assert "src/" in result["data"]["tree"]

    @pytest.mark.asyncio
    async def test_execute_unknown_tool(
        self, mock_provider, session_with_project, mock_backend
    ):
        """Test that unknown tools return an error."""
        supervisor = SupervisorAgent(
            mock_provider,
            session=session_with_project,
            backend=mock_backend,
        )

        tool_call = {"tool": "unknown_tool"}
        result = await supervisor._execute_tool_call(tool_call)

        assert result["tool"] == "unknown_tool"
        assert result["success"] is False
        assert "Unknown tool" in result["error"]

    @pytest.mark.asyncio
    async def test_tool_without_filesystem_tools(self, mock_provider):
        """Test that tool calls fail gracefully without filesystem tools."""
        # Supervisor without session/backend
        supervisor = SupervisorAgent(mock_provider)

        tool_call = {"tool": "read_file", "path": "test.py"}
        result = await supervisor._execute_tool_call(tool_call)

        assert result["success"] is False
        assert "not available" in result["error"]

    def test_system_prompt_includes_tools_when_enabled(
        self, mock_provider, session_with_project, mock_backend
    ):
        """Test that system prompt includes tool descriptions when filesystem enabled."""
        supervisor = SupervisorAgent(
            mock_provider,
            session=session_with_project,
            backend=mock_backend,
        )

        prompt = supervisor._build_system_prompt()

        assert "Filesystem Tools" in prompt
        assert "read_file" in prompt
        assert "list_files" in prompt
        assert "search_code" in prompt
        assert "<tool_call>" in prompt

    def test_system_prompt_excludes_tools_when_disabled(self, mock_provider):
        """Test that system prompt excludes tools when filesystem not enabled."""
        supervisor = SupervisorAgent(mock_provider)

        prompt = supervisor._build_system_prompt()

        assert "Filesystem Tools" not in prompt


class TestProposalManagerIntegration:
    """Tests for proposal manager with database backend."""

    @pytest.fixture
    def temp_project(self, tmp_path: Path):
        """Create a temporary project directory."""
        (tmp_path / "existing.py").write_text("# Old content")
        return tmp_path

    @pytest.fixture
    def sqlite_backend(self, tmp_path: Path):
        """Create a real SQLite backend for testing."""
        from test_ai.state.backends import SQLiteBackend

        db_path = tmp_path / "test.db"
        backend = SQLiteBackend(str(db_path))

        # Create required tables
        backend.executescript("""
            CREATE TABLE IF NOT EXISTS chat_sessions (
                id TEXT PRIMARY KEY,
                title TEXT,
                project_path TEXT,
                mode TEXT,
                status TEXT,
                created_at TEXT,
                updated_at TEXT,
                metadata TEXT
            );

            CREATE TABLE IF NOT EXISTS edit_proposals (
                id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                file_path TEXT NOT NULL,
                old_content TEXT,
                new_content TEXT NOT NULL,
                description TEXT DEFAULT '',
                status TEXT DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                applied_at TIMESTAMP,
                error_message TEXT
            );

            CREATE TABLE IF NOT EXISTS file_access_log (
                id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                tool TEXT NOT NULL,
                file_path TEXT NOT NULL,
                operation TEXT NOT NULL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                success BOOLEAN DEFAULT TRUE,
                error_message TEXT
            );
        """)

        # Insert test session
        backend.execute(
            "INSERT INTO chat_sessions (id, title, status) VALUES (?, ?, ?)",
            ("test-session", "Test", "active"),
        )

        return backend

    def test_create_proposal(self, temp_project, sqlite_backend):
        """Test creating an edit proposal."""
        validator = PathValidator(temp_project)
        manager = ProposalManager(sqlite_backend, validator)

        proposal = manager.create_proposal(
            session_id="test-session",
            file_path="existing.py",
            new_content="# New content",
            description="Update file",
        )

        assert proposal.id is not None
        assert proposal.status == ProposalStatus.PENDING
        assert proposal.old_content == "# Old content"
        assert proposal.new_content == "# New content"

    def test_get_proposal(self, temp_project, sqlite_backend):
        """Test retrieving a proposal."""
        validator = PathValidator(temp_project)
        manager = ProposalManager(sqlite_backend, validator)

        created = manager.create_proposal(
            session_id="test-session",
            file_path="existing.py",
            new_content="# New content",
        )

        retrieved = manager.get_proposal(created.id)

        assert retrieved is not None
        assert retrieved.id == created.id
        assert retrieved.new_content == "# New content"

    def test_get_session_proposals(self, temp_project, sqlite_backend):
        """Test listing proposals for a session."""
        validator = PathValidator(temp_project)
        manager = ProposalManager(sqlite_backend, validator)

        # Create multiple proposals
        manager.create_proposal(
            session_id="test-session",
            file_path="existing.py",
            new_content="v1",
        )
        manager.create_proposal(
            session_id="test-session",
            file_path="existing.py",
            new_content="v2",
        )

        proposals = manager.get_session_proposals("test-session")

        assert len(proposals) == 2

    def test_approve_proposal(self, temp_project, sqlite_backend):
        """Test approving and applying a proposal."""
        validator = PathValidator(temp_project)
        manager = ProposalManager(sqlite_backend, validator)

        proposal = manager.create_proposal(
            session_id="test-session",
            file_path="existing.py",
            new_content="# Applied content",
        )

        approved = manager.approve_proposal(proposal.id)

        assert approved.status == ProposalStatus.APPLIED
        assert approved.applied_at is not None

        # Verify file was updated
        content = (temp_project / "existing.py").read_text()
        assert content == "# Applied content"

        # Verify backup was created
        backup = temp_project / "existing.py.bak"
        assert backup.exists()
        assert backup.read_text() == "# Old content"

    def test_reject_proposal(self, temp_project, sqlite_backend):
        """Test rejecting a proposal."""
        validator = PathValidator(temp_project)
        manager = ProposalManager(sqlite_backend, validator)

        proposal = manager.create_proposal(
            session_id="test-session",
            file_path="existing.py",
            new_content="# Should not be applied",
        )

        rejected = manager.reject_proposal(proposal.id)

        assert rejected.status == ProposalStatus.REJECTED

        # Verify file was NOT updated
        content = (temp_project / "existing.py").read_text()
        assert content == "# Old content"

    def test_cannot_approve_non_pending(self, temp_project, sqlite_backend):
        """Test that only pending proposals can be approved."""
        validator = PathValidator(temp_project)
        manager = ProposalManager(sqlite_backend, validator)

        proposal = manager.create_proposal(
            session_id="test-session",
            file_path="existing.py",
            new_content="content",
        )
        manager.reject_proposal(proposal.id)

        with pytest.raises(ValueError, match="not pending"):
            manager.approve_proposal(proposal.id)

    def test_filter_by_status(self, temp_project, sqlite_backend):
        """Test filtering proposals by status."""
        validator = PathValidator(temp_project)
        manager = ProposalManager(sqlite_backend, validator)

        p1 = manager.create_proposal(
            session_id="test-session",
            file_path="existing.py",
            new_content="v1",
        )
        p2 = manager.create_proposal(
            session_id="test-session",
            file_path="existing.py",
            new_content="v2",
        )
        manager.reject_proposal(p1.id)

        pending = manager.get_session_proposals("test-session", ProposalStatus.PENDING)
        rejected = manager.get_session_proposals("test-session", ProposalStatus.REJECTED)

        assert len(pending) == 1
        assert len(rejected) == 1
        assert pending[0].id == p2.id


class TestChatSessionFilesystem:
    """Tests for ChatSession filesystem fields."""

    def test_session_has_project_access_true(self):
        """Test has_project_access when enabled and path set."""
        session = ChatSession(
            id="test",
            project_path="/some/path",
            filesystem_enabled=True,
        )

        assert session.has_project_access is True

    def test_session_has_project_access_false_no_path(self):
        """Test has_project_access when path not set."""
        session = ChatSession(
            id="test",
            filesystem_enabled=True,
        )

        assert session.has_project_access is False

    def test_session_has_project_access_false_disabled(self):
        """Test has_project_access when disabled."""
        session = ChatSession(
            id="test",
            project_path="/some/path",
            filesystem_enabled=False,
        )

        assert session.has_project_access is False

    def test_session_from_db_row_auto_enables(self):
        """Test that from_db_row auto-enables filesystem when path present."""
        row = {
            "id": "test",
            "title": "Test",
            "project_path": "/some/path",
            "mode": "assistant",
            "status": "active",
            "created_at": "2024-01-01T00:00:00",
            "updated_at": "2024-01-01T00:00:00",
            "metadata": None,
        }

        session = ChatSession.from_db_row(row)

        assert session.filesystem_enabled is True
        assert session.has_project_access is True

    def test_session_from_db_row_with_allowed_paths(self):
        """Test that allowed_paths are extracted from metadata."""
        row = {
            "id": "test",
            "title": "Test",
            "project_path": "/main/path",
            "mode": "assistant",
            "status": "active",
            "created_at": "2024-01-01T00:00:00",
            "updated_at": "2024-01-01T00:00:00",
            "metadata": '{"allowed_paths": ["/extra/path1", "/extra/path2"]}',
        }

        session = ChatSession.from_db_row(row)

        assert session.allowed_paths == ["/extra/path1", "/extra/path2"]
