"""MSI config stamper.

Copies a base MSI and injects tenant-specific properties.

On Windows: uses msilib to modify the Property table directly.
On Linux/macOS: appends config as a JSON trailer using the DETEC_CFG_V1 marker
(the MSI installer's custom action reads this trailer at install time).
"""

import hashlib
import json
import logging
import os
import re
import shutil
import struct
import sys

logger = logging.getLogger(__name__)

MAGIC_MARKER = b"DETEC_CFG_V1\x00"

# Maximum length for any single property value stamped into the MSI.
_MAX_VALUE_LENGTH = 4096

# Regex: allow printable ASCII and common URL / key characters.
# Rejects control characters, null bytes, backticks, and other
# characters that could interfere with MSI SQL or shell contexts.
_SAFE_VALUE_RE = re.compile(
    r"^[a-zA-Z0-9\-._~:/?#\[\]@!$&()*+,=%{}\\ \"\^|]+$"
)


def _validate_stamp_value(name: str, value: str) -> None:
    """Validate a single config value before it reaches any stamping method.

    Raises ValueError if the value contains dangerous characters, null bytes,
    or exceeds the maximum length.  This is a defense-in-depth measure --
    the msilib path also uses parameterized queries, and the trailer path
    uses JSON serialization, but we reject obviously malicious input early.
    """
    if not isinstance(value, str):
        raise ValueError(f"MSI stamp value for '{name}' must be a string")
    if len(value) == 0:
        raise ValueError(f"MSI stamp value for '{name}' must not be empty")
    if len(value) > _MAX_VALUE_LENGTH:
        raise ValueError(
            f"MSI stamp value for '{name}' exceeds maximum length "
            f"({len(value)} > {_MAX_VALUE_LENGTH})"
        )
    if "\x00" in value:
        raise ValueError(
            f"MSI stamp value for '{name}' contains null bytes"
        )
    if not _SAFE_VALUE_RE.match(value):
        raise ValueError(
            f"MSI stamp value for '{name}' contains disallowed characters"
        )


def stamp_msi(
    base_msi_path: str,
    output_path: str,
    api_url: str,
    api_key: str,
    tenant_id: str,
) -> str:
    """Stamp tenant config into a copy of the base MSI."""
    if not os.path.exists(base_msi_path):
        raise FileNotFoundError(f"Base MSI not found: {base_msi_path}")

    # Validate all values at the entry point before any file I/O.
    _validate_stamp_value("api_url", api_url)
    _validate_stamp_value("api_key", api_key)
    _validate_stamp_value("tenant_id", tenant_id)

    shutil.copy2(base_msi_path, output_path)

    config = {
        "api_url": api_url,
        "api_key": api_key,
        "tenant_id": tenant_id,
    }

    if sys.platform == "win32":
        try:
            _stamp_via_msilib(output_path, config)
            return output_path
        except Exception:
            logger.warning("msilib stamping failed, falling back to trailer", exc_info=True)

    # Fallback: append config trailer (works on any platform)
    _stamp_via_trailer(output_path, config)
    return output_path


def _stamp_via_msilib(msi_path: str, config: dict):
    """Inject properties into the MSI Property table (Windows only).

    Uses parameterized queries (``?`` placeholders + MsiRecord) to avoid
    SQL injection.  Property names are hardcoded constants below so they
    never contain user input; values are bound via CreateRecord.
    """
    import msilib

    db = msilib.OpenDatabase(msi_path, msilib.MSIDBOPEN_TRANSACT)

    # Property names are constants we control -- not user input.
    property_map = {
        "DETEC_API_URL": config["api_url"],
        "DETEC_API_KEY": config["api_key"],
        "DETEC_TENANT_ID": config["tenant_id"],
    }

    for prop, val in property_map.items():
        # -- SELECT: check if the property already exists ----------------
        # Property name is a compile-time constant, safe to interpolate.
        # The value column is not referenced in the WHERE clause here.
        view = db.OpenView(
            f"SELECT `Value` FROM `Property` WHERE `Property` = '{prop}'"
        )
        view.Execute(None)
        rec = view.Fetch()
        view.Close()

        if rec:
            # -- UPDATE: bind the new value via parameterized query ------
            view = db.OpenView(
                f"UPDATE `Property` SET `Value` = ? WHERE `Property` = '{prop}'"
            )
            rec = msilib.CreateRecord(1)
            rec.SetString(1, val)
        else:
            # -- INSERT: bind both property name and value via params ----
            view = db.OpenView(
                "INSERT INTO `Property` (`Property`, `Value`) VALUES (?, ?)"
            )
            rec = msilib.CreateRecord(2)
            rec.SetString(1, prop)
            rec.SetString(2, val)
        view.Execute(rec)
        view.Close()

    db.Commit()


def _stamp_via_trailer(msi_path: str, config: dict):
    """Append config as a JSON trailer to the MSI binary.

    Format: [original MSI bytes] [MAGIC] [JSON bytes] [4-byte LE length] [MAGIC]
    This is the same format already used by the existing EXE config embedding.
    """
    config_bytes = json.dumps(config).encode("utf-8")
    trailer = MAGIC_MARKER + config_bytes + struct.pack("<I", len(config_bytes)) + MAGIC_MARKER

    with open(msi_path, "ab") as f:
        f.write(trailer)
