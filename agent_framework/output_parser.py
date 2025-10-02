"""Output parsers help interpret model responses."""
from __future__ import annotations

import abc
import json
from typing import Any


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
