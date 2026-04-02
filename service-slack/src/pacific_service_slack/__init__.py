"""service-slack — manages requests to and from Slack's ecosystem.

Handles Slack channels, messaging, and user management for Pacific modules.
Credentials are read from the module's Solid vault via the driver.
"""

from pacific_service_slack.adapter import SlackAdapter

__all__ = ["SlackAdapter"]
