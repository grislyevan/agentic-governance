"""Platform-specific filesystem path registry for detected tools.

Each tool has known install, config, data, extension, and log directories
that differ across macOS, Linux, and Windows.  Scanners call
``get_tool_paths("cursor")`` instead of hard-coding OS-specific constants.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from .types import ToolPaths

_PLATFORM = sys.platform
_HOME = Path.home()


def _env_path(var: str) -> Path:
    """Resolve a Windows environment-variable path, falling back to HOME."""
    return Path(os.environ.get(var, str(_HOME)))


def get_tool_paths(tool_name: str) -> ToolPaths:
    """Return platform-appropriate filesystem paths for *tool_name*.

    Recognised tool names (case-insensitive): cursor, vscode, ollama.
    Unrecognised names return an empty ``ToolPaths``.
    """
    key = tool_name.lower()
    builder = _REGISTRY.get(key)
    if builder is None:
        return ToolPaths()
    return builder()


# -- Cursor ----------------------------------------------------------------

def _cursor_paths() -> ToolPaths:
    if _PLATFORM == "darwin":
        return ToolPaths(
            install_dir=Path("/Applications/Cursor.app"),
            config_dir=_HOME / "Library" / "Application Support" / "Cursor",
            data_dir=_HOME / ".cursor",
            extensions_dir=_HOME / ".cursor" / "extensions",
            log_dir=_HOME / "Library" / "Application Support" / "Cursor" / "logs",
        )
    elif _PLATFORM == "win32":
        local = _env_path("LOCALAPPDATA")
        appdata = _env_path("APPDATA")
        return ToolPaths(
            install_dir=local / "Programs" / "Cursor",
            config_dir=appdata / "Cursor",
            data_dir=_HOME / ".cursor",
            extensions_dir=_HOME / ".cursor" / "extensions",
            log_dir=appdata / "Cursor" / "logs",
        )
    else:  # Linux
        config_home = _env_path("XDG_CONFIG_HOME") if os.environ.get("XDG_CONFIG_HOME") else _HOME / ".config"
        return ToolPaths(
            install_dir=Path("/opt/Cursor") if Path("/opt/Cursor").is_dir() else Path("/usr/share/cursor"),
            config_dir=config_home / "Cursor",
            data_dir=_HOME / ".cursor",
            extensions_dir=_HOME / ".cursor" / "extensions",
            log_dir=config_home / "Cursor" / "logs",
        )


# -- VS Code (used by Copilot scanner) ------------------------------------

def _vscode_paths() -> ToolPaths:
    if _PLATFORM == "darwin":
        return ToolPaths(
            install_dir=Path("/Applications/Visual Studio Code.app"),
            config_dir=_HOME / "Library" / "Application Support" / "Code",
            data_dir=_HOME / ".vscode",
            extensions_dir=_HOME / ".vscode" / "extensions",
            log_dir=_HOME / "Library" / "Application Support" / "Code" / "logs",
        )
    elif _PLATFORM == "win32":
        local = _env_path("LOCALAPPDATA")
        appdata = _env_path("APPDATA")
        return ToolPaths(
            install_dir=local / "Programs" / "Microsoft VS Code",
            config_dir=appdata / "Code",
            data_dir=_HOME / ".vscode",
            extensions_dir=_HOME / ".vscode" / "extensions",
            log_dir=appdata / "Code" / "logs",
        )
    else:  # Linux
        config_home = _env_path("XDG_CONFIG_HOME") if os.environ.get("XDG_CONFIG_HOME") else _HOME / ".config"
        return ToolPaths(
            install_dir=Path("/usr/share/code"),
            config_dir=config_home / "Code",
            data_dir=_HOME / ".vscode",
            extensions_dir=_HOME / ".vscode" / "extensions",
            log_dir=config_home / "Code" / "logs",
        )


# -- Ollama ----------------------------------------------------------------

def _ollama_paths() -> ToolPaths:
    if _PLATFORM == "darwin":
        return ToolPaths(
            install_dir=None,
            config_dir=None,
            data_dir=_HOME / ".ollama",
        )
    elif _PLATFORM == "win32":
        local = _env_path("LOCALAPPDATA")
        return ToolPaths(
            install_dir=local / "Programs" / "Ollama",
            config_dir=None,
            data_dir=_HOME / ".ollama",
        )
    else:  # Linux
        return ToolPaths(
            install_dir=Path("/usr/local/bin"),
            config_dir=None,
            data_dir=_HOME / ".ollama",
        )


# -- Registry --------------------------------------------------------------

_REGISTRY: dict[str, callable] = {
    "cursor": _cursor_paths,
    "vscode": _vscode_paths,
    "ollama": _ollama_paths,
}
