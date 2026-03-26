"""Tests for core.msi_stamper -- MSI config embedding."""

from __future__ import annotations

import json
import struct

import pytest

from core.msi_stamper import MAGIC_MARKER, _stamp_via_trailer, stamp_msi


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SAMPLE_CONFIG = {
    "api_url": "https://api.detec.example.com",
    "api_key": "a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2",
    "tenant_id": "tn_test_abc123",
}

FAKE_MSI_BYTES = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + (b"\x00" * 512)


def _create_fake_msi(path) -> None:
    """Write a minimal fake MSI file (OLE2 magic + padding)."""
    path.write_bytes(FAKE_MSI_BYTES)


def _read_trailer_config(path) -> dict:
    """Parse the JSON config from a DETEC_CFG_V1 trailer appended to a file.

    Trailer format:
        [original bytes] [MAGIC] [JSON bytes] [4-byte LE length] [MAGIC]
    """
    data = path.read_bytes()
    # The trailer ends with the magic marker.
    assert data.endswith(MAGIC_MARKER), "File does not end with MAGIC_MARKER"
    # Strip trailing marker, then read length.
    without_trailing = data[: -len(MAGIC_MARKER)]
    length = struct.unpack("<I", without_trailing[-4:])[0]
    json_bytes = without_trailing[-4 - length : -4]
    return json.loads(json_bytes)


# ---------------------------------------------------------------------------
# stamp_msi -- high-level function
# ---------------------------------------------------------------------------


class TestStampMsi:
    """Tests for the public stamp_msi() entry point."""

    def test_raises_on_nonexistent_input(self, tmp_path: pytest.TempPathFactory) -> None:
        missing = tmp_path / "does_not_exist.msi"
        output = tmp_path / "out.msi"
        with pytest.raises(FileNotFoundError, match="Base MSI not found"):
            stamp_msi(str(missing), str(output), **SAMPLE_CONFIG)

    def test_raises_when_base_is_directory(self, tmp_path) -> None:
        base_dir = tmp_path / "not_a_file"
        base_dir.mkdir()
        output = tmp_path / "out.msi"
        # os.path.exists returns True for directories, but copy2 or the trailer
        # write will still work -- the key thing is the function does not silently
        # succeed on a directory.  If the implementation doesn't guard this today,
        # shutil.copy2 raises IsADirectoryError (or similar).
        with pytest.raises((IsADirectoryError, OSError)):
            stamp_msi(str(base_dir), str(output), **SAMPLE_CONFIG)

    def test_output_file_is_created(self, tmp_path) -> None:
        base = tmp_path / "base.msi"
        _create_fake_msi(base)
        output = tmp_path / "stamped.msi"

        result = stamp_msi(str(base), str(output), **SAMPLE_CONFIG)
        assert result == str(output)
        assert output.exists()

    def test_config_values_embedded_in_output(self, tmp_path) -> None:
        base = tmp_path / "base.msi"
        _create_fake_msi(base)
        output = tmp_path / "stamped.msi"

        stamp_msi(str(base), str(output), **SAMPLE_CONFIG)

        config = _read_trailer_config(output)
        assert config["api_url"] == SAMPLE_CONFIG["api_url"]
        assert config["api_key"] == SAMPLE_CONFIG["api_key"]
        assert config["tenant_id"] == SAMPLE_CONFIG["tenant_id"]

    def test_original_bytes_preserved(self, tmp_path) -> None:
        base = tmp_path / "base.msi"
        _create_fake_msi(base)
        output = tmp_path / "stamped.msi"

        stamp_msi(str(base), str(output), **SAMPLE_CONFIG)

        stamped_data = output.read_bytes()
        assert stamped_data[: len(FAKE_MSI_BYTES)] == FAKE_MSI_BYTES

    def test_idempotency_produces_valid_output(self, tmp_path) -> None:
        """Stamping the same base twice produces two independent valid outputs."""
        base = tmp_path / "base.msi"
        _create_fake_msi(base)

        out1 = tmp_path / "stamped_1.msi"
        out2 = tmp_path / "stamped_2.msi"

        stamp_msi(str(base), str(out1), **SAMPLE_CONFIG)
        stamp_msi(str(base), str(out2), **SAMPLE_CONFIG)

        config1 = _read_trailer_config(out1)
        config2 = _read_trailer_config(out2)
        assert config1 == config2
        # Both files should be the same size since the base and config are identical.
        assert out1.stat().st_size == out2.stat().st_size

    def test_return_value_is_output_path(self, tmp_path) -> None:
        base = tmp_path / "base.msi"
        _create_fake_msi(base)
        output = tmp_path / "sub" / "dir" / "stamped.msi"
        output.parent.mkdir(parents=True)

        result = stamp_msi(str(base), str(output), **SAMPLE_CONFIG)
        assert result == str(output)


# ---------------------------------------------------------------------------
# _stamp_via_trailer -- low-level trailer append
# ---------------------------------------------------------------------------


