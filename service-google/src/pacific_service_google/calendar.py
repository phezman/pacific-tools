"""Google Calendar operations.

Creates, reads, and manages calendar events via the Google Calendar API.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from googleapiclient.discovery import build

if TYPE_CHECKING:
    from pacific_service_google.adapter import GoogleAdapter


@dataclass
class CalendarEvent:
    """A calendar event created or retrieved from Google Calendar."""

    event_id: str
    title: str
    start_time: str
    end_time: str
    attendees: list[str]
    html_link: str = ""
    meet_link: str = ""


class GoogleCalendar:
    """Google Calendar API operations."""

    def __init__(self, adapter: GoogleAdapter) -> None:
        self._adapter = adapter

    async def create_event(
        self,
        *,
        title: str,
        start_time: str,
        end_time: str,
        attendees: list[str],
        description: str = "",
        add_meet_link: bool = True,
    ) -> CalendarEvent:
        """Create a calendar event with optional Google Meet link.

        Args:
            title: Event title/summary.
            start_time: ISO 8601 start time.
            end_time: ISO 8601 end time.
            attendees: List of attendee email addresses.
            description: Optional event description.
            add_meet_link: Whether to attach a Google Meet link.

        Returns:
            CalendarEvent with the created event details.
        """
        service = build(
            "calendar", "v3", credentials=self._adapter.credentials,
        )

        body: dict[str, Any] = {
            "summary": title,
            "description": description,
            "start": {"dateTime": start_time},
            "end": {"dateTime": end_time},
            "attendees": [{"email": email} for email in attendees],
        }
        if add_meet_link:
            body["conferenceData"] = {
                "createRequest": {"requestId": f"pacific-{title[:20]}"},
            }

        result = (
            service.events()
            .insert(
                calendarId="primary",
                body=body,
                conferenceDataVersion=1 if add_meet_link else 0,
                sendUpdates="all",
            )
            .execute()
        )

        return CalendarEvent(
            event_id=result["id"],
            title=result.get("summary", title),
            start_time=start_time,
            end_time=end_time,
            attendees=attendees,
            html_link=result.get("htmlLink", ""),
            meet_link=result.get("hangoutLink", ""),
        )
