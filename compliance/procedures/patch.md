id: "patch"
name: "Apply OS and dependency patches"
cron: "0 0 0 15 * *"
satisfies:
  TSC:
    - CC7.1
    - CC8.1
---

# OS and Dependency Patch Procedure

Resolve this ticket by executing the following steps:

## Operating System Patches

- [ ] Review available OS patches for all team workstations
- [ ] Apply patches to a test workstation first
- [ ] Verify no regressions, then roll out to remaining workstations
- [ ] Confirm full-disk encryption and endpoint protection remain active post-patch

## Detec Platform Dependencies

- [ ] Run `pip audit` against `collector/requirements.txt` and `api/requirements.txt`
- [ ] Run `npm audit` against `dashboard/package.json`
- [ ] Review findings; update dependencies with known vulnerabilities
- [ ] Run collector tests: `pytest collector/tests/` (all 233 must pass)
- [ ] Run API tests: `pytest api/tests/` (all 122 must pass)
- [ ] Run protocol tests: `pytest protocol/tests/` (all 45 must pass)
- [ ] Run calibration regression: `pytest collector/tests/test_calibration.py -v`
- [ ] Deploy updated dependencies to staging, verify agent and API health
- [ ] Deploy to production

## Documentation

- [ ] Attach patch summary and test results to this ticket
