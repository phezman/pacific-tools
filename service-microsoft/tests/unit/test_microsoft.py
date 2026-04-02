"""Tests for the Microsoft service adapter."""

from __future__ import annotations

import pytest

from pacific_core.secrets import Service, ServiceCredential

from pacific_service_microsoft.adapter import MicrosoftAdapter


class FakeSecrets:
    def __init__(self, credentials: dict[Service, ServiceCredential] | None = None) -> None:
        self._creds = credentials or {}

    async def get(self, service: Service) -> ServiceCredential:
        if service not in self._creds:
            raise KeyError(f"No credentials stored for {service.value}.")
        return self._creds[service]


class FakeModule:
    def __init__(self, credentials: dict[Service, ServiceCredential] | None = None) -> None:
        self.secrets = FakeSecrets(credentials)


class TestMicrosoftAdapter:
    def test_not_connected_raises(self):
        adapter = MicrosoftAdapter()
        with pytest.raises(RuntimeError, match="Not connected"):
            _ = adapter.client

    async def test_connect_reads_vault(self):
        cred = ServiceCredential(
            service="microsoft",
            access_token="eyJ0eXAi.test-token",
            refresh_token="M.test-refresh",
            token_expiry="2026-12-31T00:00:00Z",
            scopes=["Calendars.ReadWrite", "Mail.Read"],
        )
        module = FakeModule({Service.MICROSOFT: cred})
        adapter = MicrosoftAdapter()
        await adapter.connect(module)
        assert adapter.client is not None

    async def test_connect_missing_credentials(self):
        module = FakeModule()
        adapter = MicrosoftAdapter()
        with pytest.raises(KeyError, match="microsoft"):
            await adapter.connect(module)

    async def test_health_check_not_connected(self):
        adapter = MicrosoftAdapter()
        assert await adapter.health_check() is False

    def test_service_enum(self):
        assert MicrosoftAdapter.service == Service.MICROSOFT
