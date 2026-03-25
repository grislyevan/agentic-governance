"""MSI config stamper.

Copies a base MSI and injects tenant-specific properties.

On Windows: uses msilib to modify the Property table directly.
On Linux/macOS: appends config as a JSON trailer using the DETEC_CFG_V1 marker
(the MSI installer's custom action reads this trailer at install time).
"""

import hashlib
import json
import os
import shutil
import struct
import sys

MAGIC_MARKER = b"DETEC_CFG_V1\x00"


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
            pass

    # Fallback: append config trailer (works on any platform)
    _stamp_via_trailer(output_path, config)
    return output_path


def _stamp_via_msilib(msi_path: str, config: dict):
    """Inject properties into the MSI Property table (Windows only)."""
    import msilib

    db = msilib.OpenDatabase(msi_path, msilib.MSIDBOPEN_TRANSACT)

    property_map = {
        "DETEC_API_URL": config["api_url"],
        "DETEC_API_KEY": config["api_key"],
        "DETEC_TENANT_ID": config["tenant_id"],
    }

    for prop, val in property_map.items():
        # Escape single quotes for SQL
        safe_val = val.replace("'", "''")
        safe_prop = prop.replace("'", "''")

        view = db.OpenView(
            f"SELECT `Value` FROM `Property` WHERE `Property` = '{safe_prop}'"
        )
        view.Execute(None)
        rec = view.Fetch()
        view.Close()

        if rec:
            view = db.OpenView(
                f"UPDATE `Property` SET `Value` = '{safe_val}' WHERE `Property` = '{safe_prop}'"
            )
        else:
            view = db.OpenView(
                f"INSERT INTO `Property` (`Property`, `Value`) VALUES ('{safe_prop}', '{safe_val}')"
            )
        view.Execute(None)
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
