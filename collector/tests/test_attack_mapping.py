"""Unit tests for MITRE ATT&CK technique mapping."""

from __future__ import annotations

import unittest

from engine.attack_mapping import (
    BEHAVIORAL_MAPPINGS,
    TOOL_CLASS_MAPPINGS,
    map_behavioral_patterns,
    map_scan_result,
    map_tool_class,
)
from scanner.base import ScanResult


class TestMapBehavioralPatterns(unittest.TestCase):
    """Test mapping behavioral pattern IDs to ATT&CK techniques."""

    def test_beh_001_maps_to_t1059(self):
        result = map_behavioral_patterns(["BEH-001"])
        ids = [t["technique_id"] for t in result]
        self.assertIn("T1059", ids)
        self.assertTrue(any(t.get("subtechnique") == "T1059.004" for t in result))

    def test_beh_002_maps_to_t1071_and_t1567(self):
        result = map_behavioral_patterns(["BEH-002"])
        ids = [t["technique_id"] for t in result]
        self.assertIn("T1071", ids)
        self.assertIn("T1567", ids)

    def test_beh_006_maps_to_credential_access(self):
        result = map_behavioral_patterns(["BEH-006"])
        tactics = [t["tactic"] for t in result]
        self.assertIn("Credential Access", tactics)
        ids = [t["technique_id"] for t in result]
        self.assertIn("T1552", ids)
        self.assertIn("T1555", ids)

    def test_beh_008_maps_to_persistence(self):
        result = map_behavioral_patterns(["BEH-008"])
        ids = [t["technique_id"] for t in result]
        self.assertIn("T1543", ids)
        self.assertIn("T1547", ids)

    def test_empty_patterns_returns_empty_list(self):
        result = map_behavioral_patterns([])
        self.assertEqual(result, [])

    def test_unknown_pattern_returns_empty(self):
        result = map_behavioral_patterns(["BEH-999"])
        self.assertEqual(result, [])

    def test_deduplication_overlapping_mappings(self):
        result = map_behavioral_patterns(["BEH-001", "BEH-002"])
        seen = set()
        for t in result:
            key = (t["technique_id"], t.get("subtechnique"))
            self.assertNotIn(key, seen)
            seen.add(key)


class TestMapToolClass(unittest.TestCase):
    """Test mapping tool class to ATT&CK techniques."""

    def test_class_a_maps_to_t1059(self):
        result = map_tool_class("A")
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["technique_id"], "T1059")

    def test_class_b_maps_to_execution_and_c2(self):
        result = map_tool_class("B")
        ids = [t["technique_id"] for t in result]
        self.assertIn("T1059", ids)
        self.assertIn("T1071", ids)

    def test_class_c_maps_to_user_execution(self):
        result = map_tool_class("C")
        ids = [t["technique_id"] for t in result]
        self.assertIn("T1204", ids)
        self.assertTrue(any(t.get("subtechnique") == "T1204.002" for t in result))

    def test_class_d_includes_persistence(self):
        result = map_tool_class("D")
        ids = [t["technique_id"] for t in result]
        self.assertIn("T1543", ids)

    def test_unknown_class_returns_empty_list(self):
        result = map_tool_class("X")
        self.assertEqual(result, [])

    def test_empty_class_returns_empty_list(self):
        result = map_tool_class("")
        self.assertEqual(result, [])


class TestMapScanResult(unittest.TestCase):
    """Test map_scan_result with mock ScanResult."""

    def test_behavioral_patterns_extracted(self):
        scan = ScanResult(
            detected=True,
            tool_name="Unknown Agent",
            tool_class="C",
            evidence_details={
                "behavioral_patterns": [
                    {"pattern_id": "BEH-001", "pattern_name": "Shell fan-out", "score": 0.9},
                    {"pattern_id": "BEH-002", "pattern_name": "LLM API cadence", "score": 0.8},
                ],
            },
        )
        result = map_scan_result(scan)
        ids = [t["technique_id"] for t in result]
        self.assertIn("T1059", ids)
        self.assertIn("T1071", ids)
        self.assertIn("T1567", ids)
        self.assertIn("T1204", ids)

    def test_tool_class_mapping_when_no_behavioral(self):
        scan = ScanResult(
            detected=True,
            tool_name="Claude Code",
            tool_class="C",
            evidence_details={},
        )
        result = map_scan_result(scan)
        self.assertGreater(len(result), 0)
        ids = [t["technique_id"] for t in result]
        self.assertIn("T1059", ids)

    def test_deduplication_behavioral_and_tool_class(self):
        scan = ScanResult(
            detected=True,
            tool_name="Unknown Agent",
            tool_class="B",
            evidence_details={
                "behavioral_patterns": [
                    {"pattern_id": "BEH-001", "pattern_name": "Shell fan-out", "score": 0.9},
                ],
            },
        )
        result = map_scan_result(scan)
        seen = set()
        for t in result:
            key = (t["technique_id"], t.get("subtechnique"))
            self.assertNotIn(key, seen)
            seen.add(key)

    def test_empty_scan_returns_empty_list(self):
        scan = ScanResult(
            detected=False,
            tool_name=None,
            tool_class=None,
            evidence_details={},
        )
        result = map_scan_result(scan)
        self.assertEqual(result, [])

    def test_scan_without_evidence_details(self):
        scan = ScanResult(
            detected=True,
            tool_name="Cursor",
            tool_class="C",
        )
        result = map_scan_result(scan)
        self.assertGreater(len(result), 0)
        ids = [t["technique_id"] for t in result]
        self.assertIn("T1059", ids)

    def test_technique_dict_structure(self):
        scan = ScanResult(
            detected=True,
            tool_name="Ollama",
            tool_class="B",
        )
        result = map_scan_result(scan)
        for t in result:
            self.assertIn("technique_id", t)
            self.assertIn("technique_name", t)
            self.assertIn("tactic", t)
            self.assertIsInstance(t["technique_id"], str)
            self.assertIsInstance(t["technique_name"], str)
            self.assertIsInstance(t["tactic"], str)


class TestMappingConstants(unittest.TestCase):
    """Test that mapping constants are well-formed."""

    def test_all_beh_patterns_have_mappings(self):
        expected = ["BEH-001", "BEH-002", "BEH-003", "BEH-004", "BEH-005", "BEH-006", "BEH-007", "BEH-008"]
        for pid in expected:
            self.assertIn(pid, BEHAVIORAL_MAPPINGS)
            mappings = BEHAVIORAL_MAPPINGS[pid]
            self.assertGreater(len(mappings), 0)
            for m in mappings:
                self.assertTrue(m.technique_id.startswith("T"))
                self.assertGreater(len(m.technique_name), 0)
                self.assertGreater(len(m.tactic), 0)

    def test_all_tool_classes_have_mappings(self):
        for tc in ["A", "B", "C", "D"]:
            self.assertIn(tc, TOOL_CLASS_MAPPINGS)
            mappings = TOOL_CLASS_MAPPINGS[tc]
            self.assertGreater(len(mappings), 0)
