"""Scheduler artifact discovery: cron and LaunchAgent entries that invoke AI tools.

Reads user crontab, /etc/cron.d/, and LaunchAgent plists to find scheduled
runs of known AI binaries (claude, aider, cursor, ollama, etc.). Used to
close the cron/LaunchAgent blind spot: OS-level scheduled AI agent runs
that may not be visible to process or behavioral layers without ESF.
"""

from __future__ import annotations

import logging
import plistlib
import re
import subprocess
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Binary patterns (lowercase) -> (tool_name, tool_class)
# Order matters for disambiguation: more specific first.
BINARY_TO_TOOL: list[tuple[str, str, str]] = [
    ("claude code", "Claude Code", "C"),
    ("claude", "Claude Code", "C"),
    ("openclaw", "OpenClaw", "D"),
    ("aider", "Aider", "C"),
    ("cursor", "Cursor", "A"),
    ("ollama", "Ollama", "B"),
    ("open-interpreter", "Open Interpreter", "C"),
    ("interpreter", "Open Interpreter", "C"),  # python -m interpreter
    ("lm-studio", "LM Studio", "B"),
    ("lmstudio", "LM Studio", "B"),
    ("continue", "Continue", "A"),
    ("gpt-pilot", "GPT-Pilot", "C"),
    ("cline", "Cline", "A"),
]

# Paths to scan (user crontab, /etc/cron.d, LaunchAgents)
USER_LAUNCH_AGENTS = Path.home() / "Library" / "LaunchAgents"
SYSTEM_LAUNCH_AGENTS = Path("/Library/LaunchAgents")
CRON_D_DIR = Path("/etc/cron.d")


def _get_user_crontab() -> list[dict[str, Any]]:
    """Return crontab lines for current user. Each entry: source, path, command."""
    entries: list[dict[str, Any]] = []
    try:
        proc = subprocess.run(
            ["crontab", "-l"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if proc.returncode != 0 or not proc.stdout.strip():
            return entries
        path = "crontab (user)"
        for line in proc.stdout.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            entries.append({"source": "crontab", "path": path, "command": line})
    except (subprocess.TimeoutExpired, FileNotFoundError, PermissionError, OSError) as exc:
        logger.debug("Could not read user crontab: %s", exc)
    return entries


def _read_cron_dir(dir_path: Path) -> list[dict[str, Any]]:
    """Read files in /etc/cron.d or similar; each line that looks like a schedule + command."""
    entries: list[dict[str, Any]] = []
    if not dir_path.is_dir():
        return entries
    for f in dir_path.iterdir():
        if not f.is_file():
            continue
        try:
            text = f.read_text()
        except (OSError, PermissionError) as exc:
            logger.debug("Could not read %s: %s", f, exc)
            continue
        for line in text.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            entries.append({"source": dir_path.name, "path": str(f), "command": line})
    return entries


def _read_launch_agent_plist(plist_path: Path) -> list[str]:
    """Extract ProgramArguments or RunAtLoad/StartInterval command from a plist."""
    commands: list[str] = []
    try:
        data = plistlib.loads(plist_path.read_bytes())
    except (OSError, PermissionError, plistlib.InvalidFileException) as exc:
        logger.debug("Could not read plist %s: %s", plist_path, exc)
        return commands
    if not isinstance(data, dict):
        return commands
    # ProgramArguments is list of strings (executable + args)
    args = data.get("ProgramArguments")
    if isinstance(args, list) and args:
        commands.append(" ".join(str(a) for a in args))
    # Also check for legacy Program
    prog = data.get("Program")
    if isinstance(prog, str) and prog.strip():
        commands.append(prog.strip())
    return commands


def _get_launch_agent_entries(agents_dir: Path) -> list[dict[str, Any]]:
    """Return list of { source, path, command } from LaunchAgent plists."""
    entries: list[dict[str, Any]] = []
    if not agents_dir.is_dir():
        return entries
    for plist in agents_dir.glob("*.plist"):
        for cmd in _read_launch_agent_plist(plist):
            if cmd.strip():
                entries.append({
                    "source": "LaunchAgent",
                    "path": str(plist),
                    "command": cmd.strip(),
                })
    return entries


def _match_binary(command: str) -> tuple[str, str] | None:
    """If command invokes a known AI binary, return (tool_name, tool_class)."""
    lower = command.lower()
    for pattern, tool_name, tool_class in BINARY_TO_TOOL:
        # Word boundary or path boundary to avoid false positives (e.g. "continue" vs "continued")
        if re.search(r"(^|[\s/]|\b)" + re.escape(pattern) + r"(\b|[\s/]|$)", lower):
            return (tool_name, tool_class)
    return None


def get_scheduler_entries() -> list[dict[str, Any]]:
    """Collect all scheduler artifact entries (crontab, cron.d, LaunchAgents).

    Returns list of dicts: source, path, command, and optionally tool_name, tool_class
    when the command matches a known AI binary.
    """
    raw: list[dict[str, Any]] = []
    raw.extend(_get_user_crontab())
    raw.extend(_read_cron_dir(CRON_D_DIR))
    raw.extend(_get_launch_agent_entries(USER_LAUNCH_AGENTS))
    raw.extend(_get_launch_agent_entries(SYSTEM_LAUNCH_AGENTS))

    result: list[dict[str, Any]] = []
    for e in raw:
        cmd = e.get("command") or ""
        match = _match_binary(cmd)
        if match:
            e = {**e, "tool_name": match[0], "tool_class": match[1]}
            result.append(e)
    return result


def get_scheduler_evidence_by_tool() -> dict[str, list[dict[str, Any]]]:
    """Return scheduler entries grouped by tool_name for merging into scan results."""
    by_tool: dict[str, list[dict[str, Any]]] = {}
    for e in get_scheduler_entries():
        name = e.get("tool_name")
        if name:
            by_tool.setdefault(name, []).append(e)
    return by_tool
