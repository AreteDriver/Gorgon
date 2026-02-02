"""Messaging module for two-way bot communication.

Provides integrations with messaging platforms like Telegram, Discord, and WhatsApp
for receiving and responding to messages through Gorgon's agent system.

This module enables Clawdbot-style operation where Gorgon acts as a
24/7 personal AI assistant accessible via messaging apps.

Supported Platforms:
    - Telegram: Full support via python-telegram-bot
    - Discord: Coming soon (upgrade from webhook-only)
    - WhatsApp: Coming soon (via Cloud API)

Usage:
    from test_ai.messaging import TelegramBot, MessageHandler

    # Create bot and handler
    bot = TelegramBot(token="YOUR_BOT_TOKEN")
    handler = MessageHandler(session_manager, supervisor)
    bot.set_message_callback(handler.handle_message)

    # Start listening
    await bot.start()
"""

from .base import MessagingBot, BotMessage, BotUser, MessagePlatform
from .handler import MessageHandler
from .telegram_bot import TelegramBot, create_telegram_bot
from .discord_bot import DiscordBot, create_discord_bot

__all__ = [
    # Base classes
    "MessagingBot",
    "BotMessage",
    "BotUser",
    "MessagePlatform",
    "MessageHandler",
    # Telegram
    "TelegramBot",
    "create_telegram_bot",
    # Discord
    "DiscordBot",
    "create_discord_bot",
]
