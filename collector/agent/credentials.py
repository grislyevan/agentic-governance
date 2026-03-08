"""Platform-specific API key retrieval from OS credential stores.

When the agent is started without --api-key / AGENTIC_GOV_API_KEY / config api_key,
the daemon can use this module to try the OS store first. Fallback remains
environment variable or config file.
"""

from __future__ import annotations

import logging
import platform
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)

_SERVICE = "detec-agent"
_ACCOUNT = "api-key"

# Linux: optional path for a protected file when secret-tool is not available.
_LINUX_KEY_FILE = Path.home() / ".config" / "detec" / "api_key"


def _get_api_key_macos() -> str | None:
    """Read API key from macOS Keychain (generic password)."""
    try:
        out = subprocess.run(
            [
                "security", "find-generic-password",
                "-s", _SERVICE,
                "-a", _ACCOUNT,
                "-w",
            ],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if out.returncode == 0 and out.stdout:
            return out.stdout.strip()
    except (FileNotFoundError, subprocess.TimeoutExpired) as e:
        logger.debug("Keychain lookup skipped: %s", e)
    return None


def _get_api_key_linux() -> str | None:
    """Try secret-tool (libsecret), then a protected file under ~/.config/detec/."""
    # 1. secret-tool (e.g. GNOME Keyring / libsecret)
    try:
        out = subprocess.run(
            ["secret-tool", "lookup", "service", _SERVICE, "account", _ACCOUNT],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if out.returncode == 0 and out.stdout:
            return out.stdout.strip()
    except FileNotFoundError:
        pass
    except subprocess.TimeoutExpired:
        logger.debug("secret-tool lookup timed out")

    # 2. Protected file (mode 600); user creates it manually.
    if _LINUX_KEY_FILE.exists():
        try:
            st = _LINUX_KEY_FILE.stat()
            if st.st_mode & 0o077 == 0:  # no group/other read
                return _LINUX_KEY_FILE.read_text().strip()
            logger.warning("Ignoring %s: file should be mode 600", _LINUX_KEY_FILE)
        except OSError as e:
            logger.debug("Could not read %s: %s", _LINUX_KEY_FILE, e)
    return None


def _get_api_key_windows() -> str | None:
    """Read API key from Windows Credential Manager via ctypes (no extra deps)."""
    if platform.system() != "Windows":
        return None
    try:
        import ctypes
        from ctypes import wintypes

        advapi32 = ctypes.windll.advapi32  # type: ignore[attr-defined]
        CRED_TYPE_GENERIC = 1
        CREDENTIALW = type("CREDENTIALW", (ctypes.Structure,), {
            "_fields_": [
                ("Flags", wintypes.DWORD),
                ("Type", wintypes.DWORD),
                ("TargetName", ctypes.c_wchar_p),
                ("Comment", ctypes.c_wchar_p),
                ("LastWritten", wintypes.FILETIME),
                ("CredentialBlobSize", wintypes.DWORD),
                ("CredentialBlob", ctypes.POINTER(ctypes.c_ubyte)),
                ("Persist", wintypes.DWORD),
                ("AttributeCount", wintypes.DWORD),
                ("Attributes", ctypes.c_void_p),
                ("TargetAlias", ctypes.c_wchar_p),
                ("UserName", ctypes.c_wchar_p),
            ]
        })
        pcred = ctypes.POINTER(CREDENTIALW)()
        if not advapi32.CredReadW(_SERVICE, CRED_TYPE_GENERIC, 0, ctypes.byref(pcred)):
            return None
        try:
            size = pcred.contents.CredentialBlobSize
            if not size or not pcred.contents.CredentialBlob:
                return None
            blob = ctypes.cast(
                pcred.contents.CredentialBlob,
                ctypes.POINTER(ctypes.c_ubyte * size),
            )
            return (ctypes.c_char * size).from_buffer(blob.contents).value.decode("utf-16-le")
        finally:
            advapi32.CredFree(pcred)
    except Exception as e:
        logger.debug("Credential Manager lookup failed: %s", e)
    return None


def get_api_key() -> str | None:
    """Return the API key from the platform credential store, or None.

    - macOS: Keychain generic password (service detec-agent, account api-key).
    - Linux: secret-tool (libsecret) or ~/.config/detec/api_key (mode 600).
    - Windows: Credential Manager (generic credential target detec-agent).

    Use this when env and config have not supplied an api_key; the caller
    should fall back to existing behaviour (env / config file) if this
    returns None.
    """
    system = platform.system()
    if system == "Darwin":
        return _get_api_key_macos()
    if system == "Linux":
        return _get_api_key_linux()
    if system == "Windows":
        return _get_api_key_windows()
    return None


def store_api_key_hint() -> None:
    """Log one-line hints for storing the API key in the OS store (for docs)."""
    system = platform.system()
    if system == "Darwin":
        logger.info(
            "To store API key in Keychain: security add-generic-password -s %s -a %s -w <key>",
            _SERVICE, _ACCOUNT,
        )
    elif system == "Linux":
        logger.info(
            "To store API key: secret-tool store --service=%s %s <key> ; or write to %s (chmod 600)",
            _SERVICE, _ACCOUNT, _LINUX_KEY_FILE,
        )
    elif system == "Windows":
        logger.info(
            "Store API key in Credential Manager for generic target '%s' (e.g. Control Panel).",
            _SERVICE,
        )
