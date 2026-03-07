"""Base scanner interface and shared data structures."""

from __future__ import annotations

import logging
import subprocess
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class LayerSignals:
    """Per-layer signal strengths and contributing evidence."""

    process: float = 0.0
    file: float = 0.0
    network: float = 0.0
    identity: float = 0.0
    behavior: float = 0.0

    def active_layers(self) -> list[str]:
        """Return names of layers with non-zero signal."""
        layers = []
        for name in ("process", "file", "network", "identity", "behavior"):
            if getattr(self, name) > 0.0:
                layers.append(name)
        return layers


@dataclass
class ScanResult:
    """Output of a single tool scanner."""

    detected: bool
    tool_name: str | None = None
    tool_class: str | None = None  # A, B, C, or D
    tool_version: str | None = None
    signals: LayerSignals = field(default_factory=LayerSignals)
    penalties: list[tuple[str, float]] = field(default_factory=list)
    evidence_details: dict[str, Any] = field(default_factory=dict)
    action_summary: str = ""
    action_type: str = "exec"
    action_risk: str = "R1"
    evasion_boost: float = 0.0


class BaseScanner(ABC):
    """Abstract base for tool-specific scanners."""

    @property
    @abstractmethod
    def tool_name(self) -> str:
        ...

    @property
    @abstractmethod
    def tool_class(self) -> str:
        ...

    @abstractmethod
    def scan(self, verbose: bool = False) -> ScanResult:
        ...

    def _run_cmd(self, args: list[str], timeout: int = 10) -> subprocess.CompletedProcess[str] | None:
        """Run a subprocess, returning None on any failure."""
        try:
            return subprocess.run(
                args, capture_output=True, text=True, timeout=timeout
            )
        except (subprocess.TimeoutExpired, FileNotFoundError, PermissionError, OSError) as exc:
            logger.debug("Command %s failed: %s", args, exc)
            return None

    def _log(self, msg: str, verbose: bool) -> None:
        if verbose:
            print(f"  [{self.tool_name}] {msg}")
        logger.debug("[%s] %s", self.tool_name, msg)

    # -- Common penalty helpers (Appendix B) --------------------------------

    @staticmethod
    def _penalize_weak_identity(
        result: "ScanResult", threshold: float = 0.4, amount: float = 0.10
    ) -> None:
        if result.signals.identity < threshold:
            result.penalties.append(("weak_identity_correlation", amount))

    @staticmethod
    def _penalize_stale_artifacts(
        result: "ScanResult",
        amount: float = 0.10,
        require_no_network: bool = False,
    ) -> None:
        if result.signals.file > 0 and result.signals.process == 0:
            if require_no_network and result.signals.network > 0:
                return
            result.penalties.append(("stale_artifact_only", amount))

    @staticmethod
    def _penalize_missing_process_chain(
        result: "ScanResult",
        evidence_key: str,
        amount: float = 0.15,
    ) -> None:
        if result.signals.process > 0 and not result.evidence_details.get(evidence_key):
            result.penalties.append(("missing_parent_child_chain", amount))
