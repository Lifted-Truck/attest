"""Integrity checks for the M0 toy corpus (ROADMAP M0-T2).

Not an invariant test yet (I3 hashing lands at M1), but it foreshadows it: the
committed excerpts must match the sha256 recorded in the manifest, and the
balance-sheet excerpt must still carry the figures the answerable golden items
depend on. If an excerpt drifts, this fails — the same discipline I3 formalizes.
"""

import hashlib
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
MANIFEST = ROOT / "corpus" / "toy" / "manifest.json"


@pytest.fixture(scope="module")
def manifest():
    if not MANIFEST.exists():
        pytest.skip("toy corpus not built — run scripts/build_toy_corpus.py")
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


def test_provenance_recorded(manifest):
    src = manifest["source"]
    for field in ("ticker", "form", "accession", "cik", "period_of_report", "primary_url"):
        assert src.get(field), f"missing provenance field: {field}"
    assert src["form"] == "10-K"
    assert src["ticker"] == "AAPL"


def test_excerpts_present_and_hash_matches(manifest):
    assert manifest["excerpt_count"] == len(manifest["excerpts"]) >= 5
    for ex in manifest["excerpts"]:
        path = ROOT / ex["path"]
        assert path.exists(), f"missing excerpt file: {ex['path']}"
        body = path.read_bytes()
        assert hashlib.sha256(body).hexdigest() == ex["sha256"], f"hash drift: {ex['excerpt_id']}"
        assert len(body.decode("utf-8")) == ex["char_len"]


# Figures the answerable golden items rest on must survive verbatim in the corpus.
ANSWERABLE_FIGURES = [
    "364,980", "352,583", "176,392", "9,967", "45,680", "78,304",
    "58,829", "14,287", "8,249", "10,912", "9,822", "85,750", "91,479",
    "For the fiscal year ended September 28, 2024", "Ernst & Young LLP",
]


def test_golden_figures_resolve_in_corpus(manifest):
    blob = "\n".join((ROOT / ex["path"]).read_text(encoding="utf-8") for ex in manifest["excerpts"])
    missing = [s for s in ANSWERABLE_FIGURES if s not in blob]
    assert not missing, f"answerable golden evidence missing from corpus: {missing}"
