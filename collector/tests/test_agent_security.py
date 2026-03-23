"""Collector self-defense and config security tests.

Validates that tampered or malicious config is handled safely and that
TLS/SSL is used for API connections.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest


class TestConfigTampering:
    """Config loader must handle invalid or malicious-looking config safely."""

    def test_load_config_invalid_json_returns_empty(self) -> None:
        from collector.config_loader import load_config_file
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as f:
            f.write("not valid json {")
            path = Path(f.name)
        try:
            result = load_config_file(path)
            assert result == {}
        finally:
            path.unlink(missing_ok=True)

    def test_load_config_non_dict_json_returns_empty(self) -> None:
        from collector.config_loader import load_config_file
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as f:
            json.dump(["array", "not", "object"], f)
            path = Path(f.name)
        try:
            result = load_config_file(path)
            assert result == {}
        finally:
            path.unlink(missing_ok=True)

    def test_load_config_nonexistent_path_returns_empty(self) -> None:
        from collector.config_loader import load_config_file
        path = Path("/nonexistent/collector.json")
        result = load_config_file(path)
        assert result == {}

    def test_load_config_with_api_url_does_not_crash(self) -> None:
        from collector.config_loader import load_config_file
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as f:
            json.dump({"api_url": "https://api.example.com/api", "api_key": "x"}, f)
            path = Path(f.name)
        try:
            result = load_config_file(path)
            assert "api_url" in result
            assert result["api_url"] == "https://api.example.com/api"
        finally:
            path.unlink(missing_ok=True)

    def test_load_config_strips_private_keys(self) -> None:
        from collector.config_loader import load_config_file
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as f:
            json.dump({"api_url": "https://x.com", "_private": "ignored", "config_version": 1}, f)
            path = Path(f.name)
        try:
            result = load_config_file(path)
            assert "api_url" in result
            assert "_private" not in result
            assert "config_version" not in result
        finally:
            path.unlink(missing_ok=True)


class TestHttpEmitterTLS:
    """HTTP emitter must use TLS and default SSL context for HTTPS."""

    def test_http_emitter_uses_ssl_context(self) -> None:
        from collector.output.http_emitter import HttpEmitter
        emitter = HttpEmitter(
            api_url="https://localhost:8000/api",
            api_key="test-key",
        )
        assert hasattr(emitter, "_ssl_ctx")
        assert emitter._ssl_ctx is not None

    def test_http_emitter_https_url_uses_secure_scheme(self) -> None:
        from collector.output.http_emitter import HttpEmitter
        emitter = HttpEmitter(
            api_url="https://api.example.com/api",
            api_key="key",
        )
        assert emitter._api_url.startswith("https://")
