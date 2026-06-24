"""Make repo-root modules (e.g. attest_rig) importable from tests.

pytest adds the directory containing this conftest to sys.path, so tests can
`import attest_rig` even though it lives at the repo root rather than in src/.
"""
