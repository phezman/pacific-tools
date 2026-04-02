"""Tests for the schedule-meeting MCP tool."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from pacific_core.secrets import Service, ServiceCredential

from pacific_schedule_meeting.tool import (
    MCPTool,
    ScheduleMeetingTool,
    _compute_end_time,
)


# ── Fakes ────────────────────────────────────────────────────────────────────


class FakeSecrets:
    def __init__(self, services: list[Service] | None = None) -> None:
        self._services = services or []

    async def get(self, service: Service) -> ServiceCredential:
        if service not in self._services:
            raise KeyError(f"No credentials for {service.value}")
        return ServiceCredential(
            service=service.value,
            access_token="test-token",
            refresh_token="test-refresh",
            token_expiry="2026-12-31T00:00:00Z",
            scopes=[],
        )

    async def list_services(self) -> list[Service]:
        return list(self._services)


class FakeGraph:
    def __init__(self, lookup_results: list[dict] | None = None) -> None:
        self._results = lookup_results or []

    async def query(self, cypher: str, **params) -> list[dict]:
        name = params.get("name", "").lower()
        return [r for r in self._results if r.get("label", "").lower() == name]


class FakeModule:
    def __init__(
        self,
        services: list[Service] | None = None,
        graph_data: list[dict] | None = None,
    ) -> None:
        self.secrets = FakeSecrets(services)
        self.graph = FakeGraph(graph_data)
        self.root_node_uri = "https://alice.pod/vault/nodes/alice"
        self._nodes: list[dict] = []
        self._assertions: list[dict] = []

    async def ensure_node(self, label: str, node_type: str, **kwargs: str) -> str:
        uri = f"https://alice.pod/vault/nodes/{label.lower().replace(' ', '-')}"
        self._nodes.append({"label": label, "node_type": node_type, "uri": uri})
        return uri

    async def assert_triple(self, subject_uri: str, predicate_uri: str, object_uri: str, **kw) -> str:
        uri = f"https://alice.pod/vault/assertions/{len(self._assertions)}"
        self._assertions.append({
            "subject": subject_uri,
            "predicate": predicate_uri,
            "object": object_uri,
            **kw,
        })
        return uri


# ── Tests ────────────────────────────────────────────────────────────────────


class TestScheduleMeetingTool:
    def test_is_mcp_tool(self):
        tool = ScheduleMeetingTool()
        assert isinstance(tool, MCPTool)

    def test_name(self):
        assert ScheduleMeetingTool().name == "schedule_meeting"

    def test_input_schema_has_required_fields(self):
        schema = ScheduleMeetingTool().input_schema
        assert "title" in schema["properties"]
        assert "participants" in schema["properties"]
        assert "start_time" in schema["properties"]
        assert schema["required"] == ["title", "participants", "start_time"]

    async def test_no_calendar_service_raises(self):
        tool = ScheduleMeetingTool()
        module = FakeModule(services=[])
        with pytest.raises(RuntimeError, match="No calendar service"):
            await tool.execute(
                module,
                title="Sync",
                participants=["bob@acme.com"],
                start_time="2026-04-03T14:00:00",
            )

    @patch("pacific_schedule_meeting.tool._create_google_event")
    async def test_google_calendar_path(self, mock_create):
        mock_create.return_value = {"event_id": "evt-123", "link": "https://meet.google.com/abc"}

        tool = ScheduleMeetingTool()
        module = FakeModule(
            services=[Service.GOOGLE],
            graph_data=[{
                "uri": "https://alice.pod/vault/nodes/bob",
                "label": "Bob Smith",
                "email": "bob@acme.com",
            }],
        )

        result = await tool.execute(
            module,
            title="Product sync",
            participants=["Bob Smith"],
            start_time="2026-04-03T14:00:00",
            duration_minutes=30,
        )

        assert result["status"] == "scheduled"
        assert result["event_id"] == "evt-123"
        assert result["link"] == "https://meet.google.com/abc"
        assert result["end_time"] == "2026-04-03T14:30:00"
        assert "Bob Smith" in result["participants_resolved"]

        # Meeting node created
        assert any(n["node_type"] == "meeting" for n in module._nodes)

        # Participant assertions created (owner + Bob)
        participant_assertions = [
            a for a in module._assertions
            if "participant" in a["predicate"]
        ]
        assert len(participant_assertions) >= 1

    @patch("pacific_schedule_meeting.tool._create_microsoft_event")
    async def test_microsoft_calendar_fallback(self, mock_create):
        mock_create.return_value = {"event_id": "evt-ms", "link": "https://teams.microsoft.com/abc"}

        tool = ScheduleMeetingTool()
        module = FakeModule(services=[Service.MICROSOFT])

        result = await tool.execute(
            module,
            title="Standup",
            participants=["carol@acme.com"],
            start_time="2026-04-03T09:00:00",
        )

        assert result["status"] == "scheduled"
        assert result["event_id"] == "evt-ms"
        mock_create.assert_called_once()

    @patch("pacific_schedule_meeting.tool._create_google_event")
    async def test_unknown_participant_creates_node(self, mock_create):
        mock_create.return_value = {"event_id": "evt-456", "link": ""}

        tool = ScheduleMeetingTool()
        module = FakeModule(services=[Service.GOOGLE], graph_data=[])

        result = await tool.execute(
            module,
            title="Intro",
            participants=["Unknown Person"],
            start_time="2026-04-03T10:00:00",
        )

        assert result["status"] == "scheduled"
        # Should have created a node for the unknown participant
        person_nodes = [n for n in module._nodes if n["node_type"] == "person"]
        assert any(n["label"] == "Unknown Person" for n in person_nodes)


class TestComputeEndTime:
    def test_30_minutes(self):
        assert _compute_end_time("2026-04-03T14:00:00", 30) == "2026-04-03T14:30:00"

    def test_60_minutes(self):
        assert _compute_end_time("2026-04-03T14:00:00", 60) == "2026-04-03T15:00:00"

    def test_with_timezone(self):
        result = _compute_end_time("2026-04-03T14:00:00+00:00", 45)
        assert "14:45" in result