class TestStampViaTrailer:
    """Tests for the trailer-based config embedding."""

    def test_config_is_json_serializable_in_trailer(self, tmp_path) -> None:
        target = tmp_path / "test.msi"
        target.write_bytes(FAKE_MSI_BYTES)

        _stamp_via_trailer(str(target), SAMPLE_CONFIG)

        config = _read_trailer_config(target)
        assert isinstance(config, dict)
        assert config == SAMPLE_CONFIG

    def test_trailer_appended_not_replacing(self, tmp_path) -> None:
        target = tmp_path / "test.msi"
        original = b"ORIGINAL_CONTENT_HERE"
        target.write_bytes(original)

        _stamp_via_trailer(str(target), SAMPLE_CONFIG)

        data = target.read_bytes()
        assert data.startswith(original)
        assert len(data) > len(original)

    def test_round_trip_write_then_read(self, tmp_path) -> None:
        """Config written via trailer can be read back identically."""
        target = tmp_path / "test.msi"
        target.write_bytes(FAKE_MSI_BYTES)

        config = {
            "api_url": "https://prod.example.com/v1",
            "api_key": "deadbeef" * 8,
            "tenant_id": "tn_roundtrip_001",
        }
        _stamp_via_trailer(str(target), config)

        recovered = _read_trailer_config(target)
        assert recovered == config

    def test_trailer_structure_has_two_markers(self, tmp_path) -> None:
        """The trailer contains exactly two copies of the magic marker."""
        target = tmp_path / "test.msi"
        target.write_bytes(b"")

        _stamp_via_trailer(str(target), {"key": "value"})

        data = target.read_bytes()
        assert data.count(MAGIC_MARKER) == 2

    def test_length_field_is_correct(self, tmp_path) -> None:
        """The 4-byte LE length field matches the actual JSON payload size."""
        target = tmp_path / "test.msi"
        target.write_bytes(b"")

        _stamp_via_trailer(str(target), SAMPLE_CONFIG)

        data = target.read_bytes()
        # Strip trailing marker, read length, verify against JSON.
        without_trailing = data[: -len(MAGIC_MARKER)]
        length = struct.unpack("<I", without_trailing[-4:])[0]
        json_bytes = without_trailing[-4 - length : -4]
        assert json.loads(json_bytes) == SAMPLE_CONFIG
        assert length == len(json.dumps(SAMPLE_CONFIG).encode("utf-8"))

    def test_unicode_values_in_config(self, tmp_path) -> None:
        """Config values with unicode characters survive the round trip."""
        target = tmp_path / "test.msi"
        target.write_bytes(FAKE_MSI_BYTES)

        config = {
            "api_url": "https://api.example.com",
            "api_key": "key123",
            "tenant_id": "tn_unicode_\u00e9\u00e0\u00fc",
        }
        _stamp_via_trailer(str(target), config)

        recovered = _read_trailer_config(target)
        assert recovered == config


# ---------------------------------------------------------------------------
# Input validation (security hardening -- future-proofing)
# ---------------------------------------------------------------------------


class TestInputValidation:
    """Tests for input validation in stamp_msi.

    These tests verify that dangerous config values are rejected before
    they can be embedded.  The stamp_msi function should raise ValueError
    for inputs containing SQL injection characters, since the msilib path
    uses SQL statements and even the trailer path should not accept
    obviously malicious payloads.

    Tests marked xfail(strict=False) document the expected validation
    behavior.  Input validation is now implemented in stamp_msi via
    _validate_stamp_value -- all injection payloads are rejected.
    """

    INJECTION_PAYLOADS = [
        pytest.param("backtick", "https://api.example.com`; DROP TABLE Property;--", id="backtick"),
        pytest.param("semicolon", "https://api.example.com; DROP TABLE users", id="semicolon"),
        pytest.param("single_quote_attack", "val'; INSERT INTO Property VALUES('x','y')--", id="single_quote_attack"),
        pytest.param("null_byte", "https://api.example.com\x00malicious", id="null_byte"),
        pytest.param("newline_injection", "https://api.example.com\nX-Injected: header", id="newline_injection"),
    ]

    SAFE_VALUES = [
        ("hostname", "https://api.detec.example.com"),
        ("hex_key", "a1b2c3d4e5f6" * 5),
        ("url_with_path", "https://api.example.com/v2/collect"),
        ("tenant_id", "tn_prod_abc123"),
        ("uuid_style", "550e8400-e29b-41d4-a716-446655440000"),
        ("url_with_port", "https://api.example.com:8443/api"),
    ]

    @pytest.mark.parametrize("name,payload", INJECTION_PAYLOADS)
    def test_rejects_injection_in_api_url(self, tmp_path, name, payload) -> None:
        base = tmp_path / "base.msi"
        _create_fake_msi(base)
        output = tmp_path / "out.msi"
        with pytest.raises((ValueError, TypeError)):
            stamp_msi(
                str(base),
                str(output),
                api_url=payload,
                api_key=SAMPLE_CONFIG["api_key"],
                tenant_id=SAMPLE_CONFIG["tenant_id"],
            )

    @pytest.mark.parametrize("name,payload", INJECTION_PAYLOADS)
    def test_rejects_injection_in_api_key(self, tmp_path, name, payload) -> None:
        base = tmp_path / "base.msi"
        _create_fake_msi(base)
        output = tmp_path / "out.msi"
        with pytest.raises((ValueError, TypeError)):
            stamp_msi(
                str(base),
                str(output),
                api_url=SAMPLE_CONFIG["api_url"],
                api_key=payload,
                tenant_id=SAMPLE_CONFIG["tenant_id"],
            )

    @pytest.mark.parametrize("name,value", SAFE_VALUES, ids=[v[0] for v in SAFE_VALUES])
    def test_accepts_safe_values(self, tmp_path, name, value) -> None:
        base = tmp_path / "base.msi"
        _create_fake_msi(base)
        output = tmp_path / "out.msi"
        # Should not raise -- safe values are allowed.
        result = stamp_msi(
            str(base),
            str(output),
            api_url=value,
            api_key=value,
            tenant_id=value,
        )
        assert output.exists()
        assert result == str(output)
