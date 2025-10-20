# Infinity Lookalike Agent Framework

This repository provides a lightweight, composable agent framework inspired by
n8n workflows. It is implemented in Python so it can be deployed on AWS
Lambda, Fargate, ECS, or any other compute environment.

## Features

- **Tools** – Define Python callables that can be dynamically registered and
  invoked by the agent.
- **Memory** – Plug-and-play memory backends with an in-memory conversation
  buffer implementation.
- **Chat Models** – Abstract base class for LLM providers and a ready-made
  OpenAI adapter.
- **Output Parsers** – Convert raw model responses into structured data for
  downstream logic.
- **Iterative Orchestration** – The agent loops through model/tool exchanges
  until a final response is produced, mirroring n8n workflows with multiple
  tool hops.

## Getting Started

```bash
python -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -r requirements.txt  # optional if you use the OpenAI adapter
```

Run the example script to see the framework in action:

```bash
python examples/basic_usage.py
```

The script demonstrates how a model can request a tool, receive the tool
response, and then issue a final answer. It uses the `StructuredOutputParser`
to interpret JSON emitted by the chat model and loops until a terminal
response is produced.

You can also try the market-data example, which wires in real HTTP tools for
Twelve Data and Finnhub:

```bash
export TWELVEDATA_API_KEY=...  # provided by https://twelvedata.com/
export FINNHUB_API_KEY=...     # provided by https://finnhub.io/
python examples/market_data_agent.py
```

This example mirrors an n8n-style routing workflow: the model decides which
tool to call, executes it, observes the result, and emits a final summary.

## Building Your Own Workflow

The framework exposes a few key concepts that mirror the n8n primitives:

- **AgentConfig** – wires together the chat model, memory backend, tools, and
  output parser. Create a configuration object once and reuse it across
  invocations.
- **Agent** – the runtime orchestrator. Instantiate it with an `AgentConfig`
  and call `agent.run("your prompt")` to process a request.
- **ToolRegistry** – a container for your callable tools. Each tool is a
  function with a schema describing its expected arguments and a docstring that
  acts as the model-facing description.
- **OutputParser** – optional component that can translate raw model responses
  into structured Python objects (JSON, Pydantic models, etc.).

A minimal custom agent might look like this:

```python
from agent_framework import Agent, AgentConfig, ConversationMemory, ToolRegistry, tool
from agent_framework.chat_model import OpenAIChatModel


@tool(description="Add two numbers together")
def add(a: float, b: float) -> float:
    """Add two numbers."""
    return a + b


tools = ToolRegistry()
tools.register(add)
config = AgentConfig(
    model=OpenAIChatModel(api_key="sk-..."),
    memory=ConversationMemory(),
    tool_registry=tools,
)

agent = Agent(config)
print(agent.run("What is 2 + 2?"))
```

Swap in your own chat model implementation if you prefer a different LLM
provider or run a local model.

## Deploying on AWS

The framework has no hard dependency on a specific web framework, allowing it
to be embedded in FastAPI, Flask, or AWS Lambda handlers. A minimal Lambda
handler might look like:

```python
from agent_framework import Agent, AgentConfig, ConversationMemory
from my_models import MyChatModel

agent = Agent(AgentConfig(model=MyChatModel(), memory=ConversationMemory()))


def handler(event, context):
    user_input = event["body"]
    response = agent.run(user_input)
    return {"statusCode": 200, "body": response}
```

From there you can package the project using AWS SAM, Serverless Framework, or
container images hosted on Amazon ECR. A typical deployment flow is:

1. Expose an HTTP endpoint (FastAPI, Flask, Chalice, Lambda + API Gateway) that
   instantiates the agent once per process and reuses it for requests.
2. Configure your model credentials via environment variables or a secrets
   manager (e.g., `OPENAI_API_KEY`).
3. Package the code with its dependencies and deploy to your chosen compute
   target.

Because the abstractions are pure Python, you can unit-test your tools and
custom logic with standard testing frameworks (pytest, unittest) before
shipping to production.

## Consolidating Git Branches into `master`

If your GitHub project has accumulated many feature branches, you can use the
utility in `scripts/merge_all_branches.py` to merge everything back into
`master` in a single sweep. The helper defaults to a dry-run so you can review
the planned operations before executing them:

```bash
python scripts/merge_all_branches.py --create-master-from work
```

Once the output looks correct, repeat the command with `--execute` to perform
the merges. You can also skip specific branches by adding
`--ignore branch_one branch_two` or allow fast-forward merges with
`--allow-fast-forward`.
