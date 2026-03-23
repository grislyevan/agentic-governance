# Detec Compliance Program

High-level TODO created by [comply](https://github.com/strongdm/comply), updated Mar 11 2026.

## Initialization Phase (hours)
- [x] Add project to source control
- [x] Configure `comply.yml` with org name and GitHub ticketing
- [ ] Install BasicTeX for PDF generation: `brew install --cask basictex` (requires sudo)
- [ ] Set `GITHUB_TOKEN` environment variable for ticketing integration
- [ ] Verify `comply build` generates valid output
- [ ] Verify `comply sync` executes without errors

## Authoring Phase (weeks)
- [x] Validate standards/ (TSC-2017 controls confirmed)
- [x] Customize narratives/ (all 5 narratives written for Detec)
    - [x] Organizational Narrative: entity type, structure, risk management
    - [x] Products and Services Narrative: agent, API, dashboard architecture
    - [x] Security Architecture Narrative: threat model, access controls, risk assessment
    - [x] System Architecture Narrative: data flow, logical access, backup/recovery
    - [x] Control Environment Narrative: logical, policy, procedural controls
- [x] Review and update policies/
    - [x] Fixed invalid TSC control references (CC9.9) in Encryption and Password policies
    - [x] Updated Incident Response Policy with contact procedures
    - [ ] Distribute controls among policies (review for gaps)
    - [ ] Ensure policies address all controls (comply todo shows 61/61 satisfied)
- [x] Customize procedures/
    - [x] Patch procedure: OS and dependency patching with test gates
    - [x] Onboarding procedure: access provisioning, workstation setup, agent install
    - [x] Offboarding procedure: access revocation, credential rotation, device recovery
    - [x] Workstation review: Detec dashboard inventory, compliance checks
    - [x] New: Vulnerability Scan procedure (monthly, with dependency/SAST/infrastructure checks)
    - [ ] Assign schedules (cron expressions added to patch, workstation, vulnerability-scan)
    - [ ] Create valid ticket templates
- [x] Verify `comply todo` indicates all controls satisfied (61/61 YES)

## Deployment Phase (weeks)
- [ ] Deploy `comply scheduler` (see README.md for example script)
- [ ] Deploy `comply build` output to shared location
- [ ] Distribute policies to team
- [ ] Train team on use of ticketing system to designate compliance-relevant activity

## Operating Phase (eternal)
- [ ] Monitor timely ticket workflow
- [ ] Adjust and re-publish narratives, policies and procedures as necessary

## Audit Phase (weeks, annually)
- [ ] Import request list (tickets will be generated)
- [ ] Fulfill all request tickets
    - [ ] Attach policies, procedures, and narratives
    - [ ] Attach evidence collected by previously-executed procedure tickets

---

## Backlog: open items with owner, due date, evidence

Each open item above is tracked below with owner, due date, and evidence location.

| ID | Open item | Owner | Due | Evidence location |
|----|-----------|-------|-----|-------------------|
| INIT-1 | Install BasicTeX for PDF generation | Compliance / Ops | 2026-04-30 | `comply build` output; this file (checkbox) |
| INIT-2 | Set GITHUB_TOKEN for ticketing | Compliance / Ops | 2026-04-30 | CI or runbook; this file |
| INIT-3 | Verify comply build generates valid output | Compliance / Ops | 2026-04-30 | compliance/README.md or build artifact path |
| INIT-4 | Verify comply sync executes without errors | Compliance / Ops | 2026-04-30 | compliance/README.md; sync log or ticket |
| AUTH-1 | Distribute controls among policies (review for gaps) | Compliance lead | 2026-05-15 | compliance/policies/; comply todo output |
| AUTH-2 | Ensure policies address all controls (61/61) | Compliance lead | 2026-05-15 | `comply todo` output; this file |
| AUTH-3 | Assign schedules (cron for patch, workstation, vulnerability-scan) | Compliance / Ops | 2026-05-15 | compliance/procedures/*.md (schedule fields) |
| AUTH-4 | Create valid ticket templates | Compliance / Ops | 2026-05-15 | compliance/templates/ or ticketing system |
| DEP-1 | Deploy comply scheduler | Ops / Compliance | 2026-06-30 | compliance/README.md; scheduler config or script |
| DEP-2 | Deploy comply build output to shared location | Ops | 2026-06-30 | Documented path or URL in compliance/README.md |
| DEP-3 | Distribute policies to team | Compliance lead | 2026-06-30 | Distribution log or acknowledgment |
| DEP-4 | Train team on ticketing system | Compliance lead | 2026-06-30 | Training record or runbook link |
| OP-1 | Monitor timely ticket workflow | Compliance / Ops | Ongoing | Ticket dashboard or periodic report |
| OP-2 | Adjust and re-publish narratives, policies, procedures | Compliance lead | As needed | compliance/narratives/, compliance/policies/, compliance/procedures/ |
| AUDIT-1 | Import request list (tickets generated) | Compliance lead | Annual | Audit request list; ticket IDs |
| AUDIT-2 | Fulfill all request tickets (attach policies, procedures, narratives, evidence) | Compliance lead | Per audit | Ticket attachments; compliance/ build output |
