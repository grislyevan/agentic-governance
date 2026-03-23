"""Tests for strongest subchain extraction."""

from __future__ import annotations

import pytest

from core.subchain_extractor import (
    extract_strongest_subchain,
    format_subchain_chain,
)


def test_empty_timeline_returns_empty() -> None:
    assert extract_strongest_subchain([]) == []
    assert extract_strongest_subchain([{"type": "sequence_start"}]) == []


def test_single_type_returns_empty() -> None:
    assert extract_strongest_subchain([{"type": "llm"}]) == []


def test_two_types_returns_both_when_weighted() -> None:
    out = extract_strongest_subchain([{"type": "llm"}, {"type": "shell_exec"}])
    assert out == ["llm", "shell_exec"]


def test_noisy_timeline_extracts_best_segment() -> None:
    timeline = [
        {"type": "file_write"},
        {"type": "llm"},
        {"type": "shell_exec"},
        {"type": "file_write"},
        {"type": "git"},
        {"type": "network"},
        {"type": "file_write"},
    ]
    out = extract_strongest_subchain(timeline)
    assert "llm" in out
    assert "shell_exec" in out
    assert "git" in out or "file_write" in out


def test_format_subchain_chain() -> None:
    assert format_subchain_chain([]) == ""
    assert format_subchain_chain(["llm", "shell_exec", "git"]) == "llm -> shell_exec -> git"


def test_skips_sequence_boundaries() -> None:
    timeline = [
        {"type": "sequence_start"},
        {"type": "llm"},
        {"type": "shell_exec"},
        {"type": "sequence_end"},
    ]
    out = extract_strongest_subchain(timeline)
    assert out == ["llm", "shell_exec"]
