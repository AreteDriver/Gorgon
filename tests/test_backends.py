"""Tests for database backends."""

import pytest
import tempfile
import os
import sys
sys.path.insert(0, 'src')

from test_ai.state.backends import (
    SQLiteBackend,
    create_backend,
)


class TestSQLiteBackend:
    """Tests for SQLiteBackend class."""

    @pytest.fixture
    def backend(self):
        """Create a temporary SQLite backend."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            backend = SQLiteBackend(db_path=db_path)
            yield backend
            backend.close()

    def test_execute_create_table(self, backend):
        """Can create tables."""
        backend.executescript("""
            CREATE TABLE test (
                id INTEGER PRIMARY KEY,
                name TEXT
            )
        """)
        # Should not raise
        backend.execute("INSERT INTO test (name) VALUES (?)", ("test",))

    def test_fetchone(self, backend):
        """Can fetch one row."""
        backend.executescript("CREATE TABLE test (id INTEGER PRIMARY KEY, name TEXT)")
        backend.execute("INSERT INTO test (name) VALUES (?)", ("alice",))

        row = backend.fetchone("SELECT * FROM test WHERE name = ?", ("alice",))
        assert row is not None
        assert row["name"] == "alice"

    def test_fetchone_no_result(self, backend):
        """Fetchone returns None when no match."""
        backend.executescript("CREATE TABLE test (id INTEGER PRIMARY KEY, name TEXT)")

        row = backend.fetchone("SELECT * FROM test WHERE name = ?", ("missing",))
        assert row is None

    def test_fetchall(self, backend):
        """Can fetch all rows."""
        backend.executescript("CREATE TABLE test (id INTEGER PRIMARY KEY, name TEXT)")
        backend.execute("INSERT INTO test (name) VALUES (?)", ("alice",))
        backend.execute("INSERT INTO test (name) VALUES (?)", ("bob",))

        rows = backend.fetchall("SELECT * FROM test ORDER BY name")
        assert len(rows) == 2
        assert rows[0]["name"] == "alice"
        assert rows[1]["name"] == "bob"

    def test_transaction_commit(self, backend):
        """Transaction commits on success."""
        backend.executescript("CREATE TABLE test (id INTEGER PRIMARY KEY, name TEXT)")

        with backend.transaction():
            backend.execute("INSERT INTO test (name) VALUES (?)", ("test",))

        row = backend.fetchone("SELECT * FROM test")
        assert row is not None

    def test_transaction_rollback(self, backend):
        """Transaction rolls back on error."""
        backend.executescript("CREATE TABLE test (id INTEGER PRIMARY KEY, name TEXT)")

        with pytest.raises(ValueError):
            with backend.transaction():
                backend.execute("INSERT INTO test (name) VALUES (?)", ("test",))
                raise ValueError("Simulated error")

        row = backend.fetchone("SELECT * FROM test")
        assert row is None

    def test_placeholder(self, backend):
        """SQLite uses ? placeholder."""
        assert backend.placeholder == "?"

    def test_adapt_query(self, backend):
        """SQLite doesn't change query placeholders."""
        query = "SELECT * FROM test WHERE id = ?"
        assert backend.adapt_query(query) == query


class TestCreateBackend:
    """Tests for create_backend function."""

    def test_sqlite_url(self):
        """Can create SQLite backend from URL."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            backend = create_backend(f"sqlite:///{db_path}")
            assert isinstance(backend, SQLiteBackend)
            backend.close()

    def test_sqlite_default(self):
        """Creates SQLite backend by default."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            backend = create_backend(db_path=db_path)
            assert isinstance(backend, SQLiteBackend)
            backend.close()

    def test_unknown_scheme_raises(self):
        """Unknown URL scheme raises ValueError."""
        with pytest.raises(ValueError) as exc:
            create_backend("mysql://localhost/test")
        assert "Unsupported" in str(exc.value)

    def test_postgres_url_requires_psycopg2(self):
        """PostgreSQL URL requires psycopg2."""
        # This will either work (if psycopg2 installed) or raise ImportError
        try:
            backend = create_backend("postgresql://user:pass@localhost/test")
            backend.close()
        except ImportError as e:
            assert "psycopg2" in str(e)
