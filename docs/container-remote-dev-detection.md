# Container and Remote-Dev Detection Expectations

**Workstream 2.** What the Detec endpoint agent can and cannot infer when tools run inside Docker, DevContainers, or remote development contexts. Host-based detection weakens there; this doc sets expectations for SOC and playbook alignment.

## What we detect today

| Context | Detection | Code |
|--------|-----------|------|
| **Linux container (Docker/OCI)** | `is_containerized(pid)` checks `/proc/{pid}/cgroup`, mountinfo, and `/.dockerenv`. Used by ISO-001 (Class C must run in container). | [collector/engine/container.py](../collector/engine/container.py) |
| **macOS + Docker Desktop** | `is_child_of_docker(pid)` walks process tree for `com.docker` / Docker; fallback: `/var/run/docker.sock` present. | Same |
| **DevContainer** | `is_devcontainer(pid)` checks env `DEVCONTAINER`, `DEVCONTAINER_ID`, and (Linux) `/.devcontainer`, `/run/.devcontainer`. | Same |
| **Remote dev** | `is_remote_dev_context()` checks `VSCODE_IPC_HOOK_CLI`, `REMOTE_CONTAINERS`, `CODESPACES`, `SSH_CONNECTION` + VS Code. | Same |

## Where host-based detection weakens

- **Inside a container:** Process and file signals are from the container’s view. The host agent may not see container-internal processes unless the agent runs inside the same container or has access to the runtime’s APIs.
- **DevContainer:** Same as container; plus the “host” may be the user’s laptop while the tool runs in the dev container. Agent on the laptop sees Docker (or remote) parent processes, not the full process tree inside the container.
- **Remote dev (SSH / Codespaces):** The tool runs on a remote host or VM. The “endpoint” may be the remote machine; if the agent runs on the user’s laptop, it does not see the remote processes or files.

## Intended use

- **Policy (ISO-001):** Only `is_containerized` / `is_child_of_docker` are used for policy today. Class C agents must run in a container; the policy evaluates the PID of the detected tool.
- **Reporting:** `is_devcontainer()` and `is_remote_dev_context()` are for event context and documentation. Events can carry a `container_context` or `remote_dev` hint so the SOC knows telemetry may be partial.
- **Playbook / INIT:** Tool profiles (INIT-13–22) and INIT-31 E2 (Environment Isolation) state that containerized and remote-dev sessions reduce host visibility. Detection confidence and layer weights may be adjusted in future for these contexts; currently we report context and document the limitation.

## Limitations

- We do not read another process’s environment; `is_devcontainer(pid)` for `pid != current` returns False.
- Remote dev is inferred from env vars that may not be set in all IDEs or SSH setups.
- No automatic “run agent inside container” deployment; that is a deployment/DevOps concern.
