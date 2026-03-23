"""Tests for collector/output/emitter.py: EventEmitter NDJSON output and schema conformance."""

import json
import tempfile
import unittest
from pathlib import Path

from output.emitter import EventEmitter
from schema.validator import EventValidator


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent.parent


def _load_one_example_event() -> dict:
    path = _repo_root() / "schemas" / "example-events.json"
    with open(path) as f:
        events = json.load(f)
    return events[0]


class TestEventEmitter(unittest.TestCase):
    """Test that emitted NDJSON lines parse as JSON and conform to schema."""

    def setUp(self) -> None:
        self.schema_path = _repo_root() / "schemas" / "canonical-event-schema.json"
        self.validator = EventValidator(schema_path=self.schema_path)

    def test_emit_valid_event_writes_ndjson_line(self) -> None:
        """Emitting a valid event appends one NDJSON line to the file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".ndjson", delete=False) as f:
            path = f.name
        try:
            emitter = EventEmitter(output_path=path, validator=self.validator)
            event = _load_one_example_event()
            ok = emitter.emit(event)
            self.assertTrue(ok)
            self.assertEqual(emitter.stats["emitted"], 1)
            self.assertEqual(emitter.stats["failed"], 0)
            with open(path) as f:
                lines = f.readlines()
            self.assertEqual(len(lines), 1)
            parsed = json.loads(lines[0])
            self.assertEqual(parsed["event_id"], event["event_id"])
            self.assertEqual(parsed["event_type"], event["event_type"])
        finally:
            Path(path).unlink(missing_ok=True)

    def test_emitted_line_is_valid_json(self) -> None:
        """Each emitted line must parse as JSON."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".ndjson", delete=False) as f:
            path = f.name
        try:
            emitter = EventEmitter(output_path=path, validator=self.validator)
            event = _load_one_example_event()
            emitter.emit(event)
            with open(path) as f:
                line = f.read()
            obj = json.loads(line)
            self.assertIsInstance(obj, dict)
            self.assertIn("event_id", obj)
        finally:
            Path(path).unlink(missing_ok=True)

    def test_emitted_event_conforms_to_schema(self) -> None:
        """Emitted content must validate against the canonical schema."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".ndjson", delete=False) as f:
            path = f.name
        try:
            emitter = EventEmitter(output_path=path, validator=self.validator)
            event = _load_one_example_event()
            emitter.emit(event)
            with open(path) as f:
                parsed = json.loads(f.read())
            errors = self.validator.validate(parsed)
            self.assertEqual(errors, [], f"Emitted event failed schema: {errors}")
        finally:
            Path(path).unlink(missing_ok=True)

    def test_invalid_event_fails_validation_and_not_written(self) -> None:
        """Invalid event must not be written; failed count incremented."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".ndjson", delete=False) as f:
            path = f.name
        try:
            emitter = EventEmitter(output_path=path, validator=self.validator)
            event = _load_one_example_event()
            del event["event_id"]
            ok = emitter.emit(event)
            self.assertFalse(ok)
            self.assertEqual(emitter.stats["emitted"], 0)
            self.assertEqual(emitter.stats["failed"], 1)
            with open(path) as f:
                self.assertEqual(f.read(), "")
        finally:
            Path(path).unlink(missing_ok=True)

    def test_multiple_emits_produce_multiple_lines(self) -> None:
        """Multiple valid emits produce one NDJSON line each."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".ndjson", delete=False) as f:
            path = f.name
        try:
            emitter = EventEmitter(output_path=path, validator=self.validator)
            path_examples = _repo_root() / "schemas" / "example-events.json"
            with open(path_examples) as f:
                two = json.load(f)[:2]
            for evt in two:
                emitter.emit(evt)
            self.assertEqual(emitter.stats["emitted"], 2)
            with open(path) as f:
                lines = f.readlines()
            self.assertEqual(len(lines), 2)
            for line in lines:
                obj = json.loads(line)
                self.assertIn("event_id", obj)
        finally:
            Path(path).unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
