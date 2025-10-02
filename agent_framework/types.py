"""Shared agent data structures."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass
class AgentToolCall:
    """Instruction from the model to execute a tool."""

    tool: str
    input: Any = None
    args: Dict[str, Any] = field(default_factory=dict)
    summary: Optional[str] = None


@dataclass
class AgentFinish:
    """Terminal response produced by the model."""

    content: Any
