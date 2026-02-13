"""Messaging bot commands — Telegram, Discord."""

from __future__ import annotations

import typer
from rich.panel import Panel
from rich.table import Table

from ..helpers import console

bot_app = typer.Typer(help="Run messaging bots for 24/7 AI assistant")


@bot_app.command("telegram")
def bot_telegram(
    token: str = typer.Option(
        None, "--token", "-t", envvar="TELEGRAM_BOT_TOKEN", help="Telegram bot token"
    ),
    allowed_users: str = typer.Option(
        None,
        "--allowed",
        "-a",
        envvar="TELEGRAM_ALLOWED_USERS",
        help="Comma-separated allowed user IDs",
    ),
    admin_users: str = typer.Option(
        None,
        "--admins",
        envvar="TELEGRAM_ADMIN_USERS",
        help="Comma-separated admin user IDs",
    ),
):
    """Start Telegram bot for two-way messaging.

    This enables Clawdbot-style operation where Gorgon acts as a
    24/7 personal AI assistant via Telegram.

    Example:
        gorgon bot telegram --token YOUR_BOT_TOKEN
        gorgon bot telegram  # Uses TELEGRAM_BOT_TOKEN env var

    Setup:
        1. Message @BotFather on Telegram to create a bot
        2. Copy the token and set TELEGRAM_BOT_TOKEN
        3. Optionally set TELEGRAM_ALLOWED_USERS to restrict access
    """
    import asyncio

    if not token:
        console.print("[red]Telegram bot token required.[/red]")
        console.print("\nSet TELEGRAM_BOT_TOKEN environment variable or use --token")
        console.print("\nTo get a token:")
        console.print("  1. Open Telegram and message @BotFather")
        console.print("  2. Send /newbot and follow the prompts")
        console.print("  3. Copy the token you receive")
        raise typer.Exit(1)

    try:
        from test_ai.messaging import TelegramBot, MessageHandler
        from test_ai.chat import ChatSessionManager
        from test_ai.state.backends import get_backend
    except ImportError as e:
        console.print(f"[red]Missing dependencies:[/red] {e}")
        console.print("\nInstall with: pip install 'gorgon[messaging]'")
        console.print("Or: pip install python-telegram-bot")
        raise typer.Exit(1)

    # Parse user lists
    allowed = (
        [u.strip() for u in allowed_users.split(",") if u.strip()]
        if allowed_users
        else None
    )
    admins = (
        [u.strip() for u in admin_users.split(",") if u.strip()]
        if admin_users
        else None
    )

    console.print(
        Panel(
            "[bold]Telegram Bot Starting[/bold]\n\n"
            f"Allowed Users: {len(allowed) if allowed else 'All'}\n"
            f"Admin Users: {len(admins) if admins else 'None'}",
            title="Gorgon Messaging",
            border_style="cyan",
        )
    )

    async def run_bot():
        # Initialize components
        backend = get_backend()
        session_manager = ChatSessionManager(backend)

        # Create bot
        bot = TelegramBot(
            token=token,
            name="Gorgon",
            allowed_users=allowed,
            admin_users=admins,
        )

        # Create message handler
        handler = MessageHandler(session_manager)
        bot.set_message_callback(handler.handle_message)
        bot.set_command_handler(handler)

        console.print("[green]Bot started! Listening for messages...[/green]")
        console.print("[dim]Press Ctrl+C to stop[/dim]\n")

        try:
            await bot.start()
            # Keep running until interrupted
            while bot.is_running:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            console.print("\n[yellow]Shutting down...[/yellow]")
        finally:
            await bot.stop()
            console.print("[green]Bot stopped[/green]")

    try:
        asyncio.run(run_bot())
    except Exception as e:
        console.print(f"[red]Bot error:[/red] {e}")
        raise typer.Exit(1)


