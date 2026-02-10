"""Main Textual App for the Gorgon TUI."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from pathlib import Path

from textual.app import App
from textual.binding import Binding

from test_ai.tui.chat_screen import ChatScreen
from test_ai.tui.widgets.input_bar import InputBar

logger = logging.getLogger(__name__)

CSS_PATH = Path(__file__).parent / "styles.tcss"


class GorgonApp(App):
    """Gorgon TUI - Unified AI terminal interface.

    Unifies Claude, OpenAI, Ollama into a single interactive terminal app
    with streaming, file context, multi-agent orchestration, and session persistence.
    """

    TITLE = "Gorgon"
    SUB_TITLE = "AI Terminal Interface"
    CSS_PATH = CSS_PATH

    BINDINGS = [
        Binding("ctrl+q", "quit", "Quit", show=True, priority=True),
        Binding("ctrl+b", "toggle_sidebar", "Toggle Sidebar", show=True),
        Binding("ctrl+l", "clear_chat", "Clear Chat", show=True),
        Binding("ctrl+n", "new_session", "New Session", show=True),
        Binding("ctrl+c", "cancel_generation", "Cancel", show=True, priority=True),
    ]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._provider_manager = None
        self._messages: list[dict] = []
        self._system_prompt: str | None = None
        self._cancel_event: asyncio.Event = asyncio.Event()
        self._is_streaming: bool = False
        self._command_registry = None
        self._session = None
        self._agent_mode: str = "off"
        self._supervisor = None

    def on_mount(self) -> None:
        self.push_screen(ChatScreen(name="chat"))
        self._init_providers()

    def _init_providers(self) -> None:
        """Initialize provider manager from settings."""
        try:
            from test_ai.tui.providers import create_provider_manager

            self._provider_manager = create_provider_manager()
            provider = self._provider_manager.get_default()
            if provider:
                screen = self.screen
                if isinstance(screen, ChatScreen):
                    screen.sidebar.provider_name = provider.name
                    screen.sidebar.model_name = provider.default_model
                    screen.status_bar.provider_name = provider.name
                    screen.status_bar.model_name = provider.default_model
                    screen.chat_display.add_system_message(
                        f"Connected to {provider.name} ({provider.default_model}). Type a message or /help."
                    )
            else:
                screen = self.screen
                if isinstance(screen, ChatScreen):
                    screen.chat_display.add_error_message(
                        "No providers configured. Set API keys in .env"
                    )
        except Exception as e:
            logger.error(f"Failed to init providers: {e}")
            screen = self.screen
            if isinstance(screen, ChatScreen):
                screen.chat_display.add_error_message(f"Provider init failed: {e}")

    def _init_commands(self) -> None:
        """Lazy-init the command registry."""
        if self._command_registry is None:
            from test_ai.tui.commands import create_command_registry

            self._command_registry = create_command_registry(self)

    async def on_input_bar_submitted(self, event: InputBar.Submitted) -> None:
        """Handle user input submission."""
        value = event.value

        if event.is_command:
            await self._handle_command(value)
        else:
            await self._handle_chat_message(value)

    async def _handle_command(self, text: str) -> None:
        """Parse and execute a slash command."""
        self._init_commands()
        screen = self.screen
        if not isinstance(screen, ChatScreen):
            return

        parts = text[1:].split(None, 1)
        cmd_name = parts[0].lower() if parts else ""
        cmd_args = parts[1] if len(parts) > 1 else ""

        result = await self._command_registry.execute(cmd_name, cmd_args)
        if result:
            screen.chat_display.add_system_message(result)

    async def _handle_chat_message(self, content: str) -> None:
        """Send a chat message and stream the response."""
        screen = self.screen
        if not isinstance(screen, ChatScreen):
            return

        if not self._provider_manager:
            screen.chat_display.add_error_message("No providers configured.")
            return

        provider = self._provider_manager.get_default()
        if not provider:
            screen.chat_display.add_error_message("No default provider set.")
            return

        # Show user message
        screen.chat_display.add_user_message(content)
        self._messages.append(
            {
                "role": "user",
                "content": content,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        )

        # Check if we should use agent mode
        if self._agent_mode != "off" and self._agent_mode != "none":
            await self._handle_agent_message(content, screen)
            return

        # Stream response
        self._cancel_event.clear()
        self._is_streaming = True
        screen.status_bar.is_streaming = True
        screen.chat_display.begin_assistant_stream()

        full_response = ""
        try:
            from test_ai.tui.streaming import stream_completion

            # Build messages for the API
            api_messages = []
            if self._system_prompt:
                api_messages.append({"role": "system", "content": self._system_prompt})

            # Add file context
            file_context = self._build_file_context()
            if file_context:
                api_messages.append({"role": "system", "content": file_context})

            for msg in self._messages:
                api_messages.append({"role": msg["role"], "content": msg["content"]})

            async for chunk in stream_completion(provider, api_messages):
                if self._cancel_event.is_set():
                    screen.chat_display.append_stream_chunk("\n[cancelled]")
                    break
                full_response += chunk
                screen.chat_display.append_stream_chunk(chunk)

        except Exception as e:
            logger.error(f"Streaming error: {e}")
            screen.chat_display.add_error_message(str(e))
        finally:
            self._is_streaming = False
            screen.status_bar.is_streaming = False
            screen.chat_display.end_assistant_stream(full_response)

        if full_response:
            self._messages.append(
                {
                    "role": "assistant",
                    "content": full_response,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
            )

            # Auto-save session if active
            if self._session:
                try:
                    self._session.messages = self._messages
                    self._session.save()
                except Exception as e:
                    logger.debug(f"Auto-save failed: {e}")

    async def _handle_agent_message(self, content: str, screen: ChatScreen) -> None:
        """Handle a message in agent mode via SupervisorAgent."""
        if self._supervisor is None:
            try:
                from test_ai.agents.supervisor import SupervisorAgent

                provider = self._provider_manager.get_default()
                from test_ai.agents.provider_wrapper import AgentProvider

                agent_provider = AgentProvider(provider)
                self._supervisor = SupervisorAgent(provider=agent_provider)
            except Exception as e:
                screen.chat_display.add_error_message(f"Agent init failed: {e}")
                return

        self._cancel_event.clear()
        self._is_streaming = True
        screen.status_bar.is_streaming = True

        full_response = ""
        try:
            import uuid

            from test_ai.chat.models import ChatMessage

            session_id = str(uuid.uuid4())
            chat_messages = [
                ChatMessage(
                    id=str(uuid.uuid4()),
                    session_id=session_id,
                    role=m["role"],
                    content=m["content"],
                )
                for m in self._messages
            ]
            async for chunk in self._supervisor.process_message(content, chat_messages):
                if self._cancel_event.is_set():
                    break

                chunk_type = chunk.get("type", "text")
                chunk_content = chunk.get("content", "")
                chunk_agent = chunk.get("agent", "supervisor")

                if chunk_type == "text" and chunk_content:
                    if not full_response:
                        screen.chat_display.begin_assistant_stream()
                    full_response += chunk_content
                    screen.chat_display.append_stream_chunk(chunk_content)
                elif chunk_type == "agent":
                    screen.chat_display.add_agent_message(chunk_agent, chunk_content)
                elif chunk_type == "tool_result":
                    screen.chat_display.add_system_message(
                        f"[tool] {chunk_content[:200]}"
                    )
                elif chunk_type == "done":
                    break

        except Exception as e:
            logger.error(f"Agent error: {e}")
            screen.chat_display.add_error_message(str(e))
        finally:
            self._is_streaming = False
            screen.status_bar.is_streaming = False
            if full_response:
                screen.chat_display.end_assistant_stream(full_response)

        if full_response:
            self._messages.append(
                {
                    "role": "assistant",
                    "content": full_response,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
            )

    def _build_file_context(self) -> str:
        """Build file context string from attached files."""
        screen = self.screen
        if not isinstance(screen, ChatScreen):
            return ""

        files = screen.sidebar.files
        if not files:
            return ""

        parts = []
        for path in files:
            try:
                content = Path(path).read_text(errors="replace")
                if len(content) > 10_000:
                    content = content[:10_000] + "\n... (truncated)"
                parts.append(f"--- File: {path} ---\n{content}")
            except Exception as e:
                parts.append(f"--- File: {path} ---\n[Error reading: {e}]")

        return "\n\n".join(parts)

    def action_toggle_sidebar(self) -> None:
        """Toggle sidebar visibility."""
        screen = self.screen
        if isinstance(screen, ChatScreen):
            sidebar = screen.sidebar
            sidebar.display = not sidebar.display

    def action_clear_chat(self) -> None:
        """Clear chat display and messages."""
        screen = self.screen
        if isinstance(screen, ChatScreen):
            screen.chat_display.clear()
            self._messages.clear()
            screen.sidebar.input_tokens = 0
            screen.sidebar.output_tokens = 0
            screen.chat_display.add_system_message("Chat cleared.")

    def action_new_session(self) -> None:
        """Start a new session."""
        self.action_clear_chat()
        self._session = None
        self._system_prompt = None
        screen = self.screen
        if isinstance(screen, ChatScreen):
            screen.sidebar.clear_files()
            screen.chat_display.add_system_message("New session started.")

    def action_cancel_generation(self) -> None:
        """Cancel ongoing generation."""
        if self._is_streaming:
            self._cancel_event.set()
