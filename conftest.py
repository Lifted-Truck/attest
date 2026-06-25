"""Make repo-root modules (e.g. attest_rig) importable from tests.

pytest adds the directory containing this conftest to sys.path, so tests can
`import attest_rig` even though it lives at the repo root rather than in src/.
"""

from pathlib import Path


def pytest_collection_modifyitems(items):
    """Tag everything under tests/ as the Layer-0 deterministic gate (docs/layer0_gate.md).

    Keeps the gate selectable as `pytest -m layer0` without per-file marks. The
    periodic Layer-E evals live outside tests/ and are not auto-tagged.
    """
    for item in items:
        if "tests" in Path(str(item.fspath)).parts:
            item.add_marker("layer0")

