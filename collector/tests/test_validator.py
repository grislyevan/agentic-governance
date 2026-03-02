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


if __name__ == "__main__":
    unittest.main()
