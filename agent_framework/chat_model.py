"""Chat model abstractions."""
from __future__ import annotations

import abc
from dataclasses import dataclass
from typing import Any, Iterable, List, Optional

try:  # pragma: no cover - optional dependency
    import openai
except ImportError:  # pragma: no cover - optional dependency
    openai = None  # type: ignore

from .tools import ToolRegistry


@dataclass
class ChatMessage:
    """Simple chat message container."""

    role: str
    content: str
    name: Optional[str] = None


class BaseChatModel(abc.ABC):
    """Abstract base class for chat completion providers."""

    @abc.abstractmethod
    def generate(
        self, messages: Iterable[ChatMessage], *, tool_registry: ToolRegistry, **kwargs: Any
    ) -> Any:
        """Generate a response from the model."""


class OpenAIChatModel(BaseChatModel):
    """Wrapper around OpenAI's Chat Completions API.

    Parameters
    ----------
    model:
        Chat completion model identifier.
    api_key:
        Optional API key. If omitted, ``OPENAI_API_KEY`` is used.
    """

    def __init__(self, model: str = "gpt-3.5-turbo", api_key: Optional[str] = None) -> None:
        if openai is None:  # pragma: no cover - dependency optional
            raise RuntimeError(
                "openai package is required for OpenAIChatModel. Install openai first."
            )
        if api_key:
            openai.api_key = api_key
        self.model = model

    def generate(
        self, messages: Iterable[ChatMessage], *, tool_registry: ToolRegistry, **kwargs: Any
    ) -> Any:
        tools_payload: List[dict] = [tool.json_schema for tool in tool_registry]

        response = openai.ChatCompletion.create(  # type: ignore[attr-defined]
            model=self.model,
            messages=[
                {k: v for k, v in message.__dict__.items() if v is not None}
                for message in messages
            ],
            tools=tools_payload or None,
            **kwargs,
        )
        choice = response["choices"][0]
        if tool_call := choice.get("message", {}).get("tool_calls"):
            return {
                "tool": tool_call[0]["function"]["name"],
                "input": tool_call[0]["function"].get("arguments"),
            }
        return choice["message"]["content"]
