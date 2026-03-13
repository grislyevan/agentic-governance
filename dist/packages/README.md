# Agent packages (for dashboard “Deploy Agent” downloads)

Place pre-built agent installers here. The API serves them from `/data/packages/` inside the container (this directory is mounted as `./dist/packages` in Docker).

## Expected filenames

| Platform | Accepts (first found) |
|----------|------------------------|
| **Windows** | `DetecAgentSetup.exe` or `detec-agent.zip` |
| **macOS** | `DetecAgent-latest.pkg` or `DetecAgent.pkg` |
| **Linux** | `detec-agent-linux.tar.gz` |

## How to get the files

- **Windows:** On a Windows machine, run `packaging/windows/build-installer.ps1` (full pipeline) or build the agent with PyInstaller and zip the `packaging/windows/dist/detec-agent/` folder as `detec-agent.zip`. Copy `DetecAgentSetup.exe` or `detec-agent.zip` into this directory.
- **macOS:** On a Mac, run `packaging/macos/build-pkg.sh`. Copy the resulting `.pkg` into this directory as `DetecAgent-latest.pkg` or `DetecAgent.pkg`.
- **Linux:** Build the agent with PyInstaller on Linux, then tar the output as `detec-agent-linux.tar.gz` and place it here.

Until at least one of these files is present, the dashboard “Deploy Agent” page will show “No pre-built agent package found” for that platform.
