"""Confidence scoring engine implementing Playbook Appendix B formula."""

from __future__ import annotations

from scanner.base import LayerSignals, ScanResult

# 5-layer confidence model aligned with Playbook Appendix B "Layer Weight
# Defaults".  Tool-specific weights below may diverge from these defaults
# based on lab-run calibration (see per-tool comments).

DEFAULT_WEIGHTS: dict[str, float] = {
    "process": 0.30,
    "file": 0.20,
    "network": 0.15,
    "identity": 0.15,
    "behavior": 0.20,
}

OLLAMA_WEIGHTS: dict[str, float] = {
    "process": 0.25,
    "file": 0.25,
    "network": 0.25,
    "identity": 0.05,
    "behavior": 0.20,
}

CURSOR_WEIGHTS: dict[str, float] = {
    "process": 0.30,
    "file": 0.20,
    "network": 0.15,
    "identity": 0.15,
    "behavior": 0.20,
}

COPILOT_WEIGHTS: dict[str, float] = {
    "process": 0.25,
    "file": 0.25,
    "network": 0.20,
    "identity": 0.10,
    "behavior": 0.20,
}

OPEN_INTERPRETER_WEIGHTS: dict[str, float] = {
    "process": 0.25,
    "file": 0.15,
    "network": 0.10,
    "identity": 0.10,
    "behavior": 0.40,
}

OPENCLAW_WEIGHTS: dict[str, float] = {
    "process": 0.25,
    "file": 0.35,
    "network": 0.15,
    "identity": 0.10,
    "behavior": 0.15,
}

CONTINUE_WEIGHTS: dict[str, float] = {
    "process": 0.20,
    "file": 0.35,
    "network": 0.15,
    "identity": 0.10,
    "behavior": 0.20,
}

LM_STUDIO_WEIGHTS: dict[str, float] = {
    "process": 0.25,
    "file": 0.35,
    "network": 0.20,
    "identity": 0.05,
    "behavior": 0.15,
}

AIDER_WEIGHTS: dict[str, float] = {
    "process": 0.35,
    "file": 0.25,
    "network": 0.15,
    "identity": 0.10,
    "behavior": 0.15,
}

GPT_PILOT_WEIGHTS: dict[str, float] = {
    "process": 0.25,
    "file": 0.20,
    "network": 0.10,
    "identity": 0.10,
    "behavior": 0.35,
}

CLINE_WEIGHTS: dict[str, float] = {
    "process": 0.20,
    "file": 0.35,
    "network": 0.15,
    "identity": 0.10,
    "behavior": 0.20,
}

CLAUDE_COWORK_WEIGHTS: dict[str, float] = {
    "process": 0.30,
    "file": 0.25,
    "network": 0.15,
    "identity": 0.15,
    "behavior": 0.15,
}

# LAB-RUN-001/002: process and file are primary; network weak without EDR.
# Confidence typically Medium (0.68–0.74) until artifact/behavior signals improve.
CLAUDE_CODE_WEIGHTS: dict[str, float] = {
    "process": 0.32,
    "file": 0.23,
    "network": 0.12,
    "identity": 0.18,
    "behavior": 0.15,
}

# Behavior layer is dominant for pattern-based detection of unknown agents.
# Process and network are secondary; identity is deprioritized since unknown
# agents rarely have attributable identity signals.
BEHAVIORAL_WEIGHTS: dict[str, float] = {
    "process": 0.20,
    "file": 0.15,
    "network": 0.20,
    "identity": 0.10,
    "behavior": 0.35,
}

TOOL_WEIGHTS: dict[str, dict[str, float]] = {
    "Claude Code": CLAUDE_CODE_WEIGHTS,
    "Ollama": OLLAMA_WEIGHTS,
    "Cursor": CURSOR_WEIGHTS,
    "GitHub Copilot": COPILOT_WEIGHTS,
    "Open Interpreter": OPEN_INTERPRETER_WEIGHTS,
    "OpenClaw": OPENCLAW_WEIGHTS,
    "Continue": CONTINUE_WEIGHTS,
    "LM Studio": LM_STUDIO_WEIGHTS,
    "Aider": AIDER_WEIGHTS,
    "GPT-Pilot": GPT_PILOT_WEIGHTS,
    "Cline": CLINE_WEIGHTS,
    "Claude Cowork": CLAUDE_COWORK_WEIGHTS,
    "Unknown Agent": BEHAVIORAL_WEIGHTS,
}


def get_weights(tool_name: str | None) -> dict[str, float]:
    """Return per-tool calibrated weights, falling back to defaults."""
    if tool_name and tool_name in TOOL_WEIGHTS:
        return TOOL_WEIGHTS[tool_name]
    return DEFAULT_WEIGHTS


# Tools with strong infrastructure signals (daemon + rich file footprint) that
# should not be underscored when the model is temporarily incapable.  The floor
# is applied when both process and file signals exceed the thresholds below.
# Rationale: LAB-RUN-013 showed that a small model dropped OpenClaw from 0.80
# to 0.725 entirely due to the behavior layer, while infrastructure was unchanged.
INFRASTRUCTURE_FLOOR_TOOLS: frozenset[str] = frozenset({"OpenClaw"})
INFRASTRUCTURE_FLOOR_THRESHOLD = 0.80
INFRASTRUCTURE_FLOOR_VALUE = 0.70


def compute_confidence(scan: ScanResult) -> float:
    """Compute final confidence score per Appendix B formula.

    base_score = sum(layer_weight * layer_signal_strength)
    penalties  = sum(applicable penalty values)
    evasion_boost = sum(evasion boosts from scanner)
    final = max(0, base_score - penalties + evasion_boost)

    An infrastructure floor prevents underscoring Class D tools whose process
    and file signals are both strong (LAB-RUN-013 finding).
    """
    weights = get_weights(scan.tool_name)
    signals = scan.signals

    base_score = (
        weights["process"] * signals.process
        + weights["file"] * signals.file
        + weights["network"] * signals.network
        + weights["identity"] * signals.identity
        + weights["behavior"] * signals.behavior
    )

    penalty_total = sum(val for _, val in scan.penalties)
    evasion_boost = scan.evasion_boost

    final = max(0.0, min(1.0, base_score - penalty_total + evasion_boost))

    if (
        scan.tool_name in INFRASTRUCTURE_FLOOR_TOOLS
        and signals.process >= INFRASTRUCTURE_FLOOR_THRESHOLD
        and signals.file >= INFRASTRUCTURE_FLOOR_THRESHOLD
    ):
        final = max(final, INFRASTRUCTURE_FLOOR_VALUE)

    return round(final, 4)


def classify_confidence(score: float) -> str:
    """Classify confidence score into Low/Medium/High per Playbook Section 6.2."""
    if score >= 0.75:
        return "High"
    if score >= 0.45:
        return "Medium"
    return "Low"
