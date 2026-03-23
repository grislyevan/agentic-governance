"""Integration tests for ClineScanner with synthetic file fixtures and mocked subprocesses."""

from __future__ import annotations

import contextlib
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scanner.cline import ClineScanner
from tests.fixtures.canned_responses import CLINE_NOT_RUNNING, make_dispatcher
from tests.fixtures.compat_fixtures import make_cline_compat_mocks
from tests.fixtures.file_fixtures import create_cline_footprint


def _cline_patches(home, *, active: bool, extra=None):
    """Build the standard patch list for ClineScanner tests."""
    find_proc, get_conn, get_paths = make_cline_compat_mocks(home, active=active)
    cms = [
        patch("scanner.cline.find_processes", find_proc),
        patch("scanner.cline.get_connections", get_conn),
        patch("scanner.cline.get_tool_paths", get_paths),
        patch.object(ClineScanner, "_run_cmd", make_dispatcher(CLINE_NOT_RUNNING)),
    ]
    if extra:
        cms.extend(extra)
    return cms


@contextlib.contextmanager
def _apply(patches):
    with contextlib.ExitStack() as stack:
        for p in patches:
            stack.enter_context(p)
        yield


class TestClineCleanSystem(unittest.TestCase):
    """Scenario: no Cline extension, no tasks, no processes."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.home = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_clean_system_no_meaningful_signals(self):
        """Identity layer always returns >= 0.25 (getpass), so detected may be
        True, but process/file/network/behavior should all be zero."""
        env_clean = {k: v for k, v in os.environ.items()
                     if k not in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY")}
        patches = _cline_patches(
            self.home, active=False,
            extra=[patch.dict(os.environ, env_clean, clear=True)],
        )
        with _apply(patches):
            scanner = ClineScanner()
            result = scanner.scan(verbose=False)

        self.assertEqual(result.signals.process, 0.0)
        self.assertEqual(result.signals.file, 0.0)
        self.assertEqual(result.signals.network, 0.0)
        self.assertEqual(result.signals.behavior, 0.0)
        self.assertGreaterEqual(result.signals.identity, 0.25)


class TestClineExtensionInstalled(unittest.TestCase):
    """Scenario: Cline extension installed but no task history."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.home = Path(self._tmp.name)
        create_cline_footprint(
            self.home, with_extension=True, with_tasks=False,
        )

    def tearDown(self):
        self._tmp.cleanup()

    def test_extension_only(self):
        patches = _cline_patches(self.home, active=False)
        with _apply(patches):
            scanner = ClineScanner()
            result = scanner.scan(verbose=False)

        self.assertTrue(result.detected)
        self.assertGreaterEqual(result.signals.file, 0.65)
        self.assertEqual(result.signals.process, 0.0)
        self.assertIn("extension_installs", result.evidence_details)
        self.assertEqual(result.tool_class, "A")
        self.assertEqual(result.action_risk, "R1")


class TestClineTaskHistoryClassA(unittest.TestCase):
    """Scenario: Cline has task history but no tool-call or write ops — stays Class A."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.home = Path(self._tmp.name)
        create_cline_footprint(
            self.home,
            with_extension=True,
            with_tasks=True,
            tool_calls=False,
            write_ops=False,
            task_count=5,
        )

    def tearDown(self):
        self._tmp.cleanup()

    def test_tasks_without_tool_calls_class_a(self):
        patches = _cline_patches(self.home, active=False)
        with _apply(patches):
            scanner = ClineScanner()
            result = scanner.scan(verbose=False)

        self.assertTrue(result.detected)
        self.assertGreaterEqual(result.signals.file, 0.75)
        self.assertGreaterEqual(result.signals.behavior, 0.55)
        self.assertEqual(result.tool_class, "A")
        self.assertEqual(result.evidence_details.get("task_count"), 5)


class TestClineToolCallsClassC(unittest.TestCase):
    """Scenario: Cline's latest task has tool_use entries — escalates to Class C."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.home = Path(self._tmp.name)
        create_cline_footprint(
            self.home,
            with_extension=True,
            with_tasks=True,
            tool_calls=True,
            write_ops=False,
        )

    def tearDown(self):
        self._tmp.cleanup()

    def test_tool_calls_escalate_to_class_c(self):
        patches = _cline_patches(self.home, active=True)
        with _apply(patches):
            scanner = ClineScanner()
            result = scanner.scan(verbose=True)

        self.assertTrue(result.detected)
        self.assertEqual(result.tool_class, "C")
        self.assertGreater(result.evidence_details.get("tool_calls_in_last_task", 0), 0)
        self.assertGreaterEqual(result.signals.behavior, 0.70)
        self.assertIn(result.action_risk, ("R1", "R2"))


class TestClineWriteOpsClassCR3(unittest.TestCase):
    """Scenario: Cline's latest task has write_to_file + execute_command — Class C, R3."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.home = Path(self._tmp.name)
        create_cline_footprint(
            self.home,
            with_extension=True,
            with_tasks=True,
            tool_calls=True,
            write_ops=True,
        )

    def tearDown(self):
        self._tmp.cleanup()

    def test_write_ops_class_c_r3(self):
        patches = _cline_patches(self.home, active=True)
        with _apply(patches):
            scanner = ClineScanner()
            result = scanner.scan(verbose=True)

        self.assertTrue(result.detected)
        self.assertEqual(result.tool_class, "C")
        self.assertGreater(result.evidence_details.get("write_ops_in_last_task", 0), 0)
        self.assertGreaterEqual(result.signals.behavior, 0.85)
        self.assertEqual(result.action_type, "exec")
        self.assertEqual(result.action_risk, "R3")


if __name__ == "__main__":
    unittest.main()
