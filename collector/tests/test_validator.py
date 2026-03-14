"""Tests for collector/schema/validator.py: EventValidator and canonical schema."""

import json
import unittest
from pathlib import Path

from schema.validator import EventValidator


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent.parent


def _load_example_events() -> list[dict]:
    path = _repo_root() / "schemas" / "example-events.json"
    with open(path) as f:
        return json.load(f)


class TestEventValidator(unittest.TestCase):
    """Test that valid events pass and invalid payloads fail with expected errors."""

    @classmethod
    def setUpClass(cls) -> None:
        schema_path = _repo_root() / "schemas" / "canonical-event-schema.json"
        cls.validator = EventValidator(schema_path=schema_path)

    def test_valid_example_events_pass(self) -> None:
        """Events from schemas/example-events.json must pass validation."""
        events = _load_example_events()
        for i, event in enumerate(events):
            with self.subTest(event_id=event.get("event_id"), index=i):
                errors = self.validator.validate(event)
                self.assertEqual(errors, [], f"Event {event.get('event_id')} had errors: {errors}")
                self.assertTrue(self.validator.is_valid(event))

    def test_missing_required_field_fails(self) -> None:
        """Omitting required top-level fields must produce validation errors."""
        valid = _load_example_events()[0]
        # Remove required "event_id"
        invalid = {k: v for k, v in valid.items() if k != "event_id"}
        errors = self.validator.validate(invalid)
        self.assertGreater(len(errors), 0)
        self.assertFalse(self.validator.is_valid(invalid))
        self.assertTrue(any("event_id" in e or "required" in e.lower() for e in errors))

    def test_invalid_event_type_fails(self) -> None:
        """event_type not in enum must fail."""
        valid = _load_example_events()[0]
        invalid = {**valid, "event_type": "invalid.type"}
        errors = self.validator.validate(invalid)
        self.assertGreater(len(errors), 0)
        self.assertFalse(self.validator.is_valid(invalid))

    def test_invalid_actor_trust_tier_fails(self) -> None:
        """actor.trust_tier must be T0/T1/T2/T3."""
        valid = _load_example_events()[0]
        invalid = json.loads(json.dumps(valid))
        invalid["actor"]["trust_tier"] = "T99"
        errors = self.validator.validate(invalid)
        self.assertGreater(len(errors), 0)
        self.assertFalse(self.validator.is_valid(invalid))

    def test_detection_observed_requires_tool_action_target(self) -> None:
        """Per schema allOf, detection.observed requires tool, action, target."""
        valid = _load_example_events()[0]
        self.assertEqual(valid["event_type"], "detection.observed")
        # Remove tool
        invalid = {k: v for k, v in valid.items() if k != "tool"}
        errors = self.validator.validate(invalid)
        self.assertGreater(len(errors), 0)
        self.assertFalse(self.validator.is_valid(invalid))

    def test_empty_object_fails(self) -> None:
        """Empty object must fail (many required fields missing)."""
        errors = self.validator.validate({})
        self.assertGreater(len(errors), 0)
        self.assertFalse(self.validator.is_valid({}))

    def test_scan_cleanliness_baseline_action_type_fails(self) -> None:
        """action.type 'approval_required' (from e.g. Claude Cowork) fails schema enum."""
        valid = _load_example_events()[0]
        invalid = json.loads(json.dumps(valid))
        invalid["action"]["type"] = "approval_required"
        errors = self.validator.validate(invalid)
        self.assertGreater(len(errors), 0, "action.type approval_required must fail until schema or payload fixed")
        self.assertTrue(any("action" in e and "approval_required" in e for e in errors) or any("action" in e for e in errors))

    def test_scan_cleanliness_enforcement_result_simulated_passes(self) -> None:
        """outcome.enforcement_result 'simulated' (audit posture) is allowed by schema."""
        events = _load_example_events()
        applied = next((e for e in events if e.get("event_type") == "enforcement.applied"), None)
        if not applied:
            self.skipTest("example-events.json has no enforcement.applied event")
        event = json.loads(json.dumps(applied))
        event["outcome"]["enforcement_result"] = "simulated"
        errors = self.validator.validate(event)
        self.assertEqual(errors, [], f"enforcement_result 'simulated' must pass: {errors}")
        self.assertTrue(self.validator.is_valid(event))

    def test_scan_cleanliness_correlation_context_passes(self) -> None:
        """Root-level correlation_context is allowed when schema defines it."""
        valid = _load_example_events()[0]
        event = json.loads(json.dumps(valid))
        event["correlation_context"] = {"multi_agent": True, "related_tool_names": ["Tool A", "Tool B"]}
        errors = self.validator.validate(event)
        self.assertEqual(errors, [], f"correlation_context must pass: {errors}")
        self.assertTrue(self.validator.is_valid(event))

    def test_scan_cleanliness_tool_class_x_fails(self) -> None:
        """tool.class 'X' (e.g. EvasionScanner) fails schema enum; collector normalizes to A."""
        valid = _load_example_events()[0]
        invalid = json.loads(json.dumps(valid))
        invalid["tool"]["class"] = "X"
        errors = self.validator.validate(invalid)
        self.assertGreater(len(errors), 0, "tool.class 'X' must fail schema enum")
        self.assertTrue(any("tool" in e and "X" in e for e in errors) or any("tool" in e for e in errors))


if __name__ == "__main__":
    unittest.main()
