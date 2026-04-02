# pacific-tools

Pluggable tools for Pacific modules. Each tool implements `pacific_core.tools.Tool` ABC.

## Architecture

Tools are standalone packages that depend on `pacific-core`. A module's `ToolManager` registers them, and its `Driver` invokes them via `driver.ingest(tool_name, **kwargs)`.

## Tools

### onboard-user

First task when a module's driver is initialised as a person. Runs a conversational onboarding session via ElevenLabs voice agent, extracts entities and relationships from the transcript, and writes the initial sovereign graph.

Pipeline:
1. Voice conversation (ElevenLabs `AsyncConversation` with pre-configured agent)
2. Entity extraction (Haiku) on captured transcript
3. Relationship extraction (Sonnet) between discovered entities
4. Write Nodes and Assertions to the module's Solid vault
5. Assert `owner --knows--> person` for every discovered person entity

Requires: an ElevenLabs agent ID configured for onboarding questions.

## Stack

- Python 3.11+
- `pacific-core` — Module, Driver, Tool ABC, extraction pipeline
- `elevenlabs` — Conversational AI SDK (voice agent sessions)

## Development

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install "pacific-core @ git+https://github.com/Pacific-Systems-Ltd/pacific-core.git"
pip install -e ".[dev]"
pytest tests/unit/ -v
```

## Package layout

```
src/pacific_tools/
├── __init__.py
└── onboard_user/
    ├── __init__.py
    ├── tool.py           # OnboardUserTool(Tool)
    └── conversation.py   # ElevenLabs conversation capture
```

## Commands

| Command | Purpose |
|---------|---------|
| `pytest tests/unit/ -v` | Run unit tests (no network) |
| `ruff check src/ tests/` | Lint |
| `mypy src/` | Type check |
