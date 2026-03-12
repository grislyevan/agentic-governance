"""Consistency checks: every scanner must populate ScanResult fields correctly.

These tests don't require a real detection. They verify that each scanner:
  - Declares valid tool_name and tool_class properties
  - Returns a ScanResult with valid action_type, action_risk, and action_summary
  - Populates signals as a LayerSignals instance
"""

from __future__ import annotations

import pytest

from scanner.ai_extensions import AIExtensionScanner
from scanner.aider import AiderScanner
from scanner.claude_code import ClaudeCodeScanner
from scanner.claude_cowork import ClaudeCoworkScanner
from scanner.cline import ClineScanner
from scanner.continue_ext import ContinueScanner
from scanner.copilot import CopilotScanner
from scanner.cursor import CursorScanner
from scanner.gpt_pilot import GPTPilotScanner
from scanner.lm_studio import LMStudioScanner
from scanner.ollama import OllamaScanner
from scanner.open_interpreter import OpenInterpreterScanner
from scanner.openclaw import OpenClawScanner
from scanner.base import BaseScanner, LayerSignals, ScanResult

VALID_TOOL_CLASSES = {"A", "B", "C", "D"}
VALID_ACTION_RISKS = {"R1", "R2", "R3", "R4"}
VALID_ACTION_TYPES = {"exec", "read", "write", "observe", "warn", "approval_required", "none", "removal"}

ALL_SCANNERS: list[type[BaseScanner]] = [
    AIExtensionScanner,
    AiderScanner,
    ClaudeCodeScanner,
    ClaudeCoworkScanner,
    ClineScanner,
    ContinueScanner,
    CopilotScanner,
    CursorScanner,
    GPTPilotScanner,
    LMStudioScanner,
    OllamaScanner,
    OpenInterpreterScanner,
    OpenClawScanner,
]


@pytest.fixture(params=ALL_SCANNERS, ids=lambda cls: cls.__name__)
def scanner(request: pytest.FixtureRequest) -> BaseScanner:
    return request.param()


class TestScannerProperties:
    """Verify every scanner declares valid metadata."""

    def test_tool_name_is_nonempty_string(self, scanner: BaseScanner) -> None:
        assert isinstance(scanner.tool_name, str)
        assert len(scanner.tool_name) > 0

    def test_tool_class_is_valid(self, scanner: BaseScanner) -> None:
        assert scanner.tool_class in VALID_TOOL_CLASSES, (
            f"{type(scanner).__name__}.tool_class = {scanner.tool_class!r}"
        )


class TestScanResultContract:
    """Verify ScanResult fields from a real (probably negative) scan."""

    def test_scan_returns_scan_result(self, scanner: BaseScanner) -> None:
        result = scanner.scan(verbose=False)
        assert isinstance(result, ScanResult)

    def test_signals_is_layer_signals(self, scanner: BaseScanner) -> None:
        result = scanner.scan(verbose=False)
        assert isinstance(result.signals, LayerSignals)

    def test_action_risk_is_valid(self, scanner: BaseScanner) -> None:
        result = scanner.scan(verbose=False)
        assert result.action_risk in VALID_ACTION_RISKS, (
            f"{type(scanner).__name__} returned action_risk={result.action_risk!r}"
        )

    def test_action_type_is_valid(self, scanner: BaseScanner) -> None:
        result = scanner.scan(verbose=False)
        assert result.action_type in VALID_ACTION_TYPES, (
            f"{type(scanner).__name__} returned action_type={result.action_type!r}"
        )

    def test_action_summary_is_string(self, scanner: BaseScanner) -> None:
        result = scanner.scan(verbose=False)
        assert isinstance(result.action_summary, str)

    def test_tool_name_matches_scanner(self, scanner: BaseScanner) -> None:
        result = scanner.scan(verbose=False)
        if result.detected:
            assert result.tool_name == scanner.tool_name

    def test_tool_class_matches_scanner_when_detected(self, scanner: BaseScanner) -> None:
        result = scanner.scan(verbose=False)
        if result.detected and result.tool_class is not None:
            assert result.tool_class in VALID_TOOL_CLASSES
