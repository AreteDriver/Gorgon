"""Scrollable message display with markdown and syntax highlighting."""

from __future__ import annotations

from textual.widgets import RichLog
from rich.markdown import Markdown
from rich.text import Text


class ChatDisplay(RichLog):
    """Scrollable chat message display.

    Uses RichLog for efficient append-only rendering with
    Rich markdown and syntax highlighting support.
    """

    DEFAULT_CSS = """
    ChatDisplay {
        height: 1fr;
        border: solid $surface-lighten-2;
        padding: 0 1;
        scrollbar-size: 1 1;
    }
    """

    def add_user_message(self, content: str) -> None:
        """Append a user message to the display."""
        label = Text("\n> You", style="bold cyan")
        self.write(label)
        self.write(Text(content))

    def add_assistant_message(self, content: str) -> None:
        """Append a complete assistant message (markdown rendered)."""
        label = Text("\n< Assistant", style="bold green")
        self.write(label)
        try:
            self.write(Markdown(content))
        except Exception:
            self.write(Text(content))

    def add_system_message(self, content: str) -> None:
        """Append a system/info message."""
        self.write(Text(f"\n[system] {content}", style="dim yellow"))

    def add_error_message(self, content: str) -> None:
        """Append an error message."""
        self.write(Text(f"\n[error] {content}", style="bold red"))

    def begin_assistant_stream(self) -> None:
        """Start a new assistant streaming response."""
        label = Text("\n< Assistant", style="bold green")
        self.write(label)

    def append_stream_chunk(self, text: str) -> None:
        """Append a chunk of streaming text."""
        self.write(Text(text, end=""))

    def end_assistant_stream(self, full_content: str) -> None:
        """Finalize a streamed response by re-rendering as markdown."""
        # Clear the raw text chunks and render properly
        # For now, just add a newline — the chunks are already displayed
        self.write(Text(""))

    def add_agent_message(self, role: str, content: str) -> None:
        """Append a message from a named agent role."""
        label = Text(f"\n[{role}]", style="bold magenta")
        self.write(label)
        try:
            self.write(Markdown(content))
        except Exception:
            self.write(Text(content))
