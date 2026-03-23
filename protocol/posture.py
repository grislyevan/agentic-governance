"""Enforcement posture enum shared by server and agent.

The posture controls whether the agent enforces block decisions locally.
It is set by the admin via the API and pushed to agents over TCP or
included in heartbeat responses for HTTP-only agents.
"""

from __future__ import annotations

from enum import Enum


class EnforcementPosture(str, Enum):
    PASSIVE = "passive"   # detect + report only (no local enforcement)
    AUDIT = "audit"       # log what would be enforced, emit simulated events
    ACTIVE = "active"     # enforce block decisions autonomously
