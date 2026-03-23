# Windows Behavior Lab Plan (Draft)

## Objective
Build a repeatable Windows-only behavior lab program to harden Detec policy enforcement and reduce false negatives for high-protection posture.

## Scope
- **In scope:** benign simulation of attacker-like behaviors for detection/enforcement validation.
- **Out of scope:** real malware, external C2, destructive payloads, privilege abuse outside lab host.
- **Primary target host(s):** isolated Windows lab endpoints enrolled to current tenant.

## Success Criteria
1. Every lab technique has a deterministic **pass/block/alert** outcome.
2. High-protection policy blocks or meaningfully alerts on persistence/evasion behaviors.
3. Dashboard reflects endpoint conformity and enforcement posture without stale/nonconformant drift.
4. Results are reproducible across reruns (same profile => similar outcomes).

## Lab Packs (initial)

### Pack A: Persistence
- Scheduled task create/run/delete
- Run key add/remove (HKCU/HKLM where allowed)
- Service install/start/modify attempts (safe dummy services)
- Startup folder/dropper-like artifact behavior

### Pack B: Obfuscation / Evasion
- PowerShell `-EncodedCommand`
- Split/concat command reconstruction patterns
- Parent-child process chain anomalies
- Renamed/script-wrapper execution patterns

### Pack C: LOLBin / Execution Abuse
- `mshta`, `rundll32`, `regsvr32`, `wmic`, `certutil`, `bitsadmin`/BITS variants
- Download-like and execution-like command patterns (safe/internal URLs only)

### Pack D: Policy Stress / Throughput
- Burst execution patterns (short-lived process fanout)
- Jittered behavior loops to test timing-based detections
- Mixed benign + suspicious event streams for confidence tuning

## Profiles
- **light:** low-noise smoke tests; quick policy sanity check
- **medium:** realistic workstation abuse simulation
- **aggressive:** dense bursts + chained techniques for high-protection stress test

## Harness Architecture (planned)
1. **Controller script (macOS):** launches remote lab packs via SSH.
2. **Windows runner script:** executes selected pack/profile, captures local artifacts + execution outcomes.
3. **Result collector:** stores run metadata and outcomes in repo (`lab-runs/windows/<timestamp>/`).
4. **Analyzer:** maps outcomes to pass/block/alert matrix and compares to expected policy behavior.

## Data to Capture Per Technique
- Technique ID + pack/profile
- Start/end timestamps
- Command attempted (normalized)
- Exit code / error class
- Local artifact evidence (if any)
- Agent event emission observed (yes/no)
- Policy decision observed (`allow|alert|block`)
- Enforcement action observed (`none|log|kill|prevent`)

## Reporting Format
Per run:
- Summary: total tested / blocked / alerted / missed
- Matrix by technique
- Top misses (highest risk allowed behaviors)
- Recommended policy rule updates

## Iteration Loop
1. Run baseline (medium profile all packs)
2. Identify misses + noisy false positives
3. Tune rules/thresholds
4. Re-run focused subset
5. Promote changes after two stable reruns

## Guardrails
- Lab host only; no internet payload retrieval beyond internal health endpoints
- No persistence left behind after run (cleanup phase mandatory)
- No credential dumping / destructive actions
- All actions logged and reversible

## Immediate Next Steps
1. Define technique catalog with stable IDs (A-01, A-02, ...).
2. Implement Windows runner skeleton with dry-run + execute modes.
3. Implement baseline Pack A + Pack B (light/medium).
4. Add result directory schema and summary generator.
5. Run first baseline and review misses before adding Pack C/D.
