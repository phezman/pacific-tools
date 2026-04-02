"""Microsoft Calendar operations via Microsoft Graph API.

Creates, reads, and manages calendar events via Outlook/Microsoft 365.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pacific_service_microsoft.adapter import MicrosoftAdapter


@dataclass
class CalendarEvent:
    """A calendar event created or retrieved from Microsoft Calendar."""

    event_id: str
    title: str
    start_time: str
    end_time: str
    attendees: list[str]
    web_link: str = ""
    teams_link: str = ""


class MicrosoftCalendar:
    """Microsoft Calendar API operations via Graph."""

    def __init__(self, adapter: MicrosoftAdapter) -> None:
        self._adapter = adapter

    async def create_event(
        self,
        *,
        title: str,
        start_time: str,
        end_time: str,
        attendees: list[str],
        description: str = "",
        add_teams_link: bool = True,
    ) -> CalendarEvent:
        """Create a calendar event with optional Teams link.

        Args:
            title: Event title/subject.
            start_time: ISO 8601 start time.
            end_time: ISO 8601 end time.
            attendees: List of attendee email addresses.
            description: Optional event body.
            add_teams_link: Whether to attach a Teams meeting link.

        Returns:
            CalendarEvent with the created event details.
        """
        client = self._adapter.client

        body = {
            "subject": title,
            "body": {"contentType": "text", "content": description},
            "start": {"dateTime": start_time, "timeZone": "UTC"},
            "end": {"dateTime": end_time, "timeZone": "UTC"},
            "attendees": [
                {"emailAddress": {"address": email}, "type": "required"}
                for email in attendees
            ],
            "isOnlineMeeting": add_teams_link,
            "onlineMeetingProvider": "teamsForBusiness" if add_teams_link else "unknown",
        }

        result = await client.me.events.post(body)

        return CalendarEvent(
            event_id=result.id,
            title=result.subject or title,
            start_time=start_time,
            end_time=end_time,
            attendees=attendees,
            web_link=result.web_link or "",
            teams_link=getattr(result, "online_meeting_url", "") or "",
        )
