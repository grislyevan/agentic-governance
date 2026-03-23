"""Unit tests for OpenInterpreterScanner."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from compat.types import ConnectionInfo, ProcessInfo
from scanner.open_interpreter import OpenInterpreterScanner


class TestOpenInterpreterScanner(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.home = Path(self._tmp.name)
        self.pkg = self.home / "venv" / "lib" / "python3.12" / "site-packages" / "interpreter"
        self.pkg.mkdir(parents=True, exist_ok=True)
        (self.pkg / "__init__.py").write_text("__version__='1.0.0'")
        for dep in ("litellm", "anthropic", "openai"):
            (self.pkg.parent / dep).mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        self._tmp.cleanup()

    def test_positive_detection_active_chain(self):
        proc = ProcessInfo(pid=9101, name="python", cmdline="python -m interpreter --auto_run", username="u", ppid=1)

        def find_processes(_name: str):
            return [proc]

        def get_info(pid: int):
            mapping = {
                9101: proc,
                9102: ProcessInfo(pid=9102, name="python", cmdline="python -m ipykernel", username="u", ppid=9101),
                9103: ProcessInfo(pid=9103, name="bash", cmdline="bash -lc pytest", username="u", ppid=9102),
            }
            return mapping.get(pid)

        def child_pids(pid: int):
            return {9101: [9102], 9102: [9103]}.get(pid, [])

        with (
            patch("scanner.open_interpreter.find_processes", side_effect=find_processes),
            patch("scanner.open_interpreter.get_process_info", side_effect=get_info),
            patch("scanner.open_interpreter.get_child_pids", side_effect=child_pids),
            patch("scanner.open_interpreter.get_connections", return_value=[ConnectionInfo(pid=9102, local_addr="127.0.0.1", local_port=54001, remote_addr="api.openai.com", remote_port=443, status="ESTABLISHED")]),
            patch.object(OpenInterpreterScanner, "_find_interpreter_packages", return_value=[self.pkg]),
            patch.object(OpenInterpreterScanner, "_run_cmd", return_value=None),
            patch.dict("os.environ", {"OPENAI_API_KEY": "k"}, clear=True),
        ):
            result = OpenInterpreterScanner().scan(verbose=False)

        self.assertTrue(result.detected)
        self.assertGreaterEqual(result.signals.behavior, 0.9)
        self.assertEqual(result.action_risk, "R3")
        self.assertGreater(result.evasion_boost, 0.0)

    def test_negative_no_signal(self):
        with (
            patch("scanner.open_interpreter.find_processes", return_value=[]),
            patch("scanner.open_interpreter.get_connections", return_value=[]),
            patch.object(OpenInterpreterScanner, "_find_interpreter_packages", return_value=[]),
            patch.object(OpenInterpreterScanner, "_run_cmd", return_value=None),
            patch.dict("os.environ", {}, clear=True),
        ):
            result = OpenInterpreterScanner().scan(verbose=False)

        self.assertFalse(result.detected)

    def test_stale_artifacts_vs_active_behavior(self):
        with (
            patch("scanner.open_interpreter.find_processes", return_value=[]),
            patch("scanner.open_interpreter.get_connections", return_value=[]),
            patch.object(OpenInterpreterScanner, "_find_interpreter_packages", return_value=[self.pkg]),
            patch.object(OpenInterpreterScanner, "_run_cmd", return_value=None),
            patch.dict("os.environ", {}, clear=True),
        ):
            result = OpenInterpreterScanner().scan(verbose=False)

        self.assertTrue(result.detected)
        self.assertEqual(result.signals.process, 0.0)
        self.assertGreaterEqual(result.signals.file, 0.8)
        self.assertEqual(result.signals.behavior, 0.4)

    def test_confidence_penalties(self):
        proc = ProcessInfo(pid=9201, name="python", cmdline="python -m interpreter", username="u", ppid=1)
        with (
            patch("scanner.open_interpreter.find_processes", return_value=[proc]),
            patch("scanner.open_interpreter.get_process_info", return_value=proc),
            patch("scanner.open_interpreter.get_child_pids", return_value=[]),
            patch("scanner.open_interpreter.get_connections", return_value=[]),
            patch.object(OpenInterpreterScanner, "_find_interpreter_packages", return_value=[self.pkg]),
            patch.object(OpenInterpreterScanner, "_run_cmd", return_value=None),
            patch.dict("os.environ", {}, clear=True),
        ):
            result = OpenInterpreterScanner().scan(verbose=False)

        self.assertIn(("non_default_artifact_paths", 0.05), result.penalties)
        self.assertIn(("unresolved_process_network_linkage", 0.05), result.penalties)
        self.assertIn(("weak_identity_correlation", 0.05), result.penalties)


if __name__ == "__main__":
    unittest.main()
