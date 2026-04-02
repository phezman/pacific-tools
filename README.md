# pacific-tools

Monorepo of installable tools for Pacific modules. Each tool is an independent Python package.

See [CLAUDE.md](CLAUDE.md) for architecture.

## Packages

| Package | Directory | Description |
|---------|-----------|-------------|
| `pacific-onboard-user` | `onboard-user/` | Conversational onboarding via ElevenLabs voice agent |
| `pacific-schedule-meeting` | `schedule-meeting/` | MCP tool for scheduling meetings via calendar services |
| `pacific-service-google` | `service-google/` | Google ecosystem adapter (Calendar, Gmail, Drive, Meet) |
| `pacific-service-microsoft` | `service-microsoft/` | Microsoft ecosystem adapter (Outlook, OneDrive, Teams) |
| `pacific-service-slack` | `service-slack/` | Slack ecosystem adapter (channels, messaging) |
| `pacific-service-atlassian` | `service-atlassian/` | Atlassian ecosystem adapter (Jira, Confluence) |
