# Deploy templates for Detec Agent

Templates to run the Detec Agent (endpoint collector) automatically at boot or logon. Use with the installed **detec-agent** console script (see root [DEPLOY.md](../DEPLOY.md)).

| Platform | Template | Notes |
|----------|----------|--------|
| macOS | [macos/com.detec.agent.plist](macos/com.detec.agent.plist) | LaunchAgent — copy to `~/Library/LaunchAgents/`, edit `ProgramArguments` (api-url), set API key via env or keychain |
| Linux | [linux/detec-agent.service](linux/detec-agent.service) | systemd user unit — copy to `~/.config/systemd/user/`, create `~/.config/detec/agent.env` with `AGENTIC_GOV_API_URL` and `AGENTIC_GOV_API_KEY`, then `systemctl --user enable --now detec-agent.service` |
| Windows | [windows/install-detec-agent-task.ps1](windows/install-detec-agent-task.ps1) | Scheduled task at logon — run script as user; set env vars for API URL and key |

Do not store the API key in plist XML or in scripts. Use environment files, keychain, or credential store (see DEPLOY.md).
