"""Core agent orchestration module."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional

from .chat_model import BaseChatModel, ChatMessage
from .memory import BaseMemory
from .output_parser import BaseOutputParser, TextOutputParser
from .tools import Tool, ToolRegistry

logger = logging.getLogger(__name__)


@dataclass
class AgentConfig:
    """Configuration parameters for :class:`Agent`."""

    model: BaseChatModel
    output_parser: Optional[BaseOutputParser] = None
    memory: Optional[BaseMemory] = None
    tool_registry: Optional[ToolRegistry] = None
    system_prompt: Optional[str] = None


@dataclass
class Agent:
    """A modular agent that mirrors the flexibility of an n8n workflow.

    The agent orchestrates the chat model, memory, and tools following a
    structured prompt-driven workflow. It is intentionally light-weight so it can
    be hosted on infrastructure such as AWS Lambda, Fargate, or ECS.
    """

    config: AgentConfig
    _history: List[ChatMessage] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.config.tool_registry is None:
            self.config.tool_registry = ToolRegistry()
        if self.config.output_parser is None:
            self.config.output_parser = TextOutputParser()
        if self.config.memory is not None:
            self._history = list(self.config.memory.load())
        logger.debug("Agent initialised with %d history messages", len(self._history))

    # alias for convenience
    @property
    def tool_registry(self) -> ToolRegistry:
        return self.config.tool_registry  # type: ignore[return-value]

    def add_tool(self, tool: Tool) -> None:
        """Register a new tool at runtime."""

        logger.debug("Registering tool %s", tool.name)
        self.tool_registry.register(tool)

    def _build_prompt(self, user_input: str) -> Iterable[ChatMessage]:
        if self.config.system_prompt:
            yield ChatMessage(role="system", content=self.config.system_prompt)
        for message in self._history:
            yield message
        yield ChatMessage(role="user", content=user_input)

    def _maybe_save_memory(self, message: ChatMessage) -> None:
        if self.config.memory is not None:
            logger.debug("Saving message to memory: role=%s", message.role)
            self.config.memory.save([message])

    def run(self, user_input: str, **kwargs: Any) -> Any:
        """Execute the agent workflow.

        Parameters
        ----------
        user_input:
            Input provided by the caller (e.g. user query).

        Returns
        -------
        Any
            Parsed model output.
        """

        logger.info("Running agent with user input: %s", user_input)
        prompt = list(self._build_prompt(user_input))
        logger.debug("Prompt built with %d messages", len(prompt))

        model_output = self.config.model.generate(
            prompt, tool_registry=self.tool_registry, **kwargs
        )
        logger.debug("Model output received: %s", model_output)

        parsed_output = self.config.output_parser.parse(model_output)
        logger.debug("Parsed output: %s", parsed_output)

        if isinstance(parsed_output, dict) and "tool" in parsed_output:
            tool_name = parsed_output["tool"]
            tool_input = parsed_output.get("input")
            tool_args = parsed_output.get("args", {})
            logger.info("Invoking tool %s", tool_name)
            tool = self.tool_registry.get(tool_name)
            tool_result = tool.invoke(tool_input, **tool_args)
            logger.debug("Tool result: %s", tool_result)
            parsed_output["tool_result"] = tool_result

        assistant_message = ChatMessage(role="assistant", content=str(model_output))
        self._history.append(ChatMessage(role="user", content=user_input))
        self._history.append(assistant_message)
        self._maybe_save_memory(self._history[-2])
        self._maybe_save_memory(assistant_message)

        return parsed_output
