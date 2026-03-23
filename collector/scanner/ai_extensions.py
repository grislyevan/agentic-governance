"""Generic AI extension discovery scanner for VS Code and Cursor.

Enumerates installed extensions, reads each package.json for AI-relevant
metadata (keywords, categories, description), and reports unknown AI extensions
that are not already covered by a dedicated scanner. The goal is visibility
into shadow AI tooling, not enforcement.
"""

from __future__ import annotations

import getpass
import json
import logging
import re
from pathlib import Path

from compat import get_tool_paths

from .base import BaseScanner, LayerSignals, ScanResult

logger = logging.getLogger(__name__)

# Extension prefixes handled by dedicated scanners; skip these.
_COVERED_PREFIXES = (
    "github.copilot",
    "saoudrizwan.claude-dev",
    "continue.continue",
)

_AI_KEYWORDS = {
    "ai", "artificial intelligence", "machine learning", "ml",
    "llm", "large language model", "gpt", "chatgpt", "copilot",
    "code generation", "ai code completion",
    "agent", "autonomous", "chatbot", "neural", "deep learning",
    "generative", "diffusion", "embedding", "transformer",
    "openai", "anthropic", "gemini", "claude", "ollama",
    "inference", "prompt", "rag", "retrieval augmented",
}

_AI_CATEGORIES = {"Machine Learning", "Data Science"}

_AI_DESCRIPTION_PATTERN = re.compile(
    r"\b(ai[- ]powered|ai[- ]assisted|ai[- ]driven|machine learning"
    r"|code generation|llm|large language model|generative ai"
    r"|copilot|chatbot|neural network|deep learning)\b",
    re.IGNORECASE,
)


def _all_extension_dirs() -> list[tuple[str, Path]]:
    """Return (ide_label, extensions_dir) pairs for Cursor and VS Code."""
    dirs: list[tuple[str, Path]] = []
    for tool_key, label in [("cursor", "Cursor"), ("vscode", "VSCode")]:
        paths = get_tool_paths(tool_key)
        if paths.extensions_dir:
            dirs.append((label, paths.extensions_dir))
    return dirs


def _is_covered(ext_name: str) -> bool:
    """True if this extension is handled by a dedicated scanner."""
    lower = ext_name.lower()
    return any(lower.startswith(prefix) for prefix in _COVERED_PREFIXES)


def _score_ai_relevance(manifest: dict) -> tuple[float, list[str]]:
    """Score how likely an extension is AI-related based on its package.json.

    Returns (score 0.0-1.0, list of matching signals).
    """
    signals: list[str] = []
    score = 0.0

    keywords = [str(k).lower() for k in manifest.get("keywords", []) if isinstance(k, str)]
    matched_kw = _AI_KEYWORDS & set(keywords)
    if matched_kw:
        score += min(0.4, len(matched_kw) * 0.15)
        signals.append(f"keywords: {', '.join(sorted(matched_kw))}")

    categories = [str(c) for c in manifest.get("categories", []) if isinstance(c, str)]
    matched_cat = _AI_CATEGORIES & set(categories)
    if matched_cat:
        score += 0.25
        signals.append(f"categories: {', '.join(sorted(matched_cat))}")

    description = str(manifest.get("description", ""))
    desc_match = _AI_DESCRIPTION_PATTERN.search(description)
    if desc_match:
        score += 0.25
        signals.append(f"description match: {desc_match.group(0)!r}")

    display_name = str(manifest.get("displayName", ""))
    name_match = _AI_DESCRIPTION_PATTERN.search(display_name)
    if name_match and not desc_match:
        score += 0.20
        signals.append(f"displayName match: {name_match.group(0)!r}")

    return min(score, 1.0), signals


class AIExtensionScanner(BaseScanner):
    """Discovers unknown AI-capable extensions in Cursor and VS Code."""

    @property
    def tool_name(self) -> str:
        return "AI Extensions (Discovery)"

    @property
    def tool_class(self) -> str:
        return "A"

    def scan(self, verbose: bool = False) -> ScanResult:
        result = ScanResult(
            detected=False,
            tool_name=self.tool_name,
            tool_class=self.tool_class,
        )

        file_strength = self._scan_file(result, verbose)
        identity_strength = self._scan_identity(result, verbose)

        result.signals = LayerSignals(
            process=0.0,
            file=file_strength,
            network=0.0,
            identity=identity_strength,
            behavior=0.0,
        )

        if result.evidence_details.get("discovered_extensions"):
            result.detected = True

        self._determine_action(result)
        if result.detected:
            result.process_patterns = ["ai-extension", "ai_extension"]
        return result

    def _scan_file(self, result: ScanResult, verbose: bool) -> float:
        """Enumerate extensions and score AI relevance from package.json."""
        self._log("Scanning extension directories...", verbose)
        strength = 0.0
        discovered: list[dict] = []

        for ide_label, ext_dir in _all_extension_dirs():
            if not ext_dir.is_dir():
                self._log(f"  {ide_label} extensions dir not found: {ext_dir}", verbose)
                continue

            self._log(f"  Scanning {ide_label}: {ext_dir}", verbose)
            try:
                for entry in sorted(ext_dir.iterdir()):
                    if not entry.is_dir():
                        continue
                    if _is_covered(entry.name):
                        continue

                    pkg_json = entry / "package.json"
                    if not pkg_json.is_file():
                        continue

                    try:
                        manifest = json.loads(pkg_json.read_text(errors="replace"))
                    except (json.JSONDecodeError, OSError) as exc:
                        logger.debug("Could not read %s: %s", pkg_json, exc)
                        continue

                    if not isinstance(manifest, dict):
                        continue

                    relevance, signals = _score_ai_relevance(manifest)
                    if relevance < 0.15:
                        continue

                    display_name = manifest.get("displayName", manifest.get("name", entry.name))
                    version = manifest.get("version", "unknown")
                    ext_id = entry.name

                    discovered.append({
                        "ide": ide_label,
                        "extension_id": ext_id,
                        "display_name": display_name,
                        "version": version,
                        "ai_relevance": round(relevance, 2),
                        "ai_signals": signals,
                    })
                    strength = max(strength, 0.60 + relevance * 0.20)
                    self._log(
                        f"    Found: {display_name} v{version} "
                        f"(relevance={relevance:.2f}, {', '.join(signals)})",
                        verbose,
                    )

            except (PermissionError, OSError) as exc:
                logger.debug("Could not iterate %s: %s", ext_dir, exc)

        if discovered:
            result.evidence_details["discovered_extensions"] = discovered
            result.evidence_details["discovered_count"] = len(discovered)
        else:
            self._log("  No unknown AI extensions found", verbose)

        return strength

    def _scan_identity(self, result: ScanResult, verbose: bool) -> float:
        self._log("Scanning identity layer...", verbose)
        result.evidence_details["identity_user"] = getpass.getuser()
        return 0.25

    def _determine_action(self, result: ScanResult) -> None:
        extensions = result.evidence_details.get("discovered_extensions", [])
        if not extensions:
            result.action_summary = "No unknown AI extensions discovered"
            result.action_type = "observe"
            result.action_risk = "R1"
            return

        names = [e["display_name"] for e in extensions]
        result.action_summary = (
            f"{len(extensions)} AI extension(s) discovered: {', '.join(names)}"
        )
        result.action_type = "observe"
        result.action_risk = "R1"
