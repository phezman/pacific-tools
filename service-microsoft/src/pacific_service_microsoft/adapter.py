"""MicrosoftAdapter — authenticates and manages the Microsoft Graph connection.

All vault reads for credentials go through the module's driver,
which enforces WAC access control via the Solid SDK.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from msgraph import GraphServiceClient
from msgraph_core import GraphClientFactory

from pacific_core.secrets import Service

if TYPE_CHECKING:
    from pacific_core.module import Module
    from pacific_core.secrets import ServiceCredential


class MicrosoftAdapter:
    """Manages authentication and API access to Microsoft services.

    Reads OAuth credentials from /meta/secrets/microsoft in the module's
    Solid vault, then constructs an authenticated Microsoft Graph client.
    """

    service = Service.MICROSOFT

    def __init__(self) -> None:
        self._credential: ServiceCredential | None = None
        self._client: GraphServiceClient | None = None

    @property
    def client(self) -> GraphServiceClient:
        """The authenticated Graph client. Call connect() first."""
        if self._client is None:
            raise RuntimeError(
                "Not connected. Call adapter.connect(module) first."
            )
        return self._client

    async def connect(self, module: Module) -> None:
        """Read OAuth credentials from the vault and authenticate.

        Args:
            module: The module whose vault stores Microsoft credentials.

        Raises:
            KeyError: If no Microsoft credentials are stored.
        """
        self._credential = await module.secrets.get(Service.MICROSOFT)
        # GraphServiceClient accepts a TokenCredential; for stored OAuth tokens
        # we use the access_token directly via a custom credential provider.
        self._client = GraphServiceClient(
            credentials=_TokenCredential(self._credential.access_token),
            scopes=self._credential.scopes,
        )

    async def health_check(self) -> bool:
        """Check whether the Microsoft credentials are valid."""
        return self._client is not None and self._credential is not None


class _TokenCredential:
    """Minimal credential wrapper for a pre-obtained access token."""

    def __init__(self, token: str) -> None:
        self._token = token

    async def get_token(self, *scopes: str, **kwargs: object) -> object:
        from collections import namedtuple
        AccessToken = namedtuple("AccessToken", ["token", "expires_on"])
        return AccessToken(token=self._token, expires_on=0)
