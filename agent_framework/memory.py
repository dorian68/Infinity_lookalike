"""Memory abstractions for agent conversations."""
from __future__ import annotations

import abc
from dataclasses import dataclass, field
from typing import Iterable, List, Sequence

from .chat_model import ChatMessage


class BaseMemory(abc.ABC):
    """Interface for conversation memory stores."""

    @abc.abstractmethod
    def load(self) -> Sequence[ChatMessage]:
        """Return the stored conversation history."""

    @abc.abstractmethod
    def save(self, messages: Iterable[ChatMessage]) -> None:
        """Persist messages to the memory store."""


@dataclass
class ConversationMemory(BaseMemory):
    """In-memory implementation useful for stateless compute (e.g. Lambda)."""

    buffer: List[ChatMessage] = field(default_factory=list)
    max_messages: int = 50

    def load(self) -> Sequence[ChatMessage]:
        return list(self.buffer)

    def save(self, messages: Iterable[ChatMessage]) -> None:
        for message in messages:
            self.buffer.append(message)
        overflow = len(self.buffer) - self.max_messages
        if overflow > 0:
            del self.buffer[0:overflow]
