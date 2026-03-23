"""Preflight checks for protocol/tests.

Runs before test collection to produce a single, actionable error when a
required plugin is absent rather than a wall of confusing async failures.
"""

from __future__ import annotations

import importlib.util

import pytest


def pytest_configure(config: pytest.Config) -> None:  # noqa: ARG001
    """Abort early with a clear remediation message if pytest-asyncio is missing."""
    if importlib.util.find_spec("pytest_asyncio") is None:
        pytest.exit(
            "\n"
            "pytest-asyncio is required for protocol tests but is not installed.\n"
            "Install it with:  pip install -e \".[dev]\"\n"
            "See docs/local-test-profiles.md for local profile setup.\n",
            returncode=3,
        )
