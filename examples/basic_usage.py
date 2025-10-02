"""Example demonstrating the agent framework."""
from __future__ import annotations

from agent_framework import (
    Agent,
    AgentConfig,
    ConversationMemory,
    JsonOutputParser,
    ToolRegistry,
    tool,
)


@tool(description="Add two numbers together", schema={
    "parameters": {
        "type": "object",
        "properties": {
            "a": {"type": "number"},
            "b": {"type": "number"},
        },
        "required": ["a", "b"],
    }
})
def add(a: float, b: float) -> float:
    return a + b


class EchoModel:
    """Toy model that echoes prompts and requests a tool."""

    def generate(self, messages, *, tool_registry, **kwargs):
        _ = list(messages)
        return {"tool": "add", "args": {"a": 2, "b": 3}}


def main() -> None:
    registry = ToolRegistry()
    registry.register(add)

    agent = Agent(
        AgentConfig(
            model=EchoModel(),
            output_parser=JsonOutputParser(),
            memory=ConversationMemory(max_messages=10),
            tool_registry=registry,
        )
    )

    result = agent.run("Please add two numbers for me")
    print(result)


if __name__ == "__main__":
    main()
