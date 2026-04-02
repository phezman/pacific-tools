"""Tests for the Google service adapter."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from pacific_core.secrets import Service, ServiceCredential

from pacific_service_google.adapter import GoogleAdapter


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


class TestGoogleAdapter:
    def test_not_connected_raises(self):
        adapter = GoogleAdapter()
        with pytest.raises(RuntimeError, match="Not connected"):
            _ = adapter.credentials

    async def test_connect_reads_vault(self):
        cred = ServiceCredential(
            service="google",
            access_token="ya29.test-token",
            refresh_token="1//test-refresh",
            token_expiry="2026-12-31T00:00:00Z",
            scopes=["https://www.googleapis.com/auth/calendar"],
        )
        module = FakeModule({Service.GOOGLE: cred})
        adapter = GoogleAdapter()
        await adapter.connect(module)
        assert adapter.credentials.token == "ya29.test-token"

    async def test_connect_missing_credentials(self):
        module = FakeModule()
        adapter = GoogleAdapter()
        with pytest.raises(KeyError, match="google"):
            await adapter.connect(module)

    async def test_health_check_not_connected(self):
        adapter = GoogleAdapter()
        assert await adapter.health_check() is False

    def test_service_enum(self):
        assert GoogleAdapter.service == Service.GOOGLE
