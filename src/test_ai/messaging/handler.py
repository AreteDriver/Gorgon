"""Message handler that routes bot messages to Gorgon's agent system."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from .base import BotMessage, BotUser, MessagePlatform

if TYPE_CHECKING:
    from test_ai.agents.supervisor import SupervisorAgent
    from test_ai.chat.session_manager import ChatSessionManager
    from test_ai.chat.models import ChatMode

logger = logging.getLogger(__name__)


class MessageHandler:
    """Routes incoming messages from messaging bots to Gorgon's agent system.

    This handler:
    1. Maps platform users to chat sessions
    2. Stores messages in the chat database
    3. Routes messages to the Supervisor agent for processing
    4. Returns agent responses to the messaging bot

    Usage:
        handler = MessageHandler(session_manager, supervisor)
        telegram_bot.set_message_callback(handler.handle_message)
        await telegram_bot.start()
    """

    def __init__(
        self,
        session_manager: "ChatSessionManager",
        supervisor: "SupervisorAgent | None" = None,
        default_mode: "ChatMode | None" = None,
    ):
        """Initialize the message handler.

        Args:
            session_manager: Chat session manager for storing messages.
            supervisor: Supervisor agent for processing messages.
            default_mode: Default chat mode for new sessions.
        """
        self.session_manager = session_manager
        self.supervisor = supervisor
        self.default_mode = default_mode

        # Cache: platform:user_id -> session_id
        self._user_sessions: dict[str, str] = {}

    def _get_or_create_session(
        self,
        user: BotUser,
        platform: MessagePlatform,
    ) -> str:
        """Get existing session or create new one for a user.

        Args:
            user: The messaging platform user.
            platform: The messaging platform.

        Returns:
            Session ID.
        """
        from test_ai.chat.models import ChatMode

        cache_key = user.identifier

        # Check cache first
        if cache_key in self._user_sessions:
            session_id = self._user_sessions[cache_key]
            # Verify session still exists
            session = self.session_manager.get_session(session_id)
            if session and session.status == "active":
                return session_id

        # Create new session
        title = f"{platform.value.title()} - {user.display_name or user.username or user.id}"
        mode = self.default_mode or ChatMode.ASSISTANT

        session = self.session_manager.create_session(
            title=title,
            mode=mode,
        )

        # Cache the session
        self._user_sessions[cache_key] = session.id
        logger.info(f"Created new session {session.id} for user {cache_key}")

        return session.id

    async def handle_message(self, message: BotMessage) -> str | None:
        """Handle an incoming message from a messaging platform.

        Args:
            message: The incoming bot message.

        Returns:
            Response text to send back, or None.
        """
        from test_ai.chat.models import MessageRole

        # Get or create session for this user
        session_id = self._get_or_create_session(message.user, message.platform)

        # Store the user message
        self.session_manager.add_message(
            session_id=session_id,
            role=MessageRole.USER,
            content=message.content,
            metadata={
                "platform": message.platform.value,
                "platform_user_id": message.user.id,
                "platform_message_id": message.id,
                "platform_chat_id": message.chat_id,
                "has_attachments": message.has_attachments,
            },
        )

        # Process through supervisor if available
        if self.supervisor:
            try:
                response = await self._process_with_supervisor(session_id, message)
            except Exception as e:
                logger.exception(f"Supervisor error: {e}")
                response = f"I encountered an error processing your request: {str(e)}"
        else:
            # Fallback response when no supervisor is configured
            response = (
                "Gorgon is running but no agent is configured to handle messages. "
                "Please set up the Supervisor agent."
            )

        # Store the assistant response
        if response:
            self.session_manager.add_message(
                session_id=session_id,
                role=MessageRole.ASSISTANT,
                content=response,
                agent="supervisor",
                metadata={
                    "platform": message.platform.value,
                    "in_reply_to": message.id,
                },
            )

        return response

    async def _process_with_supervisor(
        self,
        session_id: str,
        message: BotMessage,
    ) -> str:
        """Process a message through the Supervisor agent.

        Args:
            session_id: The chat session ID.
            message: The incoming message.

        Returns:
            Agent response text.
        """
        # Get conversation history for context
        messages = self.session_manager.get_messages(session_id, limit=20)

        # Format history for the supervisor
        history = []
        for msg in messages[:-1]:  # Exclude the message we just added
            history.append(
                {
                    "role": msg.role.value,
                    "content": msg.content,
                }
            )

        # Build context about the platform
        context = {
            "platform": message.platform.value,
            "user_id": message.user.id,
            "user_name": message.user.display_name or message.user.username,
            "is_admin": message.user.is_admin,
            "has_attachments": message.has_attachments,
        }

        # Process through supervisor
        # Note: This integrates with the existing Supervisor agent
        result = await self.supervisor.process(
            message=message.content,
            history=history,
            context=context,
        )

        return result.get("response", "I couldn't generate a response.")

    def get_session_for_user(self, user: BotUser) -> str | None:
        """Get the session ID for a user if it exists.

        Args:
            user: The messaging platform user.

        Returns:
            Session ID or None.
        """
        return self._user_sessions.get(user.identifier)

    def clear_session(self, user: BotUser) -> bool:
        """Clear the cached session for a user, forcing a new session on next message.

        Args:
            user: The messaging platform user.

        Returns:
            True if session was cleared, False if no session existed.
        """
        cache_key = user.identifier
        if cache_key in self._user_sessions:
            del self._user_sessions[cache_key]
            return True
        return False

    async def handle_command(
        self,
        message: BotMessage,
        command: str,
        args: list[str],
    ) -> str | None:
        """Handle a bot command.

        Args:
            message: The incoming message.
            command: Command name (without prefix).
            args: Command arguments.

        Returns:
            Response text or None.
        """
        handlers: dict[str, Any] = {
            "start": self._cmd_start,
            "help": self._cmd_help,
            "new": self._cmd_new_session,
            "status": self._cmd_status,
            "history": self._cmd_history,
        }

        handler = handlers.get(command.lower())
        if handler:
            return await handler(message, args)

        # Unknown command - treat as regular message
        return None

    async def _cmd_start(self, message: BotMessage, args: list[str]) -> str:
        """Handle /start command."""
        return (
            f"Hello! I'm {self.supervisor.name if self.supervisor else 'Gorgon'}, "
            "your AI assistant.\n\n"
            "I can help you with:\n"
            "- Answering questions\n"
            "- Running workflows\n"
            "- Managing tasks\n"
            "- And much more!\n\n"
            "Just send me a message to get started. "
            "Use /help to see available commands."
        )

    async def _cmd_help(self, message: BotMessage, args: list[str]) -> str:
        """Handle /help command."""
        return (
            "Available commands:\n\n"
            "/start - Start conversation\n"
            "/help - Show this help message\n"
            "/new - Start a new conversation session\n"
            "/status - Show current session status\n"
            "/history - Show recent messages\n\n"
            "You can also just send me a message directly!"
        )

    async def _cmd_new_session(self, message: BotMessage, args: list[str]) -> str:
        """Handle /new command to start a fresh session."""
        self.clear_session(message.user)
        return (
            "Started a new conversation session. "
            "Your previous conversation history is preserved but I'll start fresh."
        )

    async def _cmd_status(self, message: BotMessage, args: list[str]) -> str:
        """Handle /status command."""
        session_id = self.get_session_for_user(message.user)
        if not session_id:
            return "No active session. Send a message to start one."

        session = self.session_manager.get_session(session_id)
        if not session:
            return "Session not found. Send a message to start a new one."

        msg_count = self.session_manager.get_message_count(session_id)
        return (
            f"Session: {session.id[:8]}...\n"
            f"Title: {session.title}\n"
            f"Mode: {session.mode.value}\n"
            f"Status: {session.status}\n"
            f"Messages: {msg_count}\n"
            f"Created: {session.created_at.strftime('%Y-%m-%d %H:%M')}"
        )

    async def _cmd_history(self, message: BotMessage, args: list[str]) -> str:
        """Handle /history command — show recent task history."""
        limit = 5
        if args and args[0].isdigit():
            limit = min(int(args[0]), 20)

        try:
            from test_ai.db import get_task_store

            tasks = get_task_store().query_tasks(limit=limit)
            if tasks:
                lines = [f"Last {len(tasks)} tasks:\n"]
                for t in tasks:
                    status = t["status"]
                    wf = t["workflow_id"][:20]
                    agent = t.get("agent_role") or "?"
                    dur = f"{t['duration_ms']}ms" if t.get("duration_ms") else "-"
                    cost = f"${t['cost_usd']:.4f}" if t.get("cost_usd") else "-"
                    lines.append(f"[{status}] {wf} | {agent} | {dur} | {cost}")
                return "\n".join(lines)
        except Exception:
            pass

        # Fallback: show session messages
        session_id = self.get_session_for_user(message.user)
        if not session_id:
            return "No task history or active session."

        messages = self.session_manager.get_messages(session_id, limit=limit)
        if not messages:
            return "No task history or messages yet."

        lines = [f"Last {len(messages)} messages:\n"]
        for msg in messages:
            role = "You" if msg.role.value == "user" else "Gorgon"
            content = (
                msg.content[:100] + "..." if len(msg.content) > 100 else msg.content
            )
            lines.append(f"[{role}] {content}")

        return "\n".join(lines)
