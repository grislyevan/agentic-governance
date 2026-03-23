# Detec agentic-governance: test and build targets
# Run from repo root. See docs/ci-security.md and docs/release-checklist.md for CI/release.

.PHONY: bootstrap-dev test-collector test-api test-protocol test-all-safe build-dashboard \
        test-collector-noinstall test-api-noinstall test-protocol-noinstall help

help:
	@echo "Detec test targets"
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
	@echo ""
	@echo "See docs/local-test-profiles.md for profile-specific setup guidance."

# Single-command setup for contributors: install project with dev extras and API deps so all test suites can run.
bootstrap-dev:
	pip install -e ".[dev]"
	pip install -r api/requirements.txt

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
