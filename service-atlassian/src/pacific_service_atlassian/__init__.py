"""service-atlassian — manages requests to and from Atlassian's ecosystem.

Handles Jira, Confluence, and Bitbucket integration for Pacific modules.
Credentials are read from the module's Solid vault via the driver.
"""

from pacific_service_atlassian.adapter import AtlassianAdapter

__all__ = ["AtlassianAdapter"]
