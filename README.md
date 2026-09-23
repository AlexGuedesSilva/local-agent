# Local Agent

A local-first AI agent in Python, developed incrementally as a long-term portfolio project.

## Goal

The project explores an AI agent that can run against a language model served locally. A local-first approach prioritizes keeping model interaction and future capabilities under the developer's control. The current implementation connects to an OpenAI-compatible local endpoint and supports a small tool-calling loop.

## Current status

**Early development.** The initial agent flow and two existing tools (calculator and current time) are present. The architecture is being organized for incremental development; future goals are not implemented yet.

## Initial architecture

- `agent/core`: orchestration of model requests and tool calls.
- `agent/llm`: OpenAI-compatible client configured through environment variables.
- `agent/tools`: current tool implementations and name-to-function registry.
- `tests/unit` and `tests/integration`: locations for meaningful tests as behavior evolves.
- `docs/architecture`: architecture documentation.

Future goals may include improving tool handling, reliability, and local model integration. No database, memory, RAG, or filesystem features are implemented at this stage.

## Stack

- Python
- `openai` Python package for an OpenAI-compatible chat completion API
- `python-dotenv` for loading local environment configuration
- A local model server, such as LM Studio, configured with a compatible endpoint

## Setup

Create and activate a virtual environment:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Install project dependencies:

```powershell
python -m pip install -r requirements.txt
```

Copy `.env.example` to `.env` and set the endpoint, API key accepted by your local server, and model identifier for your local model server. Do not commit `.env` or real credentials.

## Run

Start the configured local model server, then run:

```powershell
python main.py
```

Enter `sair` to exit. The current interactive application needs a reachable, correctly configured model endpoint to complete a chat request.

## Tests

Run the available tests with:

```powershell
python -m pytest
```

No test cases are currently present. Add tests when there is meaningful behavior to verify; do not add placeholder tests.
