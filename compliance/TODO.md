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
