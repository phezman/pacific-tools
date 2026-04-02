"""Tests for the Slack service adapter."""

from __future__ import annotations

import pytest

from pacific_core.secrets import Service, ServiceCredential

from pacific_service_slack.adapter import SlackAdapter


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


class TestSlackAdapter:
    def test_not_connected_raises(self):
        adapter = SlackAdapter()
        with pytest.raises(RuntimeError, match="Not connected"):
            _ = adapter.client

    async def test_connect_reads_vault(self):
        cred = ServiceCredential(
            service="slack",
            access_token="xoxb-test-token",
            refresh_token="",
            token_expiry="",
            scopes=["chat:write", "channels:read"],
        )
        module = FakeModule({Service.SLACK: cred})
        adapter = SlackAdapter()
        await adapter.connect(module)
        assert adapter.client is not None

    async def test_connect_missing_credentials(self):
        module = FakeModule()
        adapter = SlackAdapter()
        with pytest.raises(KeyError, match="slack"):
            await adapter.connect(module)

    async def test_health_check_not_connected(self):
        adapter = SlackAdapter()
        assert await adapter.health_check() is False

    def test_service_enum(self):
        assert SlackAdapter.service == Service.SLACK
