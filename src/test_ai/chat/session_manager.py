"""Chat session manager for CRUD operations."""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from .models import (
    ChatMessage,
    ChatMode,
    ChatSession,
    MessageRole,
)

if TYPE_CHECKING:
    from test_ai.state.backends import DatabaseBackend

logger = logging.getLogger(__name__)


class ChatSessionManager:
    """Manages chat sessions and messages."""

    def __init__(self, backend: "DatabaseBackend"):
        """Initialize with database backend.

        Args:
            backend: Database backend instance.
        """
        self.backend = backend

    def create_session(
        self,
        title: str | None = None,
        project_path: str | None = None,
        mode: ChatMode = ChatMode.ASSISTANT,
    ) -> ChatSession:
        """Create a new chat session.

        Args:
            title: Optional session title.
            project_path: Optional project path for context.
            mode: Chat mode (assistant or self_improve).

        Returns:
            Created ChatSession.
        """
        session_id = str(uuid.uuid4())
        now = datetime.now()
        title = title or "New Chat"

        query = """
            INSERT INTO chat_sessions (id, title, project_path, mode, status, created_at, updated_at)
            VALUES (?, ?, ?, ?, 'active', ?, ?)
        """
        self.backend.execute(
            self.backend.adapt_query(query),
            (
                session_id,
                title,
                project_path,
                mode.value,
                now.isoformat(),
                now.isoformat(),
            ),
        )

        logger.info(f"Created chat session: {session_id}")
        return ChatSession(
            id=session_id,
            title=title,
            project_path=project_path,
            mode=mode,
            status="active",
            created_at=now,
            updated_at=now,
        )

    def get_session(self, session_id: str) -> ChatSession | None:
        """Get a session by ID.

        Args:
            session_id: The session ID.

        Returns:
            ChatSession if found, None otherwise.
        """
        query = "SELECT * FROM chat_sessions WHERE id = ?"
        row = self.backend.fetchone(self.backend.adapt_query(query), (session_id,))
        if not row:
            return None
        return ChatSession.from_db_row(dict(row))

    def get_session_with_messages(self, session_id: str) -> ChatSession | None:
        """Get a session with all its messages.

        Args:
            session_id: The session ID.

        Returns:
            ChatSession with messages if found, None otherwise.
        """
        session = self.get_session(session_id)
        if not session:
            return None

        query = """
            SELECT * FROM chat_messages
            WHERE session_id = ?
            ORDER BY created_at ASC
        """
        rows = self.backend.fetchall(self.backend.adapt_query(query), (session_id,))
        session.messages = [ChatMessage.from_db_row(dict(row)) for row in rows]
        return session

    def list_sessions(
        self,
        status: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[ChatSession]:
        """List chat sessions.

        Args:
            status: Optional filter by status.
            limit: Maximum sessions to return.
            offset: Number of sessions to skip.

        Returns:
            List of ChatSessions.
        """
        if status:
            query = """
                SELECT * FROM chat_sessions
                WHERE status = ?
                ORDER BY updated_at DESC
                LIMIT ? OFFSET ?
            """
            rows = self.backend.fetchall(
                self.backend.adapt_query(query), (status, limit, offset)
            )
        else:
            query = """
                SELECT * FROM chat_sessions
                ORDER BY updated_at DESC
                LIMIT ? OFFSET ?
            """
            rows = self.backend.fetchall(
                self.backend.adapt_query(query), (limit, offset)
            )

        return [ChatSession.from_db_row(dict(row)) for row in rows]

    def update_session(
        self,
        session_id: str,
        title: str | None = None,
        status: str | None = None,
    ) -> ChatSession | None:
        """Update a session.

        Args:
            session_id: The session ID.
            title: New title if updating.
            status: New status if updating.

        Returns:
            Updated ChatSession if found, None otherwise.
        """
        session = self.get_session(session_id)
        if not session:
            return None

        updates = []
        params = []
        if title is not None:
            updates.append("title = ?")
            params.append(title)
        if status is not None:
            updates.append("status = ?")
            params.append(status)

        if not updates:
            return session

        updates.append("updated_at = ?")
        params.append(datetime.now().isoformat())
        params.append(session_id)

        query = f"UPDATE chat_sessions SET {', '.join(updates)} WHERE id = ?"
        self.backend.execute(self.backend.adapt_query(query), tuple(params))

        return self.get_session(session_id)

    def delete_session(self, session_id: str) -> bool:
        """Delete a session and all its messages.

        Args:
            session_id: The session ID.

        Returns:
            True if deleted, False if not found.
        """
        session = self.get_session(session_id)
        if not session:
            return False

        # Messages are deleted by CASCADE
        query = "DELETE FROM chat_sessions WHERE id = ?"
        self.backend.execute(self.backend.adapt_query(query), (session_id,))
        logger.info(f"Deleted chat session: {session_id}")
        return True

    def add_message(
        self,
        session_id: str,
        role: MessageRole,
        content: str,
        agent: str | None = None,
        job_id: str | None = None,
        token_count: int | None = None,
        metadata: dict | None = None,
    ) -> ChatMessage:
        """Add a message to a session.

        Args:
            session_id: The session ID.
            role: Message role (user, assistant, system).
            content: Message content.
            agent: Optional agent name.
            job_id: Optional linked job ID.
            token_count: Optional token count.
            metadata: Optional additional metadata.

        Returns:
            Created ChatMessage.
        """
        message_id = str(uuid.uuid4())
        now = datetime.now()

        query = """
            INSERT INTO chat_messages (id, session_id, role, content, agent, job_id, token_count, created_at, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        self.backend.execute(
            self.backend.adapt_query(query),
            (
                message_id,
                session_id,
                role.value,
                content,
                agent,
                job_id,
                token_count,
                now.isoformat(),
                json.dumps(metadata) if metadata else None,
            ),
        )

        # Update session's updated_at
        update_query = "UPDATE chat_sessions SET updated_at = ? WHERE id = ?"
        self.backend.execute(
            self.backend.adapt_query(update_query), (now.isoformat(), session_id)
        )

        return ChatMessage(
            id=message_id,
            session_id=session_id,
            role=role,
            content=content,
            agent=agent,
            job_id=job_id,
            token_count=token_count,
            created_at=now,
            metadata=metadata or {},
        )

    def get_messages(
        self,
        session_id: str,
        limit: int | None = None,
        before_id: str | None = None,
    ) -> list[ChatMessage]:
        """Get messages for a session.

        Args:
            session_id: The session ID.
            limit: Maximum messages to return.
            before_id: Get messages before this message ID.

        Returns:
            List of ChatMessages.
        """
        if before_id:
            # Get the created_at of the reference message
            ref_query = "SELECT created_at FROM chat_messages WHERE id = ?"
            ref_row = self.backend.fetchone(
                self.backend.adapt_query(ref_query), (before_id,)
            )
            if not ref_row:
                return []

            query = """
                SELECT * FROM chat_messages
                WHERE session_id = ? AND created_at < ?
                ORDER BY created_at DESC
                LIMIT ?
            """
            params = (session_id, ref_row["created_at"], limit or 50)
        else:
            query = """
                SELECT * FROM chat_messages
                WHERE session_id = ?
                ORDER BY created_at ASC
            """
            params = (session_id,)
            if limit:
                query += " LIMIT ?"
                params = (session_id, limit)

        rows = self.backend.fetchall(self.backend.adapt_query(query), params)
        return [ChatMessage.from_db_row(dict(row)) for row in rows]

    def link_job(self, session_id: str, job_id: str) -> None:
        """Link a job to a session.

        Args:
            session_id: The session ID.
            job_id: The job ID.
        """
        query = """
            INSERT OR IGNORE INTO chat_session_jobs (session_id, job_id)
            VALUES (?, ?)
        """
        self.backend.execute(self.backend.adapt_query(query), (session_id, job_id))

    def get_session_jobs(self, session_id: str) -> list[str]:
        """Get job IDs linked to a session.

        Args:
            session_id: The session ID.

        Returns:
            List of job IDs.
        """
        query = """
            SELECT job_id FROM chat_session_jobs
            WHERE session_id = ?
            ORDER BY created_at DESC
        """
        rows = self.backend.fetchall(self.backend.adapt_query(query), (session_id,))
        return [row["job_id"] for row in rows]

    def get_message_count(self, session_id: str) -> int:
        """Get the number of messages in a session.

        Args:
            session_id: The session ID.

        Returns:
            Message count.
        """
        query = "SELECT COUNT(*) as count FROM chat_messages WHERE session_id = ?"
        row = self.backend.fetchone(self.backend.adapt_query(query), (session_id,))
        return row["count"] if row else 0

    def generate_title(self, session_id: str) -> str:
        """Generate a title from the first user message.

        Args:
            session_id: The session ID.

        Returns:
            Generated title (first 50 chars of first user message).
        """
        query = """
            SELECT content FROM chat_messages
            WHERE session_id = ? AND role = 'user'
            ORDER BY created_at ASC
            LIMIT 1
        """
        row = self.backend.fetchone(self.backend.adapt_query(query), (session_id,))
        if row:
            content = row["content"][:50]
            if len(row["content"]) > 50:
                content += "..."
            return content
        return "New Chat"
