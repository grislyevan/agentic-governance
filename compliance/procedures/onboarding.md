id: "onboard"
name: "Onboard New User"
satisfies:
  TSC:
    - CC6.2
    - CC6.3
---

# Onboard New User

Resolve this ticket by executing the following steps:

## Access Provisioning

- [ ] Append HR add request to this ticket
- [ ] Validate role assignment with manager
- [ ] Create user account in the following systems:
    - [ ] GitHub organization (appropriate team membership)
    - [ ] Team communication platform (Slack or equivalent)
    - [ ] Cloud hosting provider (if DevOps/SRE role)
    - [ ] Detec dashboard (appropriate role: admin, analyst, or viewer)
- [ ] Provision any additional role-specific applications
- [ ] Append provisioning confirmation to this ticket

## Workstation Setup

- [ ] Verify workstation meets security requirements:
    - [ ] OS within one generation of current
    - [ ] Full-disk encryption enabled
    - [ ] Endpoint protection installed
    - [ ] Auto-updates enabled
- [ ] Install Detec endpoint agent on the new workstation
- [ ] Verify agent is reporting to the central API

## Training

- [ ] Schedule security awareness training
- [ ] Provide access to compliance policies and procedures
- [ ] Confirm with new user that they can access all provisioned systems
