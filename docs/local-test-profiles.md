# Local Test Profiles

Three tested profiles for running the Detec test suites locally. Pick the one that matches your environment and copy-paste the command blocks.

---

## Profile 1: Fresh internet-enabled dev machine

You have Python 3.11+, internet access, and nothing pre-installed yet.

```bash
# One-time: bootstrap dev dependencies and API deps
make bootstrap-dev

# Then run each suite
make test-collector-noinstall
make test-protocol-noinstall
make test-api-noinstall
```

`make bootstrap-dev` runs `pip install -e ".[dev]"` and `pip install -r api/requirements.txt`. After this, the `noinstall` targets are the fastest way to re-run tests without repeating the install step on every invocation.

---

## Profile 2: Corp proxy / restricted package index

You are behind a corporate proxy or a restricted PyPI mirror. Pip may time out or pull from an internal index.

```bash
# Set proxy before bootstrapping
export HTTPS_PROXY=https://proxy.corp.example.com:8080
export PIP_INDEX_URL=https://pypi.corp.example.com/simple/

# Bootstrap once (resolves packages via your proxy/index)
make bootstrap-dev

# Run tests — noinstall targets skip pip so proxy is irrelevant after bootstrap
make test-collector-noinstall
make test-protocol-noinstall
make test-api-noinstall
```

If your proxy requires auth: `export HTTPS_PROXY=https://user:pass@proxy.corp.example.com:8080`

**API tests** also need database env vars, even in this profile:

```bash
export DATABASE_URL=sqlite://       # in-memory SQLite (no Postgres needed locally)
export JWT_SECRET=any-local-secret
export SEED_ADMIN_PASSWORD=localpass
make test-api-noinstall
```

---

## Profile 3: Fully offline / locked venv

You have a pre-populated venv (packages already installed, no pip access). This is the CI-equivalent flow for air-gapped or locked environments.

```bash
# Activate your pre-populated venv
source /path/to/locked-venv/bin/activate   # Linux/macOS
# or: /path/to/locked-venv/Scripts/activate  (Windows)

# Set required env vars for API tests
export DATABASE_URL=sqlite://
export JWT_SECRET=any-local-secret
export SEED_ADMIN_PASSWORD=localpass

# Run directly — no install step
make test-collector-noinstall
make test-protocol-noinstall
make test-api-noinstall
```

For CI parity, pass `-x -q` flags (already set in the `noinstall` targets).

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| `ModuleNotFoundError: No module named 'pytest_asyncio'` | `pytest-asyncio` not in venv | Run `make bootstrap-dev` or `pip install pytest-asyncio` |
| `ModuleNotFoundError: No module named 'pytest'` | Venv not active or bootstrap not run | Activate venv, then `make bootstrap-dev` |
| Protocol tests hang or error on `asyncio` loop | `pytest-asyncio` version mismatch | `pip install "pytest-asyncio>=0.21"` |
| API tests fail with `DATABASE_URL not set` | Missing env var | `export DATABASE_URL=sqlite://` |
| API tests fail with `JWT_SECRET not set` | Missing env var | `export JWT_SECRET=any-value` |
| `pip` times out or SSL error | Proxy not configured | Set `HTTPS_PROXY` before running `make bootstrap-dev` |
| `import collector fails` in API test run | Package name collision — run suites separately | Run `make test-collector-noinstall` and `make test-api-noinstall` in separate invocations |
| `make: noinstall: No such target` | Old Makefile checkout | `git pull` or check Makefile for `test-*-noinstall` targets |

---

See also: [Makefile](../Makefile) · [docs/ci-security.md](ci-security.md)
