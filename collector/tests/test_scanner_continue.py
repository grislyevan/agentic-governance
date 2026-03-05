"""Integration tests for ContinueScanner with synthetic file fixtures and mocked subprocesses."""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scanner.continue_ext import ContinueScanner
from tests.fixtures.canned_responses import (
    CONTINUE_ACTIVE,
    CONTINUE_APPROVED_ACTIVE,
    CONTINUE_NOT_RUNNING,
    EMPTY,
    make_dispatcher,
)
from tests.fixtures.file_fixtures import create_continue_footprint


class TestContinueCleanSystem(unittest.TestCase):
    """Scenario: no Continue config, no extension, no processes."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.home = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_clean_system_no_meaningful_signals(self):
        """Identity layer always returns >= 0.25 (getpass), so detected may be
        True, but process/file/network/behavior should all be zero."""
        env_clean = {k: v for k, v in os.environ.items()
                     if k not in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GOOGLE_API_KEY")}
        with (
            patch("scanner.continue_ext.HOME", self.home),
            patch("scanner.continue_ext.CONTINUE_DIR", self.home / ".continue"),
            patch("scanner.continue_ext.ALL_EXT_DIRS", [
                self.home / ".vscode" / "extensions",
                self.home / ".cursor" / "extensions",
            ]),
            patch("scanner.continue_ext.VSCODE_EXT_DIRS", [self.home / ".vscode" / "extensions"]),
            patch("scanner.continue_ext.CURSOR_EXT_DIRS", [self.home / ".cursor" / "extensions"]),
            patch("scanner.continue_ext.VSCODE_STORAGE", self.home / "Library" / "Application Support" / "Code" / "User" / "globalStorage"),
            patch("scanner.continue_ext.CURSOR_STORAGE", self.home / "Library" / "Application Support" / "Cursor" / "User" / "globalStorage"),
            patch.object(ContinueScanner, "_run_cmd", make_dispatcher(CONTINUE_NOT_RUNNING)),
            patch.dict(os.environ, env_clean, clear=True),
        ):
            scanner = ContinueScanner()
            result = scanner.scan(verbose=False)

        self.assertEqual(result.signals.process, 0.0)
        self.assertEqual(result.signals.file, 0.0)
        self.assertEqual(result.signals.network, 0.0)
        self.assertEqual(result.signals.behavior, 0.0)
        self.assertGreaterEqual(result.signals.identity, 0.25)


class _ContinueTestBase(unittest.TestCase):
    """Shared setUp/tearDown and patching helpers for Continue tests."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.home = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def _patches(self, responses, *, extra_patches=None):
        """Return a list of context managers for the standard Continue patches."""
        cms = [
            patch("scanner.continue_ext.HOME", self.home),
            patch("scanner.continue_ext.CONTINUE_DIR", self.home / ".continue"),
            patch("scanner.continue_ext.ALL_EXT_DIRS", [
                self.home / ".vscode" / "extensions",
                self.home / ".cursor" / "extensions",
            ]),
            patch("scanner.continue_ext.VSCODE_EXT_DIRS", [self.home / ".vscode" / "extensions"]),
            patch("scanner.continue_ext.CURSOR_EXT_DIRS", [self.home / ".cursor" / "extensions"]),
            patch("scanner.continue_ext.VSCODE_STORAGE", self.home / "Library" / "Application Support" / "Code" / "User" / "globalStorage"),
            patch("scanner.continue_ext.CURSOR_STORAGE", self.home / "Library" / "Application Support" / "Cursor" / "User" / "globalStorage"),
            patch.object(ContinueScanner, "_run_cmd", make_dispatcher(responses)),
        ]
        if extra_patches:
            cms.extend(extra_patches)
        return cms


class TestContinueInstalledNotRunning(_ContinueTestBase):
    """Scenario: Continue config + extension present, IDE not running."""

    def test_installed_detects_file_layer(self):
        create_continue_footprint(self.home, backends=["anthropic"])

        patches = self._patches(CONTINUE_NOT_RUNNING)
        with _apply_patches(patches):
            scanner = ContinueScanner()
            result = scanner.scan(verbose=False)

        self.assertTrue(result.detected)
        self.assertGreaterEqual(result.signals.file, 0.55)
        self.assertEqual(result.signals.process, 0.0)
        self.assertIn("config_file", result.evidence_details)
        self.assertIn("extension_installs", result.evidence_details)
        self.assertEqual(result.action_risk, "R1")


class TestContinueApprovedBackendActive(_ContinueTestBase):
    """Scenario: Continue with approved (anthropic) backend, Cursor running."""

    def test_approved_backend_active(self):
        create_continue_footprint(self.home, backends=["anthropic"])

        patches = self._patches(CONTINUE_APPROVED_ACTIVE)
        with _apply_patches(patches):
            scanner = ContinueScanner()
            result = scanner.scan(verbose=True)

        self.assertTrue(result.detected)
        self.assertGreaterEqual(result.signals.file, 0.55)
        self.assertGreaterEqual(result.signals.process, 0.30)
        self.assertEqual(result.evasion_boost, 0.0)
        self.assertEqual(result.action_risk, "R1")
        self.assertNotIn("unapproved_backends", result.evidence_details)


class TestContinueUnapprovedBackend(_ContinueTestBase):
    """Scenario: Continue configured with Ollama backend — risk escalation."""

    def test_unapproved_ollama_backend(self):
        create_continue_footprint(self.home, backends=["ollama"])

        patches = self._patches(CONTINUE_ACTIVE)
        with _apply_patches(patches):
            scanner = ContinueScanner()
            result = scanner.scan(verbose=True)

        self.assertTrue(result.detected)
        self.assertGreaterEqual(result.signals.file, 0.55)
        self.assertGreater(result.evasion_boost, 0.0)
        self.assertEqual(result.action_risk, "R2")
        self.assertIn("unapproved_backends", result.evidence_details)
        self.assertIn("ollama", result.evidence_details["unapproved_backends"])

    def test_mixed_backends_flags_unapproved(self):
        """Config with both approved and unapproved backends still flags risk."""
        create_continue_footprint(self.home, backends=["anthropic", "ollama", "lmstudio"])

        patches = self._patches(CONTINUE_NOT_RUNNING)
        with _apply_patches(patches):
            scanner = ContinueScanner()
            result = scanner.scan(verbose=False)

        self.assertTrue(result.detected)
        self.assertIn("unapproved_backends", result.evidence_details)
        unapproved = result.evidence_details["unapproved_backends"]
        self.assertGreaterEqual(len(unapproved), 2)
        self.assertEqual(result.action_risk, "R2")


def _apply_patches(patches):
    """Combine multiple patch context managers into one."""
    import contextlib
    return contextlib.ExitStack().__enter__() if not patches else _StackCM(patches)


class _StackCM:
    """Thin wrapper to enter/exit a list of context managers."""

    def __init__(self, cms):
        self._cms = cms
        self._stack = None

    def __enter__(self):
        import contextlib
        self._stack = contextlib.ExitStack()
        self._stack.__enter__()
        for cm in self._cms:
            self._stack.enter_context(cm)
        return self

    def __exit__(self, *exc):
        return self._stack.__exit__(*exc)


if __name__ == "__main__":
    unittest.main()
