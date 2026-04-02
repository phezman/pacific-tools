"""SlackAdapter — authenticates and manages the Slack API connection.

All vault reads for credentials go through the module's driver,
which enforces WAC access control via the Solid SDK.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from slack_sdk.web.async_client import AsyncWebClient

from pacific_core.secrets import Service

if TYPE_CHECKING:
    from pacific_core.module import Module


class SlackAdapter:
    """Manages authentication and API access to Slack.

    Reads OAuth credentials from /meta/secrets/slack in the module's
    Solid vault, then constructs an authenticated Slack client.
    """

    service = Service.SLACK

    def __init__(self) -> None:
        self._client: AsyncWebClient | None = None

    @property
    def client(self) -> AsyncWebClient:
        """The authenticated Slack client. Call connect() first."""
        if self._client is None:
            raise RuntimeError(
                "Not connected. Call adapter.connect(module) first."
            )
        return self._client

    async def connect(self, module: Module) -> None:
        """Read OAuth credentials from the vault and authenticate.

        Args:
            module: The module whose vault stores Slack credentials.

        Raises:
            KeyError: If no Slack credentials are stored.
        """
        credential = await module.secrets.get(Service.SLACK)
        self._client = AsyncWebClient(token=credential.access_token)

    async def health_check(self) -> bool:
        """Check whether the Slack connection is healthy."""
        if self._client is None:
            return False
        response = await self._client.auth_test()
        return response["ok"]

    async def send_message(self, channel: str, text: str) -> str:
        """Send a message to a Slack channel.

        Args:
            channel: Channel ID or name.
            text: Message text.

        Returns:
            The message timestamp (ts) identifier.
        """
        response = await self.client.chat_postMessage(channel=channel, text=text)
        return response["ts"]

    async def list_channels(self, limit: int = 100) -> list[dict]:
        """List Slack channels the bot has access to.

        Returns:
            List of channel dicts with id, name, and is_member fields.
        """
        response = await self.client.conversations_list(limit=limit)
        return [
            {"id": ch["id"], "name": ch["name"], "is_member": ch["is_member"]}
            for ch in response["channels"]
        ]
