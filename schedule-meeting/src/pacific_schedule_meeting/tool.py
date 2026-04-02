"""ScheduleMeetingTool — MCP tool for scheduling meetings.

This is an MCP tool, meaning it is directly available to the conversation
agent during coherence sessions. When the person says "schedule a meeting
with Bob tomorrow at 2pm", the agent calls this tool.

Pipeline:
    1. Resolve participant names via graph lookup
    2. Determine calendar service (Google or Microsoft)
    3. Authenticate via service adapter (credentials from vault)
    4. Create calendar event via external API
    5. Write meeting Node and participant Assertions to sovereign graph
    6. Return structured result to conversation agent
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any

from pacific_core.ontology.namespace import PAC
from pacific_core.secrets import Service

from pacific_service_google.adapter import GoogleAdapter
from pacific_service_google.calendar import GoogleCalendar
from pacific_service_microsoft.adapter import MicrosoftAdapter
from pacific_service_microsoft.calendar import MicrosoftCalendar

if TYPE_CHECKING:
    from pacific_core.module import Module

MEETING_MASS = 3.0
MEETING_VOLATILITY = 0.5  # meetings are moderately volatile events


# ── MCP Tool base ────────────────────────────────────────────────────────────


class MCPTool(ABC):
    """Base class for tools directly available to the conversation agent.

    MCP tools differ from ingestion tools (Tool ABC) in that they:
    - Expose a JSON Schema `input_schema` for the agent to call
    - Return structured dicts (not IngestResult)
    - Are invoked during conversation, not batch processing
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """MCP tool name."""

    @property
    @abstractmethod
    def description(self) -> str:
        """Human-readable description for the agent's tool list."""

    @property
    @abstractmethod
    def input_schema(self) -> dict[str, Any]:
        """JSON Schema describing the tool's parameters."""

    @abstractmethod
    async def execute(self, module: Module, **params: Any) -> dict[str, Any]:
        """Execute the tool and return a structured result."""


# ── Schedule Meeting ─────────────────────────────────────────────────────────


class ScheduleMeetingTool(MCPTool):
    """Schedule a meeting with participants from the sovereign graph."""

    @property
    def name(self) -> str:
        return "schedule_meeting"

    @property
    def description(self) -> str:
        return (
            "Schedule a meeting with one or more participants. Resolves names "
            "from the knowledge graph, creates a calendar event via Google "
            "Calendar or Microsoft Outlook, and records the meeting in the "
            "sovereign graph."
        )

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "title": {
                    "type": "string",
                    "description": "Meeting title/subject.",
                },
                "participants": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Names or email addresses of participants.",
                },
                "start_time": {
                    "type": "string",
                    "description": "ISO 8601 start time.",
                },
                "duration_minutes": {
                    "type": "integer",
                    "default": 30,
                    "description": "Duration in minutes.",
                },
                "description": {
                    "type": "string",
                    "default": "",
                    "description": "Optional meeting description.",
                },
            },
            "required": ["title", "participants", "start_time"],
        }

    async def execute(self, module: Module, **params: Any) -> dict[str, Any]:
        """Schedule the meeting.

        Returns a dict with status, event details, and graph URIs.
        """
        title: str = params["title"]
        participants: list[str] = params["participants"]
        start_time: str = params["start_time"]
        duration_minutes: int = params.get("duration_minutes", 30)
        description: str = params.get("description", "")

        end_time = _compute_end_time(start_time, duration_minutes)

        # 1. Resolve participants — look up emails in the graph
        resolved = await _resolve_participants(module, participants)

        # 2. Determine calendar service
        connected = await module.secrets.list_services()
        if Service.GOOGLE in connected:
            event = await _create_google_event(
                module, title=title, start_time=start_time, end_time=end_time,
                attendees=resolved["emails"], description=description,
            )
        elif Service.MICROSOFT in connected:
            event = await _create_microsoft_event(
                module, title=title, start_time=start_time, end_time=end_time,
                attendees=resolved["emails"], description=description,
            )
        else:
            raise RuntimeError(
                "No calendar service connected. Store credentials for "
                "Google or Microsoft via module.secrets.store()."
            )

        # 3. Write meeting Node to sovereign graph
        now = datetime.now(timezone.utc).isoformat()
        meeting_uri = await module.ensure_node(
            label=title,
            node_type="meeting",
        )

        # 4. Assert participant relationships
        root = module.root_node_uri or ""
        assertion_count = 0

        # Owner participates
        if root:
            await module.assert_triple(
                subject_uri=root,
                predicate_uri=str(PAC.participant),
                object_uri=meeting_uri,
                valid_from=start_time,
                mass=MEETING_MASS,
                volatility=MEETING_VOLATILITY,
                source=f"schedule_meeting:{event['event_id']}",
                confidence=1.0,
            )
            assertion_count += 1

        # Each resolved participant participates
        for uri in resolved["node_uris"]:
            if uri != root:
                await module.assert_triple(
                    subject_uri=uri,
                    predicate_uri=str(PAC.participant),
                    object_uri=meeting_uri,
                    valid_from=start_time,
                    mass=MEETING_MASS,
                    volatility=MEETING_VOLATILITY,
                    source=f"schedule_meeting:{event['event_id']}",
                    confidence=1.0,
                )
                assertion_count += 1

        return {
            "status": "scheduled",
            "event_id": event["event_id"],
            "title": title,
            "start_time": start_time,
            "end_time": end_time,
            "link": event.get("link", ""),
            "participants_resolved": resolved["names"],
            "meeting_node_uri": meeting_uri,
            "assertions_created": assertion_count,
        }


