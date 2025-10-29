"""Serveur MCP pour agent IA de relation client multicanal."""

from .server import build_app
from .telegram_bot import TelegramCustomerAgentBot

__all__ = ["build_app", "TelegramCustomerAgentBot"]
