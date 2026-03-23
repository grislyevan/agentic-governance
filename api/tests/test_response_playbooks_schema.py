"""Tests for response playbook schema validation (F-006, F-014)."""

from __future__ import annotations

import pytest

from schemas.response_playbooks import (
    MAX_PAYLOAD_DEPTH,
    MAX_PAYLOAD_SIZE,
    PlaybookTestRequest,
    ResponsePlaybookCreate,
    ResponsePlaybookUpdate,
)


class TestPlaybookTestRequestLimits:
    """PlaybookTestRequest event_payload: max depth and size (F-006)."""

    def test_event_payload_empty_allowed(self) -> None:
        PlaybookTestRequest(event_payload={})

    def test_event_payload_shallow_allowed(self) -> None:
        PlaybookTestRequest(event_payload={"event_type": "detection.observed", "tool": {"name": "Cursor"}})

    def test_event_payload_exceeds_depth_rejected(self) -> None:
        # Build nested dict of depth MAX_PAYLOAD_DEPTH + 1
        deep = {"a": 1}
        for _ in range(MAX_PAYLOAD_DEPTH):
            deep = {"nested": deep}
        with pytest.raises(ValueError, match="exceeds max nesting depth"):
            PlaybookTestRequest(event_payload=deep)

    def test_event_payload_exceeds_size_rejected(self) -> None:
        large = {"key": "x" * (MAX_PAYLOAD_SIZE + 1)}
        with pytest.raises(ValueError, match="exceeds max size"):
            PlaybookTestRequest(event_payload=large)


class TestResponsePlaybookCreateDepth:
    """ResponsePlaybookCreate trigger/actions/escalation max depth (F-014)."""

    def test_trigger_within_depth_allowed(self) -> None:
        trigger = {"event_type": "detection.observed", "tool": {"class": "C"}}
        ResponsePlaybookCreate(name="Test", trigger=trigger, actions=[])

    def test_trigger_exceeds_depth_rejected(self) -> None:
        deep = {"a": 1}
        for _ in range(MAX_PAYLOAD_DEPTH):
            deep = {"nested": deep}
        with pytest.raises(ValueError, match="trigger exceeds max nesting depth"):
            ResponsePlaybookCreate(name="Test", trigger=deep, actions=[])

    def test_actions_item_exceeds_depth_rejected(self) -> None:
        deep = {"a": 1}
        for _ in range(MAX_PAYLOAD_DEPTH):
            deep = {"nested": deep}
        with pytest.raises(ValueError, match="actions\\[0\\] exceeds max nesting depth"):
            ResponsePlaybookCreate(name="Test", trigger={}, actions=[deep])


class TestResponsePlaybookUpdateDepth:
    """ResponsePlaybookUpdate trigger/actions/escalation max depth (F-014)."""

    def test_trigger_exceeds_depth_rejected(self) -> None:
        deep = {"a": 1}
        for _ in range(MAX_PAYLOAD_DEPTH):
            deep = {"nested": deep}
        with pytest.raises(ValueError, match="trigger exceeds max nesting depth"):
            ResponsePlaybookUpdate(trigger=deep)
