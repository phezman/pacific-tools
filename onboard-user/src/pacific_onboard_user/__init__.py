"""onboard-user — first task when a module's driver is initialised as a person.

Runs a structured conversational onboarding session via ElevenLabs voice agent,
extracts entities and relationships from the person's answers, and writes the
initial sovereign graph.
"""

from pacific_onboard_user.tool import OnboardUserTool

__all__ = ["OnboardUserTool"]