@bot_app.command("discord")
def bot_discord(
    token: str = typer.Option(
        None, "--token", "-t", envvar="DISCORD_BOT_TOKEN", help="Discord bot token"
    ),
    allowed_users: str = typer.Option(
        None,
        "--allowed",
        "-a",
        envvar="DISCORD_ALLOWED_USERS",
        help="Comma-separated allowed user IDs",
    ),
    admin_users: str = typer.Option(
        None,
        "--admins",
        envvar="DISCORD_ADMIN_USERS",
        help="Comma-separated admin user IDs",
    ),
    allowed_guilds: str = typer.Option(
        None,
        "--guilds",
        "-g",
        envvar="DISCORD_ALLOWED_GUILDS",
        help="Comma-separated guild IDs to operate in",
    ),
):
    """Start Discord bot for two-way messaging.

    The bot responds to:
    - Direct messages (DMs)
    - Mentions in channels (@Gorgon)
    - Commands with prefix (default: !)

    Example:
        gorgon bot discord --token YOUR_BOT_TOKEN
        gorgon bot discord  # Uses DISCORD_BOT_TOKEN env var

    Setup:
        1. Go to https://discord.com/developers/applications
        2. Create a new application and add a bot
        3. Enable MESSAGE CONTENT INTENT in bot settings
        4. Copy the bot token
        5. Invite bot with: /oauth2/authorize?client_id=YOUR_CLIENT_ID&scope=bot&permissions=68608
    """
    import asyncio

    if not token:
        console.print("[red]Discord bot token required.[/red]")
        console.print("\nSet DISCORD_BOT_TOKEN environment variable or use --token")
        console.print("\nTo get a token:")
        console.print("  1. Go to https://discord.com/developers/applications")
        console.print("  2. Create a new application")
        console.print("  3. Go to 'Bot' section and click 'Add Bot'")
        console.print("  4. Enable 'MESSAGE CONTENT INTENT'")
        console.print("  5. Copy the token")
        raise typer.Exit(1)

    try:
        from test_ai.messaging import DiscordBot, MessageHandler
        from test_ai.chat import ChatSessionManager
        from test_ai.state.backends import get_backend
    except ImportError as e:
        console.print(f"[red]Missing dependencies:[/red] {e}")
        console.print("\nInstall with: pip install 'gorgon[messaging]'")
        console.print("Or: pip install discord.py")
        raise typer.Exit(1)

    # Parse user/guild lists
    allowed = (
        [u.strip() for u in allowed_users.split(",") if u.strip()]
        if allowed_users
        else None
    )
    admins = (
        [u.strip() for u in admin_users.split(",") if u.strip()]
        if admin_users
        else None
    )
    guilds = (
        [g.strip() for g in allowed_guilds.split(",") if g.strip()]
        if allowed_guilds
        else None
    )

    console.print(
        Panel(
            "[bold]Discord Bot Starting[/bold]\n\n"
            f"Allowed Users: {len(allowed) if allowed else 'All'}\n"
            f"Admin Users: {len(admins) if admins else 'None'}\n"
            f"Allowed Guilds: {len(guilds) if guilds else 'All'}",
            title="Gorgon Messaging",
            border_style="blue",
        )
    )

    async def run_bot():
        # Initialize components
        backend = get_backend()
        session_manager = ChatSessionManager(backend)

        # Create bot
        bot = DiscordBot(
            token=token,
            name="Gorgon",
            allowed_users=allowed,
            admin_users=admins,
            allowed_guilds=guilds,
        )

        # Create message handler
        handler = MessageHandler(session_manager)
        bot.set_message_callback(handler.handle_message)
        bot.set_command_handler(handler)

        console.print("[green]Bot started! Listening for messages...[/green]")
        console.print("[dim]Responds to: DMs, @mentions, and !commands[/dim]")
        console.print("[dim]Press Ctrl+C to stop[/dim]\n")

        try:
            await bot.start()
        except KeyboardInterrupt:
            console.print("\n[yellow]Shutting down...[/yellow]")
        finally:
            await bot.stop()
            console.print("[green]Bot stopped[/green]")

    try:
        asyncio.run(run_bot())
    except Exception as e:
        console.print(f"[red]Bot error:[/red] {e}")
        raise typer.Exit(1)


@bot_app.command("status")
def bot_status() -> None:
    """Show messaging bot configuration status."""
    import os

    console.print("[bold]Messaging Bot Configuration[/bold]\n")

    # Check Telegram
    telegram_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    telegram_users = os.environ.get("TELEGRAM_ALLOWED_USERS")
    telegram_admins = os.environ.get("TELEGRAM_ADMIN_USERS")

    table = Table(title="Telegram")
    table.add_column("Setting", style="cyan")
    table.add_column("Status")

    table.add_row(
        "TELEGRAM_BOT_TOKEN",
        "[green]Configured[/green]" if telegram_token else "[red]Not set[/red]",
    )
    table.add_row(
        "TELEGRAM_ALLOWED_USERS",
        f"[green]{len(telegram_users.split(','))} users[/green]"
        if telegram_users
        else "[dim]All users allowed[/dim]",
    )
    table.add_row(
        "TELEGRAM_ADMIN_USERS",
        f"[green]{len(telegram_admins.split(','))} admins[/green]"
        if telegram_admins
        else "[dim]None[/dim]",
    )

    console.print(table)

    # Check dependencies
    console.print("\n[bold]Dependencies[/bold]\n")

    deps = [
        ("python-telegram-bot", "telegram"),
        ("discord.py", "discord"),
        ("playwright", "playwright"),
    ]

    for name, module in deps:
        try:
            __import__(module)
            console.print(f"  [green]✓[/green] {name}")
        except ImportError:
            console.print(f"  [dim]○[/dim] {name} (not installed)")

    console.print(
        "\n[dim]Install messaging deps: pip install 'gorgon[messaging]'[/dim]"
    )


@bot_app.command("setup")
def bot_setup() -> None:
    """Interactive setup for messaging bots."""
    console.print(
        Panel(
            "[bold]Messaging Bot Setup[/bold]\n\n"
            "This will guide you through setting up messaging bots.",
            border_style="cyan",
        )
    )

    # Telegram setup
    console.print("\n[bold]1. Telegram Setup[/bold]\n")
    console.print("To create a Telegram bot:")
    console.print("  1. Open Telegram and message @BotFather")
    console.print("  2. Send /newbot")
    console.print("  3. Choose a name (e.g., 'My Gorgon Assistant')")
    console.print("  4. Choose a username (must end in 'bot', e.g., 'my_gorgon_bot')")
    console.print("  5. Copy the API token")
    console.print()

    if typer.confirm("Do you have a Telegram bot token?"):
        token = typer.prompt("Enter your Telegram bot token", hide_input=True)

        # Validate token format
        if ":" not in token or len(token) < 40:
            console.print("[yellow]Warning: Token format looks unusual[/yellow]")

        console.print("\n[green]Add this to your .env file:[/green]")
        console.print(f"  TELEGRAM_BOT_TOKEN={token}")

        # Get user ID
        console.print("\n[dim]To find your Telegram user ID:[/dim]")
        console.print("  1. Message @userinfobot on Telegram")
        console.print("  2. It will reply with your user ID")
        console.print()

        if typer.confirm("Do you want to restrict bot access to specific users?"):
            user_ids = typer.prompt("Enter comma-separated user IDs")
            console.print(f"  TELEGRAM_ALLOWED_USERS={user_ids}")

        console.print("\n[green]✓ Telegram configuration ready[/green]")
        console.print("\nStart the bot with:")
        console.print("  [cyan]gorgon bot telegram[/cyan]")
    else:
        console.print("\n[dim]Skipping Telegram setup[/dim]")
