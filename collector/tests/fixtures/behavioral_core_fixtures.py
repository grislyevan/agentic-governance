"""Event-level fixtures for DETEC-BEH-CORE-01/02/03/04 replay tests.

Each helper returns an EventStore seeded with process/network/file events
for a specific scenario (positive, false_positive, ambiguous, renamed).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from telemetry.event_store import EventStore, FileChangeEvent, NetworkConnectEvent, ProcessExecEvent


def _base_time() -> datetime:
    """Use a time within retention so events are not evicted (e.g. 2 minutes ago)."""
    return datetime.now(timezone.utc) - timedelta(minutes=2)


def _store() -> EventStore:
    return EventStore(max_events=5000, retention_seconds=86400 * 365)


# ---------------------------------------------------------------------------
# DETEC-BEH-CORE-01: Autonomous Shell Fan-Out
# ---------------------------------------------------------------------------

def seed_shell_fanout_positive() -> EventStore:
    """Clean positive: 8 shells in 42s with LLM activity (BEH-001 + BEH-002)."""
    store = _store()
    base = _base_time()
    store.push_process(ProcessExecEvent(
        timestamp=base, pid=2000, ppid=1,
        name="python3", cmdline="python3 agent/main.py", source="polling",
    ))
    for i in range(8):
        store.push_process(ProcessExecEvent(
            timestamp=base + timedelta(seconds=2 + i * 5),
            pid=2001 + i, ppid=2000, name="bash",
            cmdline=f"bash -c 'cmd-{i}'", source="polling",
        ))
    for i in range(4):  # BEH-002: 4 LLM connections in 120s so aggregate crosses threshold
        store.push_network(NetworkConnectEvent(
            timestamp=base + timedelta(seconds=5 + i * 25), pid=2000, process_name="python3",
            remote_addr="api.anthropic.com", remote_port=443, local_port=44444 + i,
            protocol="tcp", sni="api.anthropic.com", source="polling",
        ))
    store.push_file(FileChangeEvent(
        timestamp=base + timedelta(seconds=25), path="/repo/src/foo.py",
        action="modified", pid=2001, process_name="bash", source="polling",
    ))
    # BEH-003 (burst write): 10+ files, 3+ dirs in 30s so aggregate crosses 0.45
    for i in range(10):
        store.push_file(FileChangeEvent(
            timestamp=base + timedelta(seconds=30 + i * 2),
            path=f"/repo/dir{i % 3}/f{i}.py", action="modified",
            pid=2001 + (i % 8), process_name="bash", source="polling",
        ))
    # BEH-006: one sensitive path so 4th pattern fires (aggregate >= 0.45)
    store.push_file(FileChangeEvent(
        timestamp=base + timedelta(seconds=50), path="/home/dev/.env",
        action="modified", pid=2000, process_name="python3", source="polling",
    ))
    return store


def seed_shell_fanout_false_positive() -> EventStore:
    """Normal dev: 3 shells in 60s (below min_children 5)."""
    store = _store()
    base = _base_time()
    store.push_process(ProcessExecEvent(
        timestamp=base, pid=3000, ppid=1,
        name="zsh", cmdline="-zsh", source="polling",
    ))
    for i in range(3):
        store.push_process(ProcessExecEvent(
            timestamp=base + timedelta(seconds=10 + i * 15),
            pid=3001 + i, ppid=3000, name="bash",
            cmdline=f"bash -c 'make step-{i}'", source="polling",
        ))
    return store


def seed_shell_fanout_ambiguous() -> EventStore:
    """Edge: exactly 5 shells in 60s, no LLM (may still fire at lower score)."""
    store = _store()
    base = _base_time()
    store.push_process(ProcessExecEvent(
        timestamp=base, pid=4000, ppid=1,
        name="node", cmdline="node run.js", source="polling",
    ))
    for i in range(5):
        store.push_process(ProcessExecEvent(
            timestamp=base + timedelta(seconds=i * 10),
            pid=4001 + i, ppid=4000, name="sh",
            cmdline=f"sh -c 'test {i}'", source="polling",
        ))
    return store


def seed_shell_fanout_renamed() -> EventStore:
    """Same as positive but root name is custom (Unknown Agent path)."""
    store = _store()
    base = _base_time()
    store.push_process(ProcessExecEvent(
        timestamp=base, pid=5000, ppid=1,
        name="my-custom-agent", cmdline="/opt/my-custom-agent --daemon", source="polling",
    ))
    for i in range(8):
        store.push_process(ProcessExecEvent(
            timestamp=base + timedelta(seconds=2 + i * 5),
            pid=5001 + i, ppid=5000, name="bash",
            cmdline=f"bash -c 'run {i}'", source="polling",
        ))
    for i in range(4):  # BEH-002 so aggregate crosses threshold
        store.push_network(NetworkConnectEvent(
            timestamp=base + timedelta(seconds=5 + i * 25), pid=5000, process_name="my-custom-agent",
            remote_addr="api.openai.com", remote_port=443, local_port=55555 + i,
            protocol="tcp", sni="api.openai.com", source="polling",
        ))
    for i in range(10):  # BEH-003
        store.push_file(FileChangeEvent(
            timestamp=base + timedelta(seconds=45 + i * 2), path=f"/w/d{i % 3}/f{i}.py",
            action="modified", pid=5001 + (i % 8), process_name="bash", source="polling",
        ))
    store.push_file(FileChangeEvent(
        timestamp=base + timedelta(seconds=65), path="/home/x/.env",
        action="modified", pid=5000, process_name="my-custom-agent", source="polling",
    ))
    return store


# ---------------------------------------------------------------------------
# DETEC-BEH-CORE-02: Read-Modify-Write Loop
# ---------------------------------------------------------------------------

def seed_rmw_positive() -> EventStore:
    """Clean positive: 3 file-net-file cycles with model endpoint."""
    store = _store()
    base = _base_time()
    store.push_process(ProcessExecEvent(
        timestamp=base, pid=6000, ppid=1,
        name="cursor", cmdline="Cursor", source="polling",
    ))
    # Cycle 1: file @ 0, net @ 2, file @ 4
    store.push_file(FileChangeEvent(
        timestamp=base, path="/proj/src/a.py", action="modified",
        pid=6000, process_name="cursor", source="polling",
    ))
    store.push_network(NetworkConnectEvent(
        timestamp=base + timedelta(seconds=2), pid=6000, process_name="cursor",
        remote_addr="api.anthropic.com", remote_port=443, local_port=60001,
        protocol="tcp", sni="api.anthropic.com", source="polling",
    ))
    store.push_file(FileChangeEvent(
        timestamp=base + timedelta(seconds=4), path="/proj/src/a.py", action="modified",
        pid=6000, process_name="cursor", source="polling",
    ))
    # Cycle 2: file @ 5, net @ 7, file @ 8
    store.push_file(FileChangeEvent(
        timestamp=base + timedelta(seconds=5), path="/proj/lib/b.py", action="modified",
        pid=6000, process_name="cursor", source="polling",
    ))
    store.push_network(NetworkConnectEvent(
        timestamp=base + timedelta(seconds=7), pid=6000, process_name="cursor",
        remote_addr="api.anthropic.com", remote_port=443, local_port=60002,
        protocol="tcp", sni="api.anthropic.com", source="polling",
    ))
    store.push_file(FileChangeEvent(
        timestamp=base + timedelta(seconds=8), path="/proj/lib/b.py", action="modified",
        pid=6000, process_name="cursor", source="polling",
    ))
    # Cycle 3
    store.push_file(FileChangeEvent(
        timestamp=base + timedelta(seconds=9), path="/proj/src/c.py", action="modified",
        pid=6000, process_name="cursor", source="polling",
    ))
    store.push_network(NetworkConnectEvent(
        timestamp=base + timedelta(seconds=10), pid=6000, process_name="cursor",
        remote_addr="api.anthropic.com", remote_port=443, local_port=60003,
        protocol="tcp", sni="api.anthropic.com", source="polling",
    ))
    store.push_file(FileChangeEvent(
        timestamp=base + timedelta(seconds=11), path="/proj/src/c.py", action="modified",
        pid=6000, process_name="cursor", source="polling",
    ))
    # Extra LLM connections so BEH-002 fires and aggregate crosses threshold
    for i in range(3):
        store.push_network(NetworkConnectEvent(
            timestamp=base + timedelta(seconds=15 + i * 30), pid=6000, process_name="cursor",
            remote_addr="api.anthropic.com", remote_port=443, local_port=60010 + i,
            protocol="tcp", sni="api.anthropic.com", source="polling",
        ))
    for i in range(10):  # BEH-003
        store.push_file(FileChangeEvent(
            timestamp=base + timedelta(seconds=20 + i * 2), path=f"/proj/d{i % 3}/x{i}.py",
            action="modified", pid=6000, process_name="cursor", source="polling",
        ))
    store.push_file(FileChangeEvent(
        timestamp=base + timedelta(seconds=40), path="/home/dev/.env",
        action="modified", pid=6000, process_name="cursor", source="polling",
    ))
    return store


def seed_rmw_false_positive() -> EventStore:
    """Normal edit: one file edit and one API call (single cycle, min_cycles=2)."""
    store = _store()
    base = _base_time()
    store.push_process(ProcessExecEvent(
        timestamp=base, pid=7000, ppid=1,
        name="code", cmdline="code .", source="polling",
    ))
    store.push_file(FileChangeEvent(
        timestamp=base, path="/dev/app.js", action="modified",
        pid=7000, process_name="code", source="polling",
    ))
    store.push_network(NetworkConnectEvent(
        timestamp=base + timedelta(seconds=2), pid=7000, process_name="code",
        remote_addr="api.openai.com", remote_port=443, local_port=70001,
        protocol="tcp", sni="api.openai.com", source="polling",
    ))
    store.push_file(FileChangeEvent(
        timestamp=base + timedelta(seconds=4), path="/dev/app.js", action="modified",
        pid=7000, process_name="code", source="polling",
    ))
    return store


def seed_rmw_ambiguous() -> EventStore:
    """Edge: exactly 2 cycles (min_cycles) + LLM so aggregate crosses threshold."""
    store = _store()
    base = _base_time()
    store.push_process(ProcessExecEvent(
        timestamp=base, pid=8000, ppid=1,
        name="python3", cmdline="python agent.py", source="polling",
    ))
    for cycle in range(2):
        t = cycle * 8
        store.push_file(FileChangeEvent(
            timestamp=base + timedelta(seconds=t), path=f"/w/d{cycle}/f.py", action="modified",
            pid=8000, process_name="python3", source="polling",
        ))
        store.push_network(NetworkConnectEvent(
            timestamp=base + timedelta(seconds=t + 2), pid=8000, process_name="python3",
            remote_addr="localhost", remote_port=11434, local_port=80000 + cycle,
            protocol="tcp", sni=None, source="polling",
        ))
        store.push_file(FileChangeEvent(
            timestamp=base + timedelta(seconds=t + 4), path=f"/w/d{cycle}/f.py", action="modified",
            pid=8000, process_name="python3", source="polling",
        ))
    for i in range(3):  # BEH-002
        store.push_network(NetworkConnectEvent(
            timestamp=base + timedelta(seconds=20 + i * 35), pid=8000, process_name="python3",
            remote_addr="api.openai.com", remote_port=443, local_port=80100 + i,
            protocol="tcp", sni="api.openai.com", source="polling",
        ))
    for i in range(10):  # BEH-003
        store.push_file(FileChangeEvent(
            timestamp=base + timedelta(seconds=25 + i * 2), path=f"/w/d{i % 3}/g{i}.py",
            action="modified", pid=8000, process_name="python3", source="polling",
        ))
    store.push_file(FileChangeEvent(
        timestamp=base + timedelta(seconds=45), path="/home/u/.env",
        action="modified", pid=8000, process_name="python3", source="polling",
    ))
    return store


# ---------------------------------------------------------------------------
# DETEC-BEH-CORE-03: Sensitive Access Followed by Outbound
# ---------------------------------------------------------------------------

def seed_credential_outbound_positive() -> EventStore:
    """Sensitive path access then outbound (BEH-006 + BEH-002 + BEH-003 + BEH-001)."""
    store = _store()
    base = _base_time()
    store.push_process(ProcessExecEvent(
        timestamp=base, pid=9000, ppid=1,
        name="python3", cmdline="python script.py", source="polling",
    ))
    for i in range(6):  # BEH-001 so aggregate crosses threshold
        store.push_process(ProcessExecEvent(
            timestamp=base + timedelta(seconds=1 + i * 8), pid=9001 + i, ppid=9000,
            name="bash", cmdline=f"bash -c 'x{i}'", source="polling",
        ))
    store.push_file(FileChangeEvent(
        timestamp=base + timedelta(seconds=0),
        path="/home/dev/.env", action="modified",
        pid=9000, process_name="python3", source="polling",
    ))
    store.push_file(FileChangeEvent(
        timestamp=base + timedelta(seconds=1),
        path="/home/dev/.aws/credentials", action="modified",
        pid=9000, process_name="python3", source="polling",
    ))
    store.push_network(NetworkConnectEvent(
        timestamp=base + timedelta(seconds=12),
        pid=9000, process_name="python3",
        remote_addr="api.anthropic.com", remote_port=443, local_port=90001,
        protocol="tcp", sni="api.anthropic.com", source="polling",
    ))
    for i in range(2):  # More LLM so BEH-002 fires
        store.push_network(NetworkConnectEvent(
            timestamp=base + timedelta(seconds=20 + i * 40), pid=9000, process_name="python3",
            remote_addr="api.anthropic.com", remote_port=443, local_port=90002 + i,
            protocol="tcp", sni="api.anthropic.com", source="polling",
        ))
    for i in range(10):  # BEH-003 so aggregate crosses threshold
        store.push_file(FileChangeEvent(
            timestamp=base + timedelta(seconds=30 + i * 2), path=f"/home/dev/d{i % 3}/f{i}.py",
            action="modified", pid=9000, process_name="python3", source="polling",
        ))
    return store


def seed_credential_outbound_false_positive() -> EventStore:
    """Sensitive access but no network after (or network before access)."""
    store = _store()
    base = _base_time()
    store.push_process(ProcessExecEvent(
        timestamp=base, pid=10000, ppid=1,
        name="vim", cmdline="vim .env", source="polling",
    ))
    store.push_file(FileChangeEvent(
        timestamp=base + timedelta(seconds=5),
        path="/home/user/.env", action="modified",
        pid=10000, process_name="vim", source="polling",
    ))
    # No network event after; credential_require_network + temporal => no qualifying net
    return store


def seed_credential_outbound_ambiguous() -> EventStore:
    """Sensitive access then outbound at window boundary + BEH-001 so aggregate crosses threshold."""
    store = _store()
    base = _base_time()
    store.push_process(ProcessExecEvent(
        timestamp=base, pid=11000, ppid=1,
        name="node", cmdline="node deploy.js", source="polling",
    ))
    for i in range(6):  # BEH-001
        store.push_process(ProcessExecEvent(
            timestamp=base + timedelta(seconds=1 + i * 8), pid=11001 + i, ppid=11000,
            name="bash", cmdline=f"sh -c 'run {i}'", source="polling",
        ))
    store.push_file(FileChangeEvent(
        timestamp=base, path="/home/x/.kube/config", action="modified",
        pid=11000, process_name="node", source="polling",
    ))
    store.push_network(NetworkConnectEvent(
        timestamp=base + timedelta(seconds=299),  # within 300s default window
        pid=11000, process_name="node",
        remote_addr="api.openai.com", remote_port=443, local_port=11001,
        protocol="tcp", sni="api.openai.com", source="polling",
    ))
    for i in range(2):  # BEH-002
        store.push_network(NetworkConnectEvent(
            timestamp=base + timedelta(seconds=305 + i * 40), pid=11000, process_name="node",
            remote_addr="api.openai.com", remote_port=443, local_port=11002 + i,
            protocol="tcp", sni="api.openai.com", source="polling",
        ))
    for i in range(10):  # BEH-003
        store.push_file(FileChangeEvent(
            timestamp=base + timedelta(seconds=310 + i * 2), path=f"/home/x/d{i % 3}/h{i}.py",
            action="modified", pid=11000, process_name="node", source="polling",
        ))
    return store


def seed_credential_outbound_unknown_dest() -> EventStore:
    """Sensitive access then outbound to unknown host; add BEH-001 so aggregate crosses threshold."""
    store = _store()
    base = _base_time()
    store.push_process(ProcessExecEvent(
        timestamp=base, pid=12000, ppid=1,
        name="python3", cmdline="python exfil.py", source="polling",
    ))
    for i in range(6):  # Shell fan-out so BEH-001 fires
        store.push_process(ProcessExecEvent(
            timestamp=base + timedelta(seconds=1 + i * 8), pid=12001 + i, ppid=12000,
            name="bash", cmdline=f"bash -c 'x{i}'", source="polling",
        ))
    store.push_file(FileChangeEvent(
        timestamp=base, path="/home/u/.ssh/id_rsa", action="modified",
        pid=12000, process_name="python3", source="polling",
    ))
    store.push_network(NetworkConnectEvent(
        timestamp=base + timedelta(seconds=10),
        pid=12000, process_name="python3",
        remote_addr="unknown-external.com", remote_port=443, local_port=12001,
        protocol="tcp", sni="unknown-external.com", source="polling",
    ))
    # BEH-003 only (no model traffic) so BEH-006 evidence has model_vs_unknown=unknown
    for i in range(10):
        store.push_file(FileChangeEvent(
            timestamp=base + timedelta(seconds=70 + i * 2), path=f"/home/u/d{i % 3}/z{i}.py",
            action="modified", pid=12000, process_name="python3", source="polling",
        ))
    return store


# ---------------------------------------------------------------------------
# DETEC-BEH-CORE-04: Agent Execution Chain (BEH-009)
# ---------------------------------------------------------------------------

def seed_execution_chain_positive() -> EventStore:
    """Clean positive: LLM call then shell then file write within window (BEH-009)."""
    store = _store()
    base = _base_time()
    store.push_process(ProcessExecEvent(
        timestamp=base, pid=6000, ppid=0,
        name="python3", cmdline="python3 agent.py", source="polling",
    ))
    store.push_process(ProcessExecEvent(
        timestamp=base + timedelta(seconds=5), pid=6001, ppid=6000,
        name="bash", cmdline="bash", source="polling",
    ))
    store.push_network(NetworkConnectEvent(
        timestamp=base, pid=6000, process_name="python3",
        remote_addr="api.anthropic.com", remote_port=443, local_port=5000,
        protocol="tcp", sni="api.anthropic.com", source="polling",
    ))
    store.push_file(FileChangeEvent(
        timestamp=base + timedelta(seconds=10), path="/tmp/out.txt",
        action="modified", pid=6000, process_name="python3", source="polling",
    ))
    return store