# ── Helpers ──────────────────────────────────────────────────────────────────


def _compute_end_time(start_time: str, duration_minutes: int) -> str:
    """Compute end time from start + duration."""
    start = datetime.fromisoformat(start_time)
    end = start + timedelta(minutes=duration_minutes)
    return end.isoformat()


async def _resolve_participants(
    module: Module,
    participants: list[str],
) -> dict[str, list]:
    """Resolve participant names to graph node URIs and email addresses.

    Looks up each participant in Neo4j by label. If found, uses the
    node's email (from FOAF namespace). If not found, treats the input
    as a raw email address.

    Returns:
        Dict with "names", "emails", and "node_uris" lists.
    """
    names: list[str] = []
    emails: list[str] = []
    node_uris: list[str] = []

    for participant in participants:
        # Try graph lookup by label
        results = await module.graph.query(
            "MATCH (n:Entity) WHERE toLower(n.label) = toLower($name) "
            "RETURN n.uri AS uri, n.label AS label, n.email AS email LIMIT 1",
            name=participant,
        )
        if results:
            record = results[0]
            names.append(record.get("label", participant))
            node_uris.append(record["uri"])
            email = record.get("email")
            if email:
                emails.append(email)
        elif "@" in participant:
            # Treat as raw email
            names.append(participant)
            emails.append(participant)
        else:
            # Create a new node for this unknown participant
            uri = await module.ensure_node(label=participant, node_type="person")
            names.append(participant)
            node_uris.append(uri)

    return {"names": names, "emails": emails, "node_uris": node_uris}


async def _create_google_event(
    module: Module,
    *,
    title: str,
    start_time: str,
    end_time: str,
    attendees: list[str],
    description: str,
) -> dict[str, str]:
    """Create a Google Calendar event."""
    adapter = GoogleAdapter()
    await adapter.connect(module)
    calendar = GoogleCalendar(adapter)
    event = await calendar.create_event(
        title=title,
        start_time=start_time,
        end_time=end_time,
        attendees=attendees,
        description=description,
    )
    return {
        "event_id": event.event_id,
        "link": event.html_link or event.meet_link,
    }


async def _create_microsoft_event(
    module: Module,
    *,
    title: str,
    start_time: str,
    end_time: str,
    attendees: list[str],
    description: str,
) -> dict[str, str]:
    """Create a Microsoft Calendar event."""
    adapter = MicrosoftAdapter()
    await adapter.connect(module)
    calendar = MicrosoftCalendar(adapter)
    event = await calendar.create_event(
        title=title,
        start_time=start_time,
        end_time=end_time,
        attendees=attendees,
        description=description,
    )
    return {
        "event_id": event.event_id,
        "link": event.web_link or event.teams_link,
    }
