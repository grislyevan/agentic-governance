id: "offboard"
name: "Offboard User"
satisfies:
  TSC:
    - CC6.2
    - CC6.3
---

# Offboard User

Resolve this ticket by executing the following steps:

## Immediate Access Revocation

- [ ] Immediately suspend user in SSO/identity provider
- [ ] Revoke GitHub organization membership
- [ ] Disable Detec dashboard account
- [ ] Revoke cloud hosting access (if applicable)
- [ ] Revoke team communication access

## Verification

- [ ] Append HR termination request to this ticket
- [ ] Review manually-provisioned applications for this role or user
- [ ] Validate access revocation in each system
- [ ] Rotate any shared credentials the departing user had access to
- [ ] If user had access to API keys or JWT secrets, rotate those credentials
- [ ] Append confirmation of revocation to this ticket

## Device Recovery

- [ ] Collect or remotely wipe corporate workstation
- [ ] Verify Detec agent is no longer reporting from the user's endpoint
- [ ] Remove endpoint from the Detec dashboard
