# INIT-43 — Claude Code Process/File/Network Signal Map (Full Deep Revision)

## Scope
Parent: **INIT-13 (Claude Code detection profile)**
Subtask objective: define a high-fidelity signal map for Claude Code across **process**, **file/artifact**, and **network** layers, including confidence contribution, failure modes, and correlation rules.

---

## 1) Why This Subtask Matters
Claude Code attribution quality depends heavily on the first three telemetry layers:
- process lineage establishes execution truth,
- file artifacts provide persistence and forensic continuity,
- network traces corroborate cloud interaction timing.

If these layers are weakly modeled, downstream confidence and governance decisions degrade.

---

## 2) Process Signal Map

### Core process signals
1. CLI invocation identity
   - binary path / package entrypoint / hash / signer where available.
2. Parent lineage
   - terminal/IDE terminal/shell launcher ancestry.
3. Child process fan-out
   - shell, git, build/test tools spawned near prompt-response windows.
4. Session shape
   - long-lived interactive CLI sessions with iterative command bursts.

### Normalization fields
- `proc.name`
- `proc.path`
- `proc.hash`
- `proc.signer`
- `proc.parent_chain[]`
- `proc.child_chain[]`
- `proc.start_time`
- `proc.duration_ms`
- `proc.args_digest`

### Confidence contribution
- High when entrypoint + parent chain + child execution pattern align.
- Medium when only top-level process identity is present.
- Low when generic shell/python process seen without tool attribution context.

### Process-layer failure modes
- wrapper scripts mask executable name,
- renamed binary aliases,
- containerized execution reducing host-native lineage visibility.

Mitigation:
- lineage-first matching,
- behavior-correlated attribution,
- confidence penalties for unresolved parent/child chains.

---

## 3) File/Artifact Signal Map

### Core artifact signals
1. Config and state footprints
   - user-level and project-level config/state files tied to Claude workflows.
2. Session residue
   - history/transcript/cache artifacts where present.
3. Repo mutation pattern
   - clustered edits tied temporally to Claude process windows.
4. First-seen and drift indicators
   - artifact creation/modification evolution over time.

### Normalization fields
- `artifact.path`
- `artifact.type` (config/cache/session/temp)
- `artifact.hash`
- `artifact.first_seen`
- `artifact.last_modified`
- `artifact.repo_scope`
- `artifact.sensitivity_tag`

### Confidence contribution
- High for tool presence continuity when artifacts are stable and correlated.
- Medium for standalone artifact presence.
- Low when artifacts are stale, relocated, or uncorrelated.

### File-layer failure modes
- non-default paths,
- cleanup/ephemeral artifacts,
- shared temp locations creating ambiguity.

Mitigation:
- hash and timeline correlation,
- repository scope binding,
- artifact recency weighting.

---

## 4) Network Signal Map

### Core network signals
1. outbound model/API interaction windows
2. destination identity (hostname/SNI/IP where available)
3. burst cadence around CLI interaction loops
4. process-to-connection linkage for attribution certainty

### Normalization fields
- `net.dest_host`
- `net.dest_ip`
- `net.dest_port`
- `net.sni`
- `net.bytes_out`
- `net.bytes_in`
- `net.conn_start`
- `net.conn_end`
- `net.proc_link_confidence`

### Confidence contribution
- Medium as standalone corroboration.
- High only when process linkage and timing alignment are strong.

### Network-layer failure modes
- shared proxy/gateway paths,
- endpoint obfuscation by relay infrastructure,
- inability to distinguish tool-specific traffic on shared endpoints.

Mitigation:
- treat network as corroborative layer,
- enforce explicit confidence penalties for ambiguous routing,
- never rely on network-only hard enforcement.

---

## 5) Cross-Layer Correlation Rules

### Rule C1 — High-confidence Claude attribution
Requires:
- process entrypoint + lineage,
- at least one fresh artifact signal,
- and either network timing alignment or strong behavioral continuity.

### Rule C2 — Medium-confidence attribution
Any two layers align, but missing process certainty or recency in artifacts.

### Rule C3 — Low-confidence attribution
single-layer evidence only or conflicting multi-layer signals.

### Rule C4 — Ambiguity override
If layers conflict materially (e.g., process says unknown wrapper, network says generic endpoint), downgrade confidence and move to warn/approval paths only.

---

## 6) Signal Quality Scoring Guidance

Weighting suggestion (for this subtask scope):
- Process: 0.45
- File: 0.30
- Network: 0.25

Penalty examples:
- missing parent chain: -0.15
- stale artifact only: -0.10
- ambiguous proxy route: -0.10
- unresolved process-network linkage: -0.10

These are starting values and must be calibrated in replay.

---

## 7) Validation Plan (Subtask-Level)

### Positive checks
1. canonical Claude CLI session with expected process/file/network alignment.
2. multi-command repo workflow with artifact and network corroboration.
3. repeated session consistency across reruns.

### Adversarial checks
1. wrapper alias invocation (process ambiguity injection).
2. proxy-routed network path (network ambiguity injection).

### Required outputs
- per-layer signal capture report,
- confidence calculation trace,
- correlation rule evaluation logs,
- residual ambiguity notes.

---

## 8) Deliverable Definition of Done
- [x] Process signal set defined with normalization fields.
- [x] File/artifact signal set defined with recency/integrity semantics.
- [x] Network signal set defined with attribution caveats.
- [x] Cross-layer correlation rules and confidence guidance documented.
- [x] Subtask-level validation plan specified.
- [ ] Empirical run artifacts linked.
