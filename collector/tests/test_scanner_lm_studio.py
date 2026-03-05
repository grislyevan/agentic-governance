"""Integration tests for LMStudioScanner with synthetic file fixtures and mocked subprocesses."""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scanner.lm_studio import LMStudioScanner
from tests.fixtures.canned_responses import (
    EMPTY,
    LM_STUDIO_NOT_RUNNING,
    LM_STUDIO_RUNNING,
    make_dispatcher,
)
from tests.fixtures.file_fixtures import create_lm_studio_footprint


class TestLMStudioCleanSystem(unittest.TestCase):
    """Scenario: no LM Studio artifacts, no processes."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.home = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_clean_system_not_detected(self):
        env_clean = {k: v for k, v in os.environ.items()
                     if k not in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY")}
        with (
            patch("scanner.lm_studio.HOME", self.home),
            patch("scanner.lm_studio.APP_PATH", self.home / "Applications" / "LM Studio.app"),
            patch("scanner.lm_studio.APP_SUPPORT_DIR", self.home / "Library" / "Application Support" / "LM Studio"),
            patch("scanner.lm_studio.CACHE_DIR", self.home / "Library" / "Caches" / "LM Studio"),
            patch.object(LMStudioScanner, "_run_cmd", make_dispatcher(LM_STUDIO_NOT_RUNNING)),
            patch.object(LMStudioScanner, "_query_api", return_value=None),
            patch.dict(os.environ, env_clean, clear=True),
        ):
            scanner = LMStudioScanner()
            result = scanner.scan(verbose=False)

        self.assertFalse(result.detected)
        self.assertEqual(result.signals.process, 0.0)
        self.assertEqual(result.signals.file, 0.0)
        self.assertEqual(result.signals.network, 0.0)
        self.assertEqual(result.signals.behavior, 0.0)


class TestLMStudioInstalledNotRunning(unittest.TestCase):
    """Scenario: LM Studio installed with model files but not running."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.home = Path(self._tmp.name)
        self.app_path = self.home / "Applications" / "LM Studio.app"
        self.app_support = create_lm_studio_footprint(
            self.home, with_app=True, with_models=True, app_path=self.app_path,
        )

    def tearDown(self):
        self._tmp.cleanup()

    def test_installed_detects_file_layer(self):
        with (
            patch("scanner.lm_studio.HOME", self.home),
            patch("scanner.lm_studio.APP_PATH", self.app_path),
            patch("scanner.lm_studio.APP_SUPPORT_DIR", self.app_support),
            patch("scanner.lm_studio.CACHE_DIR", self.home / "Library" / "Caches" / "LM Studio"),
            patch.object(LMStudioScanner, "_run_cmd", make_dispatcher(LM_STUDIO_NOT_RUNNING)),
            patch.object(LMStudioScanner, "_query_api", return_value=None),
        ):
            scanner = LMStudioScanner()
            result = scanner.scan(verbose=False)

        self.assertTrue(result.detected)
        self.assertGreaterEqual(result.signals.file, 0.55)
        self.assertEqual(result.signals.process, 0.0)
        self.assertEqual(result.signals.network, 0.0)
        self.assertIn("app_support_dir", result.evidence_details)
        self.assertGreater(result.evidence_details.get("model_file_count", 0), 0)
        self.assertEqual(result.action_risk, "R1")


class TestLMStudioFullyActive(unittest.TestCase):
    """Scenario: LM Studio running with local server on :1234 and loaded models."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.home = Path(self._tmp.name)
        self.app_path = self.home / "Applications" / "LM Studio.app"
        self.app_support = create_lm_studio_footprint(
            self.home, with_app=True, with_models=True, app_path=self.app_path,
        )

    def tearDown(self):
        self._tmp.cleanup()

    def test_fully_active_all_layers(self):
        api_response = json.dumps({
            "data": [{"id": "tinyllama-1.1b-chat-v1.0"}],
        })

        with (
            patch("scanner.lm_studio.HOME", self.home),
            patch("scanner.lm_studio.APP_PATH", self.app_path),
            patch("scanner.lm_studio.APP_SUPPORT_DIR", self.app_support),
            patch("scanner.lm_studio.CACHE_DIR", self.home / "Library" / "Caches" / "LM Studio"),
            patch.object(LMStudioScanner, "_run_cmd", make_dispatcher(LM_STUDIO_RUNNING)),
            patch.object(LMStudioScanner, "_query_api", return_value=api_response),
        ):
            scanner = LMStudioScanner()
            result = scanner.scan(verbose=True)

        self.assertTrue(result.detected)
        self.assertGreaterEqual(result.signals.process, 0.50)
        self.assertGreaterEqual(result.signals.file, 0.55)
        self.assertGreaterEqual(result.signals.network, 0.70)
        self.assertGreaterEqual(result.signals.behavior, 0.65)
        self.assertTrue(result.evidence_details.get("app_running"))
        self.assertTrue(result.evidence_details.get("local_server_active"))
        self.assertIn("api_models", result.evidence_details)
        self.assertEqual(result.action_risk, "R2")

    def test_server_without_api_response(self):
        """Server listening but no model loaded — still detects network layer."""
        with (
            patch("scanner.lm_studio.HOME", self.home),
            patch("scanner.lm_studio.APP_PATH", self.app_path),
            patch("scanner.lm_studio.APP_SUPPORT_DIR", self.app_support),
            patch("scanner.lm_studio.CACHE_DIR", self.home / "Library" / "Caches" / "LM Studio"),
            patch.object(LMStudioScanner, "_run_cmd", make_dispatcher(LM_STUDIO_RUNNING)),
            patch.object(LMStudioScanner, "_query_api", return_value=None),
        ):
            scanner = LMStudioScanner()
            result = scanner.scan(verbose=False)

        self.assertTrue(result.detected)
        self.assertGreaterEqual(result.signals.network, 0.70)
        self.assertTrue(result.evidence_details.get("local_server_active"))
        self.assertNotIn("api_models", result.evidence_details)


if __name__ == "__main__":
    unittest.main()
