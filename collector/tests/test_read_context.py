"""Tests for sensitive read context classification."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest import TestCase

from analysis.read_context import ReadContext, classify_read_context


class _E:
    def __init__(self, path: str, ts: float | None = None) -> None:
        self.path = path
        self.timestamp = datetime.fromtimestamp(ts or 0, tz=timezone.utc)


class TestClassifyReadContext(TestCase):
    def test_empty_returns_isolated(self) -> None:
        ctx = classify_read_context([])
        self.assertEqual(ctx.read_pattern, "isolated_read")
        self.assertEqual(ctx.read_count, 0)

    def test_single_event_isolated(self) -> None:
        ctx = classify_read_context([_E("/home/.ssh/id_rsa", 100)])
        self.assertEqual(ctx.read_pattern, "isolated_read")

    def test_two_same_path_isolated(self) -> None:
        ctx = classify_read_context([
            _E("/.env", 100),
            _E("/.env", 101),
        ])
        self.assertEqual(ctx.read_pattern, "isolated_read")

    def test_few_paths_short_burst_targeted(self) -> None:
        events = [_E(f"/.aws/f{i}", 100 + i) for i in range(5)]
        ctx = classify_read_context(events)
        self.assertEqual(ctx.read_pattern, "targeted_read")
        self.assertEqual(ctx.unique_paths, 5)
        self.assertEqual(ctx.read_count, 5)

    def test_many_unique_paths_broad_scan(self) -> None:
        events = [_E(f"/tmp/f{i}", 100 + i * 0.1) for i in range(15)]
        ctx = classify_read_context(events)
        self.assertEqual(ctx.read_pattern, "broad_scan")

    def test_high_count_long_burst_background_index(self) -> None:
        events = [_E(f"/src/f{i}", 100 + i * 0.5) for i in range(25)]
        ctx = classify_read_context(events)
        self.assertEqual(ctx.read_pattern, "background_index")
