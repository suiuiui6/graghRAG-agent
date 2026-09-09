from pathlib import Path
import sys


BACKEND_ROOT = str(Path(__file__).resolve().parents[1])
if sys.path[0] != BACKEND_ROOT:
    sys.path.insert(0, BACKEND_ROOT)
