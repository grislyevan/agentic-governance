"""Tests for compute_status() on the Endpoint model, including tamper_suspected logic."""

from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone as tz
from unittest.mock import MagicMock

from models.endpoint import (
    ENDPOINT_STATUS_ACTIVE,
    ENDPOINT_STATUS_STALE,
    ENDPOINT_STATUS_TAMPER_SUSPECTED,
    ENDPOINT_STATUS_UNGOVERNED,
    Endpoint,
)


def _make_endpoint(
    *,
    elapsed_seconds: float,
    heartbeat_interval: int,
    management_state: str = "unmanaged",
    status: str = "active",
) -> MagicMock:
    """Return a MagicMock that mimics an Endpoint with compute_status() bound."""
    ep = MagicMock(spec=Endpoint)
    ep.status = status
    ep.heartbeat_interval = heartbeat_interval
    ep.management_state = management_state
    ep.last_seen_at = datetime.now(tz.utc) - timedelta(seconds=elapsed_seconds)

    # Bind the real unbound method so the mock behaves like an actual instance.
    ep.compute_status = lambda: Endpoint.compute_status(ep)
    return ep


class TestComputeStatus(unittest.TestCase):
    def test_active_endpoint(self):
        """100s elapsed, 300s interval → active (threshold = 450s)."""
        ep = _make_endpoint(elapsed_seconds=100, heartbeat_interval=300)
        self.assertEqual(ep.compute_status(), ENDPOINT_STATUS_ACTIVE)

    def test_stale_endpoint(self):
        """600s elapsed, 300s interval → stale (threshold = 450s, stale ceiling = 1350s)."""
        ep = _make_endpoint(elapsed_seconds=600, heartbeat_interval=300)
        self.assertEqual(ep.compute_status(), ENDPOINT_STATUS_STALE)

    def test_tamper_suspected_endpoint(self):
        """1500s elapsed, 300s interval, managed → tamper_suspected (elapsed > 1350s)."""
        ep = _make_endpoint(
            elapsed_seconds=1500,
            heartbeat_interval=300,
            management_state="managed",
        )
        self.assertEqual(ep.compute_status(), ENDPOINT_STATUS_TAMPER_SUSPECTED)

    def test_unmanaged_endpoint_not_tamper_suspected(self):
        """1500s elapsed, 300s interval, unmanaged → ungoverned, NOT tamper_suspected."""
        ep = _make_endpoint(
            elapsed_seconds=1500,
            heartbeat_interval=300,
            management_state="unmanaged",
        )
        result = ep.compute_status()
        self.assertNotEqual(result, ENDPOINT_STATUS_TAMPER_SUSPECTED)
        self.assertEqual(result, ENDPOINT_STATUS_UNGOVERNED)


if __name__ == "__main__":
    unittest.main()
