"""Confidence scoring engine implementing Playbook Appendix B formula."""

from __future__ import annotations

from scanner.base import LayerSignals, ScanResult

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
    "network": 0.20,
    "identity": 0.10,
    "behavior": 0.20,
}

CURSOR_WEIGHTS: dict[str, float] = {
    "process": 0.30,
    "file": 0.20,
    "network": 0.20,
    "identity": 0.10,
    "behavior": 0.20,
}

COPILOT_WEIGHTS: dict[str, float] = {
    "process": 0.25,
    "file": 0.25,
    "network": 0.15,
    "identity": 0.15,
    "behavior": 0.20,
}

OPEN_INTERPRETER_WEIGHTS: dict[str, float] = {
    "process": 0.25,
    "file": 0.15,
    "network": 0.15,
    "identity": 0.10,
    "behavior": 0.35,
}

OPENCLAW_WEIGHTS: dict[str, float] = {
    "process": 0.25,
    "file": 0.30,
    "network": 0.15,
    "identity": 0.15,
    "behavior": 0.15,
}

# Continue: config file is the primary attribution mechanism (backend routing)
CONTINUE_WEIGHTS: dict[str, float] = {
    "process": 0.20,
    "file": 0.35,
    "network": 0.15,
    "identity": 0.10,
    "behavior": 0.20,
}

# LM Studio: similar to Ollama (local model runtime)
LM_STUDIO_WEIGHTS: dict[str, float] = {
    "process": 0.25,
    "file": 0.30,
    "network": 0.20,
    "identity": 0.10,
    "behavior": 0.15,
}

# Aider: named binary + repo artifacts are primary signals
AIDER_WEIGHTS: dict[str, float] = {
    "process": 0.30,
    "file": 0.25,
    "network": 0.15,
    "identity": 0.15,
    "behavior": 0.15,
}

# GPT-Pilot: behavior (mass generation) is the primary differentiator
GPT_PILOT_WEIGHTS: dict[str, float] = {
    "process": 0.25,
    "file": 0.20,
    "network": 0.15,
    "identity": 0.10,
    "behavior": 0.30,
}

# Cline: extension manifest + task history are primary anchors
CLINE_WEIGHTS: dict[str, float] = {
    "process": 0.20,
    "file": 0.35,
    "network": 0.15,
    "identity": 0.10,
    "behavior": 0.20,
}

TOOL_WEIGHTS: dict[str, dict[str, float]] = {
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
}


def get_weights(tool_name: str | None) -> dict[str, float]:
    """Return per-tool calibrated weights, falling back to defaults."""
    if tool_name and tool_name in TOOL_WEIGHTS:
        return TOOL_WEIGHTS[tool_name]
    return DEFAULT_WEIGHTS


def compute_confidence(scan: ScanResult) -> float:
    """Compute final confidence score per Appendix B formula.

    base_score = sum(layer_weight * layer_signal_strength)
    penalties  = sum(applicable penalty values)
    evasion_boost = sum(evasion boosts from scanner)
    final = max(0, base_score - penalties + evasion_boost)
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
    return round(final, 4)


def classify_confidence(score: float) -> str:
    """Classify confidence score into Low/Medium/High per Playbook Section 6.2."""
    if score >= 0.75:
        return "High"
    if score >= 0.45:
        return "Medium"
    return "Low"
