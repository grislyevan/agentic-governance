"""MITRE ATT&CK technique mapping for Detec detection signals.

Maps behavioral patterns (BEH-*) and tool classifications to ATT&CK techniques.
Reference: MITRE ATT&CK v15 (2024), Enterprise matrix.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class AttackMapping:
    technique_id: str
    technique_name: str
    tactic: str
    subtechnique: str | None = None

    def to_dict(self) -> dict:
        d = {
            "technique_id": self.technique_id,
            "technique_name": self.technique_name,
            "tactic": self.tactic,
        }
        if self.subtechnique:
            d["subtechnique"] = self.subtechnique
        return d


# Behavioral pattern -> ATT&CK mappings
BEHAVIORAL_MAPPINGS: dict[str, list[AttackMapping]] = {
    "BEH-001": [  # Shell fan-out
        AttackMapping("T1059", "Command and Scripting Interpreter", "Execution"),
        AttackMapping("T1059", "Command and Scripting Interpreter", "Execution", "T1059.004"),
    ],
    "BEH-002": [  # LLM API cadence
        AttackMapping("T1071", "Application Layer Protocol", "Command and Control", "T1071.001"),
        AttackMapping("T1567", "Exfiltration Over Web Service", "Exfiltration"),
    ],
    "BEH-003": [  # Multi-file burst write
        AttackMapping("T1565", "Data Manipulation", "Impact", "T1565.001"),
        AttackMapping("T1074", "Data Staged", "Collection", "T1074.001"),
    ],
    "BEH-004": [  # Read-modify-write loop
        AttackMapping("T1005", "Data from Local System", "Collection"),
        AttackMapping("T1119", "Automated Collection", "Collection"),
    ],
    "BEH-005": [  # Autonomous session duration
        AttackMapping("T1078", "Valid Accounts", "Persistence"),
        AttackMapping("T1098", "Account Manipulation", "Persistence"),
    ],
    "BEH-006": [  # Config/credential access
        AttackMapping("T1552", "Unsecured Credentials", "Credential Access"),
        AttackMapping("T1555", "Credentials from Password Stores", "Credential Access"),
    ],
    "BEH-007": [  # Git automation
        AttackMapping("T1537", "Transfer Data to Cloud Account", "Exfiltration"),
        AttackMapping("T1567", "Exfiltration Over Web Service", "Exfiltration", "T1567.001"),
    ],
    "BEH-008": [  # Process resurrection
        AttackMapping("T1543", "Create or Modify System Process", "Persistence"),
        AttackMapping("T1547", "Boot or Logon Autostart Execution", "Persistence"),
    ],
    "BEH-009": [  # Agent execution chain
        AttackMapping("T1059", "Command and Scripting Interpreter", "Execution"),
        AttackMapping("T1071", "Application Layer Protocol", "Command and Control", "T1071.001"),
        AttackMapping("T1119", "Automated Collection", "Collection"),
    ],
}

# Tool class -> ATT&CK mappings
TOOL_CLASS_MAPPINGS: dict[str, list[AttackMapping]] = {
    "A": [  # Passive aide
        AttackMapping("T1059", "Command and Scripting Interpreter", "Execution"),
    ],
    "B": [  # Interactive agent
        AttackMapping("T1059", "Command and Scripting Interpreter", "Execution"),
        AttackMapping("T1071", "Application Layer Protocol", "Command and Control", "T1071.001"),
    ],
    "C": [  # Autonomous executor
        AttackMapping("T1059", "Command and Scripting Interpreter", "Execution"),
        AttackMapping("T1071", "Application Layer Protocol", "Command and Control", "T1071.001"),
        AttackMapping("T1204", "User Execution", "Execution", "T1204.002"),
    ],
    "D": [  # Infrastructure agent
        AttackMapping("T1059", "Command and Scripting Interpreter", "Execution"),
        AttackMapping("T1071", "Application Layer Protocol", "Command and Control", "T1071.001"),
        AttackMapping("T1204", "User Execution", "Execution", "T1204.002"),
        AttackMapping("T1543", "Create or Modify System Process", "Persistence"),
    ],
}


def map_behavioral_patterns(pattern_ids: list[str]) -> list[dict]:
    """Map a list of behavioral pattern IDs to ATT&CK techniques.

    Returns deduplicated list of technique dicts.
    """
    seen = set()
    results = []
    for pid in pattern_ids:
        for mapping in BEHAVIORAL_MAPPINGS.get(pid, []):
            key = (mapping.technique_id, mapping.subtechnique)
            if key not in seen:
                seen.add(key)
                results.append(mapping.to_dict())
    return results


def map_tool_class(tool_class: str) -> list[dict]:
    """Map a tool class (A/B/C/D) to ATT&CK techniques."""
    return [m.to_dict() for m in TOOL_CLASS_MAPPINGS.get(tool_class, [])]


def map_scan_result(scan_result) -> list[dict]:
    """Map a ScanResult to ATT&CK techniques based on behavioral patterns and tool class.

    Combines behavioral pattern matches (if any) with tool class mappings.
    Returns deduplicated technique list.
    """
    seen = set()
    results = []

    # Extract behavioral pattern IDs from evidence_details
    evidence = getattr(scan_result, "evidence_details", {}) or {}
    patterns = evidence.get("behavioral_patterns", [])
    pattern_ids = [p.get("pattern_id", "") for p in patterns if isinstance(p, dict)]

    for pid in pattern_ids:
        for mapping in BEHAVIORAL_MAPPINGS.get(pid, []):
            key = (mapping.technique_id, mapping.subtechnique)
            if key not in seen:
                seen.add(key)
                results.append(mapping.to_dict())

    # Add tool class mappings
    tool_class = getattr(scan_result, "tool_class", None) or ""
    for mapping in TOOL_CLASS_MAPPINGS.get(tool_class, []):
        key = (mapping.technique_id, mapping.subtechnique)
        if key not in seen:
            seen.add(key)
            results.append(mapping.to_dict())

    return results
