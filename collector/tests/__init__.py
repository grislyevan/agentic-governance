# collector/tests — test suite for the agentic-governance collector
#
# Run from repo root:
#   python -m unittest discover -s collector/tests -p 'test_*.py' -t .
#   (requires PYTHONPATH=collector so engine/schema/output/scanner resolve)
#
# Or from collector directory (no PYTHONPATH needed):
#   cd collector && python -m unittest discover -s tests -p 'test_*.py'
#
# Optional: install pytest and run:
#   PYTHONPATH=collector python -m pytest collector/tests/ -v

from pathlib import Path
import sys

_collector_root = Path(__file__).resolve().parent.parent
if str(_collector_root) not in sys.path:
    sys.path.insert(0, str(_collector_root))
