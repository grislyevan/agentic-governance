"""Telemetry providers for agent-side event collection."""

from __future__ import annotations

from .registry import get_best_provider

__all__ = ["get_best_provider"]
