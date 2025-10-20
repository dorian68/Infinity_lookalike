"""Output parsers help interpret model responses."""
from __future__ import annotations

import abc
import json
from typing import Any, Dict

from .types import AgentFinish, AgentToolCall


class BaseOutputParser(abc.ABC):
    """Interface for post-processing model outputs."""

    @abc.abstractmethod
    def parse(self, model_output: Any) -> Any:
        """Parse the raw output from the chat model."""


class TextOutputParser(BaseOutputParser):
    """Return the model output unchanged."""

    def parse(self, model_output: Any) -> Any:
        return model_output


class JsonOutputParser(BaseOutputParser):
    """Parse JSON output emitted by models following tool instructions."""

    def parse(self, model_output: Any) -> Any:
        if isinstance(model_output, (dict, list)):
            return model_output
        if not isinstance(model_output, str):
            raise TypeError("Model output must be a JSON string")
        return json.loads(model_output)


class StructuredOutputParser(BaseOutputParser):
    """Interpret structured JSON outputs describing tool usage or final replies."""

    def parse(self, model_output: Any) -> Any:
        if isinstance(model_output, (AgentToolCall, AgentFinish)):
            return model_output

        payload: Dict[str, Any]
        if isinstance(model_output, dict):
            payload = model_output
        else:
            if not isinstance(model_output, str):
                raise TypeError("Model output must be a JSON object or string")
            payload = json.loads(model_output)

        if "tool" in payload:
            return AgentToolCall(
                tool=payload["tool"],
                input=payload.get("input"),
                args=payload.get("args", {}),
                summary=payload.get("summary"),
            )

        if "final" in payload:
            return AgentFinish(payload["final"])
        if "output" in payload:
            return AgentFinish(payload["output"])
        if "content" in payload:
            return AgentFinish(payload["content"])

        raise ValueError("Unable to interpret structured model output")
