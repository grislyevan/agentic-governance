"""Cleanup orphaned firewall rules from previous agent sessions.

On agent startup, removes any lingering firewall rules tagged with
the agentic-gov-block identifier. This handles the case where the
agent crashed after adding rules but before removing them.
"""

from __future__ import annotations

import logging
import platform
import subprocess

logger = logging.getLogger(__name__)

RULE_TAG = "agentic-gov-block"


def cleanup_orphaned_rules() -> int:
    """Remove all orphaned firewall rules from previous sessions.

    Returns the number of rules cleaned up.
    """
    system = platform.system()
    if system == "Darwin":
        return _cleanup_macos()
    if system == "Linux":
        return _cleanup_linux()
    if system == "Windows":
        return _cleanup_windows()
    return 0


def _cleanup_macos() -> int:
    """Flush all rules from the agentic-gov pf anchor."""
    anchor = "com.agentic-gov.block"
    try:
        check = subprocess.run(
            ["pfctl", "-a", anchor, "-s", "rules"],
            capture_output=True, text=True, timeout=10,
        )
        if check.returncode != 0 or not check.stdout.strip():
            return 0

        rule_count = len(check.stdout.strip().splitlines())

        result = subprocess.run(
            ["pfctl", "-a", anchor, "-F", "rules"],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode == 0:
            logger.info("Cleaned up %d orphaned pf rules from anchor %s", rule_count, anchor)
            return rule_count
        logger.warning("Failed to flush pf anchor %s: %s", anchor, result.stderr.strip())
    except (subprocess.TimeoutExpired, FileNotFoundError, PermissionError) as exc:
        logger.debug("Could not cleanup macOS firewall rules: %s", exc)
    return 0


def _cleanup_linux() -> int:
    """Remove all iptables OUTPUT rules tagged with our comment."""
    cleaned = 0
    try:
        result = subprocess.run(
            ["iptables", "-S", "OUTPUT"],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode != 0:
            return 0

        for line in reversed(result.stdout.strip().splitlines()):
            if RULE_TAG in line:
                delete_cmd = line.replace("-A OUTPUT", "-D OUTPUT", 1).split()
                try:
                    del_result = subprocess.run(
                        ["iptables"] + delete_cmd,
                        capture_output=True, text=True, timeout=10,
                    )
                    if del_result.returncode == 0:
                        cleaned += 1
                except (subprocess.TimeoutExpired, PermissionError):
                    pass

        if cleaned:
            logger.info("Cleaned up %d orphaned iptables rules", cleaned)
    except (subprocess.TimeoutExpired, FileNotFoundError, PermissionError) as exc:
        logger.debug("Could not cleanup Linux firewall rules: %s", exc)
    return cleaned


def _cleanup_windows() -> int:
    """Remove all Windows Firewall rules with our display name prefix."""
    cleaned = 0
    try:
        result = subprocess.run(
            ["netsh", "advfirewall", "firewall", "show", "rule", "name=all"],
            capture_output=True, text=True, timeout=15,
        )
        if result.returncode != 0:
            return 0

        current_name = ""
        for line in result.stdout.splitlines():
            line = line.strip()
            if line.startswith("Rule Name:"):
                current_name = line.split(":", 1)[1].strip()
            if current_name and RULE_TAG in current_name:
                try:
                    del_result = subprocess.run(
                        ["netsh", "advfirewall", "firewall", "delete", "rule",
                         f"name={current_name}"],
                        capture_output=True, text=True, timeout=10,
                    )
                    if del_result.returncode == 0:
                        cleaned += 1
                except (subprocess.TimeoutExpired, PermissionError):
                    pass
                current_name = ""

        if cleaned:
            logger.info("Cleaned up %d orphaned Windows Firewall rules", cleaned)
    except (subprocess.TimeoutExpired, FileNotFoundError, PermissionError) as exc:
        logger.debug("Could not cleanup Windows firewall rules: %s", exc)
    return cleaned
