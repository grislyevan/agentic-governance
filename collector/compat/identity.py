"""Cross-platform identity, credential-store, and code-signature helpers.

macOS:  pwd, security CLI, codesign, plistlib
Linux:  pwd, secret-tool, returns None for signatures
Windows: net user / ctypes, cmdkey, PowerShell Get-AuthenticodeSignature
"""

from __future__ import annotations

import logging
import plistlib
import subprocess
import sys
from pathlib import Path

from .types import SignatureInfo

logger = logging.getLogger(__name__)

_PLATFORM = sys.platform


# -- User existence --------------------------------------------------------

def user_exists(username: str) -> bool:
    """Check whether an OS-level user account named *username* exists."""
    if _PLATFORM == "win32":
        return _user_exists_windows(username)
    return _user_exists_posix(username)


def _user_exists_posix(username: str) -> bool:
    import pwd
    try:
        pwd.getpwnam(username)
        return True
    except KeyError:
        return False


def _user_exists_windows(username: str) -> bool:
    try:
        proc = subprocess.run(
            ["net", "user", username],
            capture_output=True, text=True, timeout=5,
        )
        return proc.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return False


# -- Credential store ------------------------------------------------------

def get_credential_store_entry(service: str) -> bool:
    """Return True if a credential for *service* exists in the OS keychain."""
    if _PLATFORM == "darwin":
        return _credential_macos(service)
    elif _PLATFORM == "win32":
        return _credential_windows(service)
    return _credential_linux(service)


def _credential_macos(service: str) -> bool:
    try:
        proc = subprocess.run(
            ["security", "find-generic-password", "-s", service],
            capture_output=True, text=True, timeout=5,
        )
        return proc.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return False


def _credential_windows(service: str) -> bool:
    try:
        proc = subprocess.run(
            ["cmdkey", "/list"],
            capture_output=True, text=True, timeout=5,
        )
        if proc.returncode == 0 and service.lower() in proc.stdout.lower():
            return True
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError) as exc:
        logger.debug("Windows credential check for %s failed: %s", service, exc)
    return False


def _credential_linux(service: str) -> bool:
    try:
        proc = subprocess.run(
            ["secret-tool", "lookup", "service", service],
            capture_output=True, text=True, timeout=5,
        )
        return proc.returncode == 0 and bool(proc.stdout.strip())
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return False


# -- Code signature verification ------------------------------------------

def verify_code_signature(path: str | Path) -> SignatureInfo | None:
    """Verify the code signature of an application bundle or executable.

    Returns ``None`` when signature checking is not available on this
    platform (e.g. Linux without GPG-based verification).
    """
    if _PLATFORM == "darwin":
        return _codesign_macos(str(path))
    elif _PLATFORM == "win32":
        return _codesign_windows(str(path))
    return None


def _codesign_macos(path: str) -> SignatureInfo | None:
    try:
        proc = subprocess.run(
            ["codesign", "-dv", path],
            capture_output=True, text=True, timeout=10,
        )
        output = (proc.stdout or "") + (proc.stderr or "")
        if proc.returncode != 0:
            return SignatureInfo(signed=False)

        subject = None
        issuer = None
        for line in output.splitlines():
            if line.startswith("Authority="):
                if subject is None:
                    subject = line.split("=", 1)[1]
                else:
                    issuer = line.split("=", 1)[1]
            elif "TeamIdentifier=" in line:
                team = line.split("=", 1)[1]
                if subject:
                    subject = f"{subject} ({team})"

        return SignatureInfo(signed=True, subject=subject, issuer=issuer)
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return None


def _codesign_windows(path: str) -> SignatureInfo | None:
    try:
        proc = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             f"(Get-AuthenticodeSignature '{path}').Status;"
             f"(Get-AuthenticodeSignature '{path}').SignerCertificate.Subject;"
             f"(Get-AuthenticodeSignature '{path}').SignerCertificate.Issuer"],
            capture_output=True, text=True, timeout=15,
        )
        if proc.returncode != 0:
            return None
        lines = proc.stdout.strip().splitlines()
        if not lines:
            return None
        status = lines[0].strip()
        signed = status == "Valid"
        subject = lines[1].strip() if len(lines) > 1 else None
        issuer = lines[2].strip() if len(lines) > 2 else None
        return SignatureInfo(signed=signed, subject=subject, issuer=issuer)
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return None


# -- Application version --------------------------------------------------

def get_app_version(path: str | Path) -> str | None:
    """Extract the version string for an installed application.

    macOS:   reads CFBundleShortVersionString from Info.plist
    Windows: reads ProductVersion via PowerShell
    Linux:   returns None (callers should fall back to CLI --version)
    """
    if _PLATFORM == "darwin":
        return _version_macos(Path(path))
    elif _PLATFORM == "win32":
        return _version_windows(str(path))
    return None


def _version_macos(app_path: Path) -> str | None:
    plist_path = app_path / "Contents" / "Info.plist"
    if not plist_path.is_file():
        return None
    try:
        with open(plist_path, "rb") as f:
            plist = plistlib.load(f)
        return (
            plist.get("CFBundleShortVersionString")
            or plist.get("CFBundleVersion")
        )
    except (OSError, plistlib.InvalidFileException):
        return None


def _version_windows(path: str) -> str | None:
    try:
        proc = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             f"(Get-Item '{path}').VersionInfo.ProductVersion"],
            capture_output=True, text=True, timeout=10,
        )
        if proc.returncode == 0 and proc.stdout.strip():
            return proc.stdout.strip()
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError) as exc:
        logger.debug("PowerShell version query for %s failed: %s", path, exc)
    return None
