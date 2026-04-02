"""schedule-meeting — MCP tool for scheduling meetings.

Directly available to the conversation agent. Resolves participants
from the sovereign graph, creates calendar events via Google or
Microsoft, and records the meeting in the module's knowledge graph.
"""

from pacific_schedule_meeting.tool import ScheduleMeetingTool

__all__ = ["ScheduleMeetingTool"]
