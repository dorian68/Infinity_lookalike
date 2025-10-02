"""Agent framework package inspired by n8n workflows."""

from .agent import Agent, AgentConfig
from .tools import Tool, ToolRegistry, tool
from .memory import BaseMemory, ConversationMemory
from .output_parser import (
    BaseOutputParser,
    JsonOutputParser,
    StructuredOutputParser,
    TextOutputParser,
)
from .chat_model import BaseChatModel, OpenAIChatModel, ChatMessage
from .types import AgentFinish, AgentToolCall

__all__ = [
    "Agent",
    "AgentConfig",
    "Tool",
    "ToolRegistry",
    "tool",
    "BaseMemory",
    "ConversationMemory",
    "BaseOutputParser",
    "JsonOutputParser",
    "StructuredOutputParser",
    "TextOutputParser",
    "BaseChatModel",
    "OpenAIChatModel",
    "ChatMessage",
    "AgentToolCall",
    "AgentFinish",
]
