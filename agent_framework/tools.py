"""Tool abstractions for the agent."""
from __future__ import annotations

import inspect
from dataclasses import dataclass
from typing import Any, Callable, Dict, Iterable, Iterator, Optional


@dataclass
class Tool:
    """Representation of an executable tool."""

    name: str
    description: str
    callback: Callable[..., Any]
    schema: Optional[Dict[str, Any]] = None

    def invoke(self, input_value: Any = None, **kwargs: Any) -> Any:
        params = {}
        signature = inspect.signature(self.callback)
        if input_value is not None:
            if "input_value" in signature.parameters:
                params["input_value"] = input_value
            else:
                params[next(iter(signature.parameters))] = input_value
        params.update(kwargs)
        return self.callback(**params)

    @property
    def json_schema(self) -> Dict[str, Any]:
        schema = self.schema or {}
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": schema.get("parameters", {"type": "object", "properties": {}}),
            },
        }


class ToolRegistry(Iterable[Tool]):
    """Registry that mirrors n8n's tool nodes."""

    def __init__(self) -> None:
        self._tools: Dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        if tool.name in self._tools:
            raise ValueError(f"Tool {tool.name} already registered")
        self._tools[tool.name] = tool

    def get(self, name: str) -> Tool:
        try:
            return self._tools[name]
        except KeyError as exc:  # pragma: no cover - defensive
            raise KeyError(f"Tool {name} not found") from exc

    def __iter__(self) -> Iterator[Tool]:
        return iter(self._tools.values())


def tool(name: Optional[str] = None, description: str = "", schema: Optional[Dict[str, Any]] = None):
    """Decorator to declare a Python callable as a tool."""

    def decorator(func: Callable[..., Any]) -> Tool:
        tool_obj = Tool(name or func.__name__, description or func.__doc__ or "", func, schema)
        setattr(func, "_tool", tool_obj)
        return tool_obj

    return decorator
