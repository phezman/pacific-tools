"""AtlassianAdapter — authenticates and manages Atlassian API connections.

All vault reads for credentials go through the module's driver,
which enforces WAC access control via the Solid SDK.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from atlassian import Jira

from pacific_core.secrets import Service

if TYPE_CHECKING:
    from pacific_core.module import Module


class AtlassianAdapter:
    """Manages authentication and API access to Atlassian services.

    Reads OAuth credentials from /meta/secrets/atlassian in the module's
    Solid vault, then constructs authenticated Jira/Confluence clients.
    """

    service = Service.ATLASSIAN

    def __init__(self, *, cloud_url: str) -> None:
        self._cloud_url = cloud_url
        self._jira: Jira | None = None

    @property
    def jira(self) -> Jira:
        """The authenticated Jira client. Call connect() first."""
        if self._jira is None:
            raise RuntimeError(
                "Not connected. Call adapter.connect(module) first."
            )
        return self._jira

    async def connect(self, module: Module) -> None:
        """Read OAuth credentials from the vault and authenticate.

        Args:
            module: The module whose vault stores Atlassian credentials.

        Raises:
            KeyError: If no Atlassian credentials are stored.
        """
        credential = await module.secrets.get(Service.ATLASSIAN)
        self._jira = Jira(
            url=self._cloud_url,
            oauth2={"access_token": credential.access_token},
        )

    async def health_check(self) -> bool:
        """Check whether the Atlassian connection is healthy."""
        if self._jira is None:
            return False
        try:
            self._jira.myself()
            return True
        except Exception:
            return False

    async def get_issue(self, issue_key: str) -> dict[str, Any]:
        """Retrieve a Jira issue by key.

        Args:
            issue_key: Jira issue key (e.g. "PROJ-123").

        Returns:
            Issue dict with key, summary, status, and assignee.
        """
        issue = self.jira.issue(issue_key)
        return {
            "key": issue["key"],
            "summary": issue["fields"]["summary"],
            "status": issue["fields"]["status"]["name"],
            "assignee": (issue["fields"].get("assignee") or {}).get("displayName", ""),
        }

    async def create_issue(
        self,
        *,
        project_key: str,
        summary: str,
        issue_type: str = "Task",
        description: str = "",
    ) -> str:
        """Create a Jira issue.

        Returns:
            The created issue key.
        """
        result = self.jira.create_issue(
            fields={
                "project": {"key": project_key},
                "summary": summary,
                "issuetype": {"name": issue_type},
                "description": description,
            }
        )
        return result["key"]
