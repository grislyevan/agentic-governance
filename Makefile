# Detec agentic-governance: test and build targets
# Run from repo root. See docs/ci-security.md and docs/release-checklist.md for CI/release.
# Quick start for new contributors: run `make smoke` to bootstrap and verify local sanity (no Postgres needed).

.PHONY: bootstrap-dev test-collector test-api test-protocol test-all-safe build-dashboard \
        test-collector-noinstall test-api-noinstall test-protocol-noinstall smoke dev help

help:
	@echo "Detec test targets"
	@echo ""
	@echo "  Quick start (new contributors):"
	@echo "    make smoke                       Bootstrap + collector smoke + core behavioral tests (no Postgres needed)"
	@echo ""
	@echo "  With pip bootstrap (first run or fresh clone):"
	@echo "    make bootstrap-dev               Install dev + API deps (run once)"
	@echo "    make test-collector              pip install then run collector tests"
	@echo "    make test-api                    pip install then run API tests"
	@echo "    make test-protocol               pip install then run protocol tests"
	@echo "    make test-all-safe               All three suites with bootstrap"
	@echo ""
	@echo "  Without bootstrap (locked venv / CI / already bootstrapped):"
	@echo "    make test-collector-noinstall    Collector tests, no pip step"
	@echo "    make test-api-noinstall          API tests, no pip step (needs DATABASE_URL etc.)"
	@echo "    make test-protocol-noinstall     Protocol tests, no pip step"
	@echo ""
  @echo "  Other:"
	@echo "    make build-dashboard             npm ci + build dashboard"
	@echo "    make dev                         Run API (hot-reload) + dashboard (Vite) concurrently"
	@echo ""
	@echo "See docs/local-test-profiles.md for profile-specific setup guidance."

# Single-command setup for contributors: install project with dev extras and API deps so all test suites can run.
bootstrap-dev:
	pip install -e ".[dev]"
	pip install -r api/requirements.txt

# Contributor quick-path smoke check: bootstrap, confirm collector works without API, run core behavioral detections.
# Does NOT require Postgres or any external service.
smoke:
	$(MAKE) bootstrap-dev
	detec scan --dry-run --verbose
	python -m pytest collector/tests/test_behavioral_core_detections.py -q

test-collector:
	pip install -e ".[dev]"
	python -m pytest collector/tests/ -m 'not benchmark and not slow' -x -q

# API tests require Postgres and env: DATABASE_URL, JWT_SECRET, SEED_ADMIN_PASSWORD (see .github/workflows/ci.yml)
test-api:
	pip install -e .
	pip install -r api/requirements.txt
	cd api && python -m pytest tests/ -m 'not benchmark and not slow' -x -q

test-protocol:
	pip install -e ".[dev]"
	python -m pytest protocol/tests/ -q

test-all-safe: test-collector test-api test-protocol

build-dashboard:
	cd dashboard && npm ci && npm run build

# Offline/locked-env variants: skip installer bootstrap and run tests directly.
test-collector-noinstall:
	python -m pytest collector/tests/ -m 'not benchmark and not slow' -x -q

# API tests require preinstalled deps + env vars; no pip bootstrap in this target.
test-api-noinstall:
	cd api && python -m pytest tests/ -m 'not benchmark and not slow' -x -q

# Protocol async tests require pytest-asyncio already installed in the active env.
test-protocol-noinstall:
	python -m pytest protocol/tests/ -q

# Run the full local stack: API (uvicorn --reload) + dashboard (Vite dev server) in one terminal.
# Requires: pip deps installed (make bootstrap-dev) and npm deps installed (cd dashboard && npm ci).
# API served at http://localhost:8000, dashboard at http://localhost:5173 (Vite proxies /api to :8000).
dev:
	@trap 'kill 0' INT; \
	cd api && uvicorn main:app --reload --port 8000 & \
	cd dashboard && npm run dev & \
	wait
