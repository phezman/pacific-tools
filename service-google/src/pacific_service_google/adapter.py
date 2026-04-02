"""GoogleAdapter — authenticates and manages the Google API connection.

All vault reads for credentials go through the module's driver,
which enforces WAC access control via the Solid SDK.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from google.oauth2.credentials import Credentials as GoogleCredentials

from pacific_core.secrets import Service

if TYPE_CHECKING:
    from pacific_core.module import Module


class GoogleAdapter:
    """Manages authentication and API access to Google services.

    Reads OAuth credentials from /meta/secrets/google in the module's
    Solid vault, then constructs authenticated Google API clients.
    """

    service = Service.GOOGLE

    def __init__(self) -> None:
        self._credentials: GoogleCredentials | None = None

    @property
    def credentials(self) -> GoogleCredentials:
        """The authenticated Google credentials. Call connect() first."""
        if self._credentials is None:
            raise RuntimeError(
                "Not connected. Call adapter.connect(module) first."
            )
        return self._credentials

    async def connect(self, module: Module) -> None:
        """Read OAuth credentials from the vault and authenticate.

        Args:
            module: The module whose vault stores Google credentials.

        Raises:
            KeyError: If no Google credentials are stored.
        """
        credential = await module.secrets.get(Service.GOOGLE)
        self._credentials = GoogleCredentials(
            token=credential.access_token,
            refresh_token=credential.refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            scopes=credential.scopes,
        )

    async def health_check(self) -> bool:
        """Check whether the Google credentials are valid."""
        if self._credentials is None:
            return False
        return self._credentials.valid and not self._credentials.expired
