"""Tests for MCP connector management."""

import pytest
from test_ai.mcp import (
    MCPConnectorManager,
    MCPServerCreateInput,
    CredentialCreateInput,
)
from test_ai.state import SQLiteBackend


@pytest.fixture
def backend(tmp_path):
    """Create a test database backend."""
    db_path = tmp_path / "test.db"
    backend = SQLiteBackend(str(db_path))

    # Run schema migration
    schema = """
    CREATE TABLE IF NOT EXISTS mcp_servers (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        url TEXT NOT NULL,
        type TEXT NOT NULL DEFAULT 'sse',
        status TEXT NOT NULL DEFAULT 'not_configured',
        description TEXT DEFAULT '',
        auth_type TEXT NOT NULL DEFAULT 'none',
        credential_id TEXT,
        tools TEXT DEFAULT '[]',
        resources TEXT DEFAULT '[]',
        last_connected TIMESTAMP,
        error TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS credentials (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        type TEXT NOT NULL,
        service TEXT NOT NULL,
        encrypted_value TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        last_used TIMESTAMP
    );
    """
    backend.executescript(schema)
    return backend


@pytest.fixture
def manager(backend):
    """Create an MCP manager with test backend."""
    return MCPConnectorManager(backend)


class TestMCPServerCRUD:
    """Tests for MCP server CRUD operations."""

    def test_create_server(self, manager):
        """Test creating an MCP server."""
        data = MCPServerCreateInput(
            name="GitHub",
            url="https://mcp.github.com/sse",
            type="sse",
            authType="bearer",
            description="GitHub MCP server",
        )
        server = manager.create_server(data)

        assert server is not None
        assert server.id is not None
        assert server.name == "GitHub"
        assert server.url == "https://mcp.github.com/sse"
        assert server.type == "sse"
        assert server.authType == "bearer"
        assert server.status == "not_configured"  # No credential

    def test_create_server_no_auth(self, manager):
        """Test creating server without auth requirement."""
        data = MCPServerCreateInput(
            name="Filesystem",
            url="stdio://mcp-filesystem",
            type="stdio",
            authType="none",
        )
        server = manager.create_server(data)

        assert server.status == "disconnected"  # Ready to connect

    def test_list_servers(self, manager):
        """Test listing servers."""
        # Create multiple servers
        manager.create_server(
            MCPServerCreateInput(name="Server1", url="https://s1.com", type="sse")
        )
        manager.create_server(
            MCPServerCreateInput(name="Server2", url="https://s2.com", type="sse")
        )

        servers = manager.list_servers()
        assert len(servers) == 2
        names = [s.name for s in servers]
        assert "Server1" in names
        assert "Server2" in names

    def test_get_server(self, manager):
        """Test getting a specific server."""
        created = manager.create_server(
            MCPServerCreateInput(name="TestServer", url="https://test.com", type="sse")
        )

        fetched = manager.get_server(created.id)
        assert fetched is not None
        assert fetched.id == created.id
        assert fetched.name == "TestServer"

    def test_get_server_not_found(self, manager):
        """Test getting non-existent server."""
        result = manager.get_server("nonexistent-id")
        assert result is None

    def test_update_server(self, manager):
        """Test updating a server."""
        from test_ai.mcp.models import MCPServerUpdateInput

        created = manager.create_server(
            MCPServerCreateInput(name="Original", url="https://test.com", type="sse")
        )

        updated = manager.update_server(
            created.id, MCPServerUpdateInput(name="Updated", description="New desc")
        )

        assert updated is not None
        assert updated.name == "Updated"
        assert updated.description == "New desc"
        assert updated.url == "https://test.com"  # Unchanged

    def test_delete_server(self, manager):
        """Test deleting a server."""
        created = manager.create_server(
            MCPServerCreateInput(name="ToDelete", url="https://test.com", type="sse")
        )

        result = manager.delete_server(created.id)
        assert result is True

        # Verify deleted
        fetched = manager.get_server(created.id)
        assert fetched is None

    def test_delete_server_not_found(self, manager):
        """Test deleting non-existent server."""
        result = manager.delete_server("nonexistent-id")
        assert result is False


class TestConnectionTest:
    """Tests for connection testing."""

    def test_connection_test_no_auth_required(self, manager):
        """Test connection with server that doesn't require auth."""
        server = manager.create_server(
            MCPServerCreateInput(
                name="Filesystem",
                url="stdio://mcp-filesystem",
                type="stdio",
                authType="none",
            )
        )

        result = manager.test_connection(server.id)
        assert result.success is True
        assert result.error is None
        # Should discover simulated tools for filesystem
        assert len(result.tools) > 0

    def test_connection_test_missing_credentials(self, manager):
        """Test connection when credentials are required but missing."""
        server = manager.create_server(
            MCPServerCreateInput(
                name="GitHub",
                url="https://mcp.github.com/sse",
                type="sse",
                authType="bearer",
            )
        )

        result = manager.test_connection(server.id)
        assert result.success is False
        assert "Credentials required" in result.error

    def test_connection_test_not_found(self, manager):
        """Test connection for non-existent server."""
        result = manager.test_connection("nonexistent-id")
        assert result.success is False
        assert "not found" in result.error.lower()


class TestCredentials:
    """Tests for credential management."""

    def test_create_credential(self, manager):
        """Test creating a credential."""
        data = CredentialCreateInput(
            name="GitHub Token",
            type="bearer",
            service="github",
            value="ghp_xxxxxxxxxxxx",
        )
        credential = manager.create_credential(data)

        assert credential is not None
        assert credential.id is not None
        assert credential.name == "GitHub Token"
        assert credential.type == "bearer"
        assert credential.service == "github"
        # Value should not be exposed
        assert (
            not hasattr(credential, "value")
            or credential.model_dump().get("value") is None
        )

    def test_list_credentials(self, manager):
        """Test listing credentials."""
        manager.create_credential(
            CredentialCreateInput(
                name="Cred1", type="bearer", service="s1", value="xxx"
            )
        )
        manager.create_credential(
            CredentialCreateInput(
                name="Cred2", type="api_key", service="s2", value="yyy"
            )
        )

        credentials = manager.list_credentials()
        assert len(credentials) == 2

    def test_get_credential_value(self, manager):
        """Test retrieving credential value (internal use)."""
        created = manager.create_credential(
            CredentialCreateInput(
                name="Test", type="bearer", service="test", value="secret123"
            )
        )

        # Internal method to retrieve decrypted value
        value = manager.get_credential_value(created.id)
        assert value == "secret123"

    def test_delete_credential(self, manager):
        """Test deleting a credential."""
        created = manager.create_credential(
            CredentialCreateInput(
                name="ToDelete", type="bearer", service="x", value="y"
            )
        )

        result = manager.delete_credential(created.id)
        assert result is True

        fetched = manager.get_credential(created.id)
        assert fetched is None

    def test_delete_credential_updates_servers(self, manager):
        """Test that deleting credential updates referencing servers."""
        # Create credential
        cred = manager.create_credential(
            CredentialCreateInput(
                name="Token", type="bearer", service="github", value="xxx"
            )
        )

        # Create server with this credential
        server = manager.create_server(
            MCPServerCreateInput(
                name="GitHub",
                url="https://mcp.github.com",
                type="sse",
                authType="bearer",
                credentialId=cred.id,
            )
        )

        # Delete credential
        manager.delete_credential(cred.id)

        # Server should be updated
        updated_server = manager.get_server(server.id)
        assert updated_server.credentialId is None
        assert updated_server.status == "not_configured"
