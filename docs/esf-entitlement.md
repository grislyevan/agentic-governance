# Endpoint Security Framework (ESF) Entitlement Status

**Purpose:** Track Apple Endpoint Security Framework entitlement status for the Detec collector. ESF is required for full behavioral-layer detection on macOS.

**Last updated:** 2026-03-12

---

## Why ESF Matters

The behavioral scanner defines detection patterns (shell fan-out, burst writes, git automation, credential access, etc.) that require a **populated event store** with live process and file telemetry. On macOS, the only reliable source for sub-second process and file events is Apple's Endpoint Security Framework (ESF).

- **With ESF:** Process exec, file write, and (optionally) network events are delivered in real time. Short-lived agentic patterns (e.g. shell → git → exit in under 2 seconds) are visible.
- **Without ESF:** The collector falls back to the **PollingProvider** (psutil every few seconds). Short-lived processes and rapid file bursts are often missed. The behavioral layer is effective for long-running interactive sessions but not for short-burst Class C/D patterns.

---

## Current Status

| Item | Status | Notes |
|------|--------|--------|
| ESF entitlement | **Not obtained** | Requires Apple Developer code signing with a dedicated System Extension entitlement. Typical timeline: 3–6 months from application. |
| Fallback | **PollingProvider** | Active. Used when native provider is unavailable or fails to start. |
| Behavioral layer | **Partially effective** | Works for long-running sessions; short-burst agentic patterns may be missed. |

**Recommendation:** Treat ESF entitlement application as a **release-gate dependency** for full behavioral detection on macOS, not a post-launch item. Start the process early.

---

## Where This Is Tracked

- **This doc:** Canonical status and rationale.
- **PROGRESS.md:** Pre-v1.0 / PM brief section lists "ESF entitlement (owner Eng)" as a tracked item.
- **Playbook:** Section 3 (Five-Layer Detection Model) and Section 11.1 (Telemetry) note that the behavioral layer is limited without ESF.

---

## References

- [collector/providers/esf_provider.py](../collector/providers/esf_provider.py) — ESF provider stub.
- [collector/providers/registry.py](../collector/providers/registry.py) — Provider selection; falls back to polling when ESF is unavailable.
- [collector/scanner/behavioral.py](../collector/scanner/behavioral.py) — Behavioral scanner; consumes event store populated by the active provider.
