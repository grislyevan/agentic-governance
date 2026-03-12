id: "workstation"
name: "Review Devices and Workstations"
cron: "0 0 0 1 1,4,7,10 *"
satisfies:
  TSC:
    - CC6.8
    - CC7.1
---

# Device and Workstation Review

Resolve this ticket by executing the following steps:

## Inventory Collection

- [ ] Export current endpoint inventory from the Detec dashboard (all reporting agents)
- [ ] Cross-reference with HR employee roster to identify missing or extra devices
- [ ] Identify any endpoints that have stopped reporting (stale agents)

## Security Compliance Check

For each active workstation, verify:

- [ ] Operating system is within one generation of current
- [ ] Full-disk encryption is enabled
- [ ] Endpoint protection software is installed and up to date
- [ ] Detec agent is installed and reporting
- [ ] No unauthorized agentic AI tools detected (or detections are policy-compliant)

## Remediation

- [ ] Contact owners of non-compliant workstations with remediation instructions
- [ ] Set a 14-day remediation deadline
- [ ] Escalate unresolved non-compliance to management

## Documentation

- [ ] Attach workstation inventory and compliance summary to this ticket
- [ ] Note any remediation actions taken
