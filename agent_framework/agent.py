"""Core agent orchestration module."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
import json
from typing import Any, Dict, Iterable, List, Optional

from .chat_model import BaseChatModel, ChatMessage
from .memory import BaseMemory
from .output_parser import BaseOutputParser, TextOutputParser
from .tools import Tool, ToolRegistry
from .types import AgentFinish, AgentToolCall

logger = logging.getLogger(__name__)


@dataclass
class AgentConfig:
    """Configuration parameters for :class:`Agent`."""

    model: BaseChatModel
    output_parser: Optional[BaseOutputParser] = None
    memory: Optional[BaseMemory] = None
    tool_registry: Optional[ToolRegistry] = None
    system_prompt: Optional[str] = None
    max_iterations: int = 6


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

    def _build_prompt(self, messages: Iterable[ChatMessage]) -> List[ChatMessage]:
        prompt: List[ChatMessage] = []
        if self.config.system_prompt:
            prompt.append(ChatMessage(role="system", content=self.config.system_prompt))
        prompt.extend(messages)
        return prompt

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
        working_history: List[ChatMessage] = list(self._history)
        user_message = ChatMessage(role="user", content=user_input)
        working_history.append(user_message)
        self._maybe_save_memory(user_message)

        prompt = self._build_prompt(working_history)
        logger.debug("Prompt built with %d messages", len(prompt))

        iterations = 0
        final_response: Optional[Any] = None

        while iterations < self.config.max_iterations:
            iterations += 1
            model_output = self.config.model.generate(
                prompt, tool_registry=self.tool_registry, **kwargs
            )
            logger.debug("Model output received: %s", model_output)

            parsed_output = self.config.output_parser.parse(model_output)
            logger.debug("Parsed output: %s", parsed_output)

            if isinstance(parsed_output, AgentToolCall):
                tool_name = parsed_output.tool
                tool_input = parsed_output.input
                tool_args = parsed_output.args
                logger.info("Invoking tool %s", tool_name)
                tool = self.tool_registry.get(tool_name)
                tool_result = tool.invoke(tool_input, **tool_args)
                logger.debug("Tool result: %s", tool_result)

                action_summary = (
                    parsed_output.summary
                    or f"Tool {tool_name} executed with input={tool_input} args={tool_args}"
                )
                working_history.append(
                    ChatMessage(role="assistant", content=action_summary)
                )
                tool_message = ChatMessage(
                    role="tool",
                    name=tool_name,
                    content=json.dumps({"result": tool_result}, default=str),
                )
                working_history.append(tool_message)
                prompt = self._build_prompt(working_history)
                continue

            if isinstance(parsed_output, AgentFinish):
                final_response = parsed_output.content
                assistant_message = ChatMessage(
                    role="assistant", content=str(parsed_output.content)
                )
                working_history.append(assistant_message)
                self._maybe_save_memory(assistant_message)
                break

            final_response = parsed_output
            assistant_message = ChatMessage(role="assistant", content=str(parsed_output))
            working_history.append(assistant_message)
            self._maybe_save_memory(assistant_message)
            break

        else:
            logger.warning("Agent reached max_iterations without finishing")

        self._history = working_history
        return final_response
