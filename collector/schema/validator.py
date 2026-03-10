"""Validates emitted events against the canonical JSON Schema."""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path
from typing import Any

import jsonschema
from jsonschema import Draft202012Validator, ValidationError

logger = logging.getLogger(__name__)

_BUNDLE_DIR = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent.parent))
SCHEMA_PATH = _BUNDLE_DIR / "schemas" / "canonical-event-schema.json"


class EventValidator:
    """Loads and validates events against the canonical event schema."""

    def __init__(self, schema_path: Path | None = None) -> None:
        path = schema_path or SCHEMA_PATH
        with open(path) as f:
            self._schema = json.load(f)
        Draft202012Validator.check_schema(self._schema)
        self._validator = Draft202012Validator(self._schema)

    def validate(self, event: dict[str, Any]) -> list[str]:
        """Validate an event dict. Returns list of error messages (empty = valid)."""
        errors: list[str] = []
        for error in self._validator.iter_errors(event):
            msg = f"{error.json_path}: {error.message}"
            errors.append(msg)
            logger.error("Schema validation failure: %s", msg)
        return errors

    def is_valid(self, event: dict[str, Any]) -> bool:
        """Quick check — returns True if event conforms to schema."""
        return self._validator.is_valid(event)
