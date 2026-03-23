# Detec Collector — endpoint agent for agentic AI tool detection.
#
# Single path bootstrap so collector subpackages (config_loader, engine, scanner,
# etc.) are importable whether the package is run as "python -m collector.main",
# "detec-agent", or from tests. Prefer "pip install -e ." and "python -m collector.main"
# from repo root, or "detec-agent" after install; avoid "python main.py" from inside collector/.
from pathlib import Path
import sys

_COLLECTOR_ROOT = str(Path(__file__).resolve().parent)
if _COLLECTOR_ROOT not in sys.path:
    sys.path.insert(0, _COLLECTOR_ROOT)
