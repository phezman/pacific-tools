# pacific-tools

Monorepo of installable tools for Pacific modules. Each subdirectory is an independent Python package with its own `pyproject.toml`.

## Architecture

Tools fall into two categories:

### MCP tools
Directly available to the conversation agent during coherence sessions. They expose a JSON Schema `input_schema` and return structured dicts. The agent decides when to call them based on the conversation.

- **schedule-meeting** — schedule meetings with participants from the sovereign graph

### Service adapters
Manage authentication and API communication with external service providers. Credentials are stored in `/meta/secrets/` in the module's Solid vault via `module.secrets` (pacific-core `Secrets` class). All vault reads go through the driver, which enforces WAC access control via the Solid SDK (`people`).

- **service-google** — Google Calendar, Gmail, Drive, Meet
- **service-microsoft** — Outlook Calendar, Mail, OneDrive, Teams
- **service-slack** — Channels, messaging, users
- **service-atlassian** — Jira, Confluence, Bitbucket

### Ingestion tools
Implement the `pacific_core.tools.Tool` ABC. Registered with `ToolManager` and invoked via `driver.ingest()`. Return `IngestResult`.

- **onboard-user** — conversational onboarding for person-initialised modules

## Key interfaces (from pacific-core)

- `module.secrets.get(Service.GOOGLE)` → `ServiceCredential`
- `module.secrets.list_services()` → connected services
- `module.ensure_node(label, node_type)` → create graph Node
- `module.assert_triple(s, p, o, ...)` → create Assertion
- `module.graph.query(cypher, ...)` → Neo4j lookup

## Package layout

```
pacific-tools/
├── onboard-user/           # pacific-onboard-user
├── schedule-meeting/       # pacific-schedule-meeting (MCP tool)
├── service-google/         # pacific-service-google
├── service-microsoft/      # pacific-service-microsoft
├── service-slack/          # pacific-service-slack
└── service-atlassian/      # pacific-service-atlassian
```

Each package follows:
```
{tool}/
├── pyproject.toml
├── src/{pacific_package_name}/
│   ├── __init__.py
│   └── ...
└── tests/unit/
    └── test_{name}.py
```

## Development

```bash
cd {tool}
python3 -m venv .venv
source .venv/bin/activate
pip install "pacific-core @ git+https://github.com/Pacific-Systems-Ltd/pacific-core.git"
pip install -e ".[dev]"
pytest tests/unit/ -v
```

## Commands

| Command | Purpose |
|---------|---------|
| `pytest {tool}/tests/unit/ -v` | Run tests for a specific tool |
| `ruff check {tool}/src/ {tool}/tests/` | Lint a tool |
| `mypy {tool}/src/` | Type check a tool |
