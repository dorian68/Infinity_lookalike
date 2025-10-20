"""Agent that routes between Twelve Data and Finnhub tools."""
from __future__ import annotations

import json
import os
from typing import Iterable

import requests

from agent_framework import (
    Agent,
    AgentConfig,
    BaseChatModel,
    ConversationMemory,
    StructuredOutputParser,
    ToolRegistry,
    tool,
)

TWELVEDATA_URL = "https://api.twelvedata.com/time_series"
FINNHUB_URL = "https://finnhub.io/api/v1/quote"


@tool(
    name="fetch_twelve_data_series",
    description="Fetch OHLCV candles from Twelve Data for a symbol.",
    schema={
        "parameters": {
            "type": "object",
            "properties": {
                "symbol": {"type": "string"},
                "interval": {
                    "type": "string",
                    "description": "Resolution such as 1min, 5min, 1h, 1day.",
                    "default": "1day",
                },
                "outputsize": {
                    "type": "integer",
                    "description": "Number of candles to fetch",
                    "default": 5,
                },
            },
            "required": ["symbol"],
        }
    },
)
def fetch_twelve_data_series(
    symbol: str,
    interval: str = "1day",
    outputsize: int = 5,
) -> dict:
    api_key = os.getenv("TWELVEDATA_API_KEY")
    if not api_key:
        raise RuntimeError("Set TWELVEDATA_API_KEY to call Twelve Data")

    params = {
        "symbol": symbol,
        "interval": interval,
        "outputsize": outputsize,
        "apikey": api_key,
        "format": "JSON",
    }

    response = requests.get(TWELVEDATA_URL, params=params, timeout=10)
    response.raise_for_status()
    payload = response.json()
    if "values" not in payload:
        raise ValueError(f"Unexpected Twelve Data response: {payload}")
    return payload["values"][0]


@tool(
    name="fetch_finnhub_quote",
    description="Fetch the latest quote for a symbol using Finnhub.",
    schema={
        "parameters": {
            "type": "object",
            "properties": {
                "symbol": {"type": "string"},
            },
            "required": ["symbol"],
        }
    },
)
def fetch_finnhub_quote(symbol: str) -> dict:
    api_key = os.getenv("FINNHUB_API_KEY")
    if not api_key:
        raise RuntimeError("Set FINNHUB_API_KEY to call Finnhub")

    params = {"symbol": symbol, "token": api_key}
    response = requests.get(FINNHUB_URL, params=params, timeout=10)
    response.raise_for_status()
    return response.json()


class MarketRouterModel(BaseChatModel):
    """Simple heuristic model that demonstrates multi-tool routing."""

    def generate(self, messages: Iterable, *, tool_registry, **kwargs):
        conversation = list(messages)
        last = conversation[-1]

        if last.role == "user":
            text = last.content.lower()
            if any(keyword in text for keyword in ["quote", "price", "last trade"]):
                symbol = text.split()[-1].upper()
                return {
                    "tool": "fetch_finnhub_quote",
                    "args": {"symbol": symbol},
                    "summary": f"Fetching latest quote for {symbol} via Finnhub",
                }

            words = [token for token in text.replace(",", " ").split() if token.isalpha()]
            symbol = (words[-1] if words else "AAPL").upper()
            return {
                "tool": "fetch_twelve_data_series",
                "args": {"symbol": symbol, "interval": "1day"},
                "summary": f"Retrieving OHLCV candles for {symbol} from Twelve Data",
            }

        if last.role == "tool":
            payload = json.loads(last.content)
            result = payload["result"]
            if "c" in result:
                price = result["c"]
                return {"final": f"Finnhub reports the latest price at {price}."}

            close = result.get("close") or result.get("c")
            date = result.get("datetime") or result.get("date")
            return {"final": f"Twelve Data shows {close} as the close for {date}."}

        return {"final": "I was unable to interpret the request."}


def build_agent() -> Agent:
    registry = ToolRegistry()
    registry.register(fetch_twelve_data_series)
    registry.register(fetch_finnhub_quote)

    return Agent(
        AgentConfig(
            model=MarketRouterModel(),
            output_parser=StructuredOutputParser(),
            memory=ConversationMemory(max_messages=20),
            tool_registry=registry,
        )
    )


def main() -> None:
    agent = build_agent()
    print(
        agent.run(
            "Quel est le dernier prix pour AAPL ? Donne moi une reponse en utilisant Finnhub."
        )
    )


if __name__ == "__main__":
    main()
