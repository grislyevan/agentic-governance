"""Binary fingerprinting for agentic AI tool detection.

SHA-256 hashing of known tool entry-point binaries hardens detection
against evasion by renaming (e.g. ``aider`` → ``my_cool_script``).
Hashes are versioned so updates can be tracked over time.
"""

from __future__ import annotations

import hashlib
import logging
import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

BLOCK_SIZE = 65_536  # 64 KiB read chunks


@dataclass
class FingerprintResult:
    binary_path: str | None = None
    sha256: str | None = None
    match_status: str = "not_found"  # not_found | known | unknown | mismatch


KNOWN_ENTRY_POINTS: dict[str, list[str]] = {
    "Aider": ["aider"],
    "Claude Code": ["claude"],
    "Cursor": ["cursor"],
    "GitHub Copilot": ["copilot"],
    "Open Interpreter": ["interpreter"],
    "OpenClaw": ["openclaw"],
    "LM Studio": ["lm-studio", "lms"],
    "Ollama": ["ollama"],
    "Continue": [],
    "GPT-Pilot": ["gpt-pilot"],
    "Cline": [],
}

KNOWN_HASHES: dict[str, dict[str, str]] = {}


def hash_binary(path: str) -> str | None:
    """Return ``sha256:<hex>`` for a file, or None on error."""
    try:
        h = hashlib.sha256()
        with open(path, "rb") as f:
            while True:
                chunk = f.read(BLOCK_SIZE)
                if not chunk:
                    break
                h.update(chunk)
        return f"sha256:{h.hexdigest()}"
    except (OSError, PermissionError) as exc:
        logger.debug("Failed to hash %s: %s", path, exc)
        return None


def resolve_binary(name: str) -> str | None:
    """Find the real filesystem path for a command name."""
    path = shutil.which(name)
    if path is None:
        return None
    try:
        return str(Path(path).resolve())
    except OSError:
        return path


def fingerprint_tool(tool_name: str) -> FingerprintResult:
    """Hash the binary for a known tool and compare against the registry."""
    entry_points = KNOWN_ENTRY_POINTS.get(tool_name, [])
    if not entry_points:
        return FingerprintResult()

    for ep in entry_points:
        real_path = resolve_binary(ep)
        if real_path is None or not os.path.isfile(real_path):
            continue

        digest = hash_binary(real_path)
        if digest is None:
            continue

        tool_hashes = KNOWN_HASHES.get(tool_name, {})
        if digest in tool_hashes.values():
            return FingerprintResult(
                binary_path=real_path, sha256=digest, match_status="known",
            )

        if tool_hashes:
            return FingerprintResult(
                binary_path=real_path, sha256=digest, match_status="mismatch",
            )

        return FingerprintResult(
            binary_path=real_path, sha256=digest, match_status="unknown",
        )

    return FingerprintResult()


def hash_running_process(pid: int) -> str | None:
    """Attempt to hash the executable behind a running PID."""
    try:
        exe_link = f"/proc/{pid}/exe"
        if os.path.exists(exe_link):
            real = os.readlink(exe_link)
            return hash_binary(real)
    except (OSError, PermissionError):
        pass

    try:
        result = subprocess.run(
            ["ps", "-p", str(pid), "-o", "comm="],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            cmd = result.stdout.strip()
            path = resolve_binary(cmd)
            if path:
                return hash_binary(path)
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass

    return None
