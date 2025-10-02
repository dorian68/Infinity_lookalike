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

## Getting Started

```bash
python -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -r requirements.txt  # optional if you use the OpenAI adapter
```

Run the example script:

```bash
python examples/basic_usage.py
```

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
container images hosted on Amazon ECR.
