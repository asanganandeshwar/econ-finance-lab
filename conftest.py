import sys
from pathlib import Path

ROOT = Path(__file__).parent
for sub in ("", "lbo-engine", "min-wage-did", "rockets-feathers"):
    sys.path.insert(0, str(ROOT / sub))
