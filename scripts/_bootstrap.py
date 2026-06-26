"""Put `src/` on sys.path so `python scripts/<name>.py` works from a fresh checkout
without `pip install -e .` (the package lives under src/, a src-layout repo).

Each script imports this first: `import _bootstrap  # noqa: F401`.
"""

import sys
from pathlib import Path

_SRC = Path(__file__).resolve().parent.parent / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))
