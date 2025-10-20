"""Example demonstrating iterative tool selection."""
from __future__ import annotations

import json
from typing import Iterable

from agent_framework import (
    Agent,
    AgentConfig,
    BaseChatModel,
    ConversationMemory,
    StructuredOutputParser,
    ToolRegistry,
    tool,
)


@tool(
    description="Add two numbers together",
    schema={
        "parameters": {
            "type": "object",
            "properties": {
                "a": {"type": "number"},
                "b": {"type": "number"},
            },
            "required": ["a", "b"],
        }
    },
)
def add(a: float, b: float) -> float:
    return a + b


class ToyReasoningModel(BaseChatModel):
    """Rule-based model that mimics LLM tool decisions for testing."""

    def generate(self, messages: Iterable, *, tool_registry, **kwargs):
        conversation = list(messages)
        last_message = conversation[-1]

        if last_message.role == "user":
            return {
                "tool": "add",
                "args": {"a": 2, "b": 3},
                "summary": "Requesting the calculator tool to add 2 and 3",
            }

        if last_message.role == "tool":
            payload = json.loads(last_message.content)
            value = payload["result"]
            return {"final": f"The answer is {value}."}

        return {"final": "Unable to respond."}


def main() -> None:
    registry = ToolRegistry()
    registry.register(add)

    agent = Agent(
        AgentConfig(
            model=ToyReasoningModel(),
            output_parser=StructuredOutputParser(),
            memory=ConversationMemory(max_messages=10),
            tool_registry=registry,
        )
    )

    result = agent.run("Please add two numbers for me")
    print(result)


if __name__ == "__main__":
    main()
