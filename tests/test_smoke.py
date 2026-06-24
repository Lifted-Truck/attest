"""Smoke test for the M0-T1 scaffold.

AC for M0-T1: a clean install runs an empty test suite green. This is the
"empty" suite — it confirms the package imports and the harness is wired.
Real Layer-0 deterministic component evals (brief §3) arrive at M2.
"""

import attest


def test_package_imports():
    assert attest.__version__ == "0.1.0"
