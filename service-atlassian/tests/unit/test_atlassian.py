"""Tests for the Atlassian service adapter."""

from __future__ import annotations

import pytest

from pacific_core.secrets import Service, ServiceCredential

from pacific_service_atlassian.adapter import AtlassianAdapter


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


class TestAtlassianAdapter:
    def test_not_connected_raises(self):
        adapter = AtlassianAdapter(cloud_url="https://test.atlassian.net")
        with pytest.raises(RuntimeError, match="Not connected"):
            _ = adapter.jira

    async def test_connect_reads_vault(self):
        cred = ServiceCredential(
            service="atlassian",
            access_token="eyJ0eXAi.atlassian-token",
            refresh_token="atlassian-refresh",
            token_expiry="2026-12-31T00:00:00Z",
            scopes=["read:jira-work", "write:jira-work"],
        )
        module = FakeModule({Service.ATLASSIAN: cred})
        adapter = AtlassianAdapter(cloud_url="https://test.atlassian.net")
        await adapter.connect(module)
        assert adapter.jira is not None

    async def test_connect_missing_credentials(self):
        module = FakeModule()
        adapter = AtlassianAdapter(cloud_url="https://test.atlassian.net")
        with pytest.raises(KeyError, match="atlassian"):
            await adapter.connect(module)

    async def test_health_check_not_connected(self):
        adapter = AtlassianAdapter(cloud_url="https://test.atlassian.net")
        assert await adapter.health_check() is False

    def test_service_enum(self):
        assert AtlassianAdapter.service == Service.ATLASSIAN
