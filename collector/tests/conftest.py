# Collector tests: single path bootstrap so "from main import", "from orchestrator import",
# and "from evasion_suite_scenarios import" resolve. Run from repo root: python -m pytest collector/tests/ -v
from pathlib import Path
import sys

_collector_root = Path(__file__).resolve().parent.parent
_tests_dir = Path(__file__).resolve().parent
for _d in (_collector_root, _tests_dir):
    if str(_d) not in sys.path:
        sys.path.insert(0, str(_d))
