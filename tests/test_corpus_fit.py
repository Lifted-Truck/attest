"""Standing tests for the corpus-fit registry (RT-6, D42).

These are the enforcement half of the corpus-fitting protocol. The prose half lives in
`docs/corpus_fitting.md`; per L0010, a lesson recorded only in prose gets re-learned, so
the rules that CAN be mechanized are mechanized here.
"""

from __future__ import annotations

import ast
import pathlib

import pytest

from cairn.corpus_fit import CORPUS, FITTED, NOT_FITTED, by_scope, drifted, live_value

pytestmark = pytest.mark.layer0

ROOT = pathlib.Path(__file__).resolve().parents[1]

# Modules holding values fitted to a particular corpus. A new tunable here must be
# registered or explicitly exempted — that is what makes provenance enforceable.
FITTED_MODULES = {
    "patents": "src/cairn/patents.py",
    "figures_map": "src/cairn/figures_map.py",
    "cues": "src/cairn/cues.py",
    "support": "src/cairn/support.py",
    "ocr_patent_figures": "scripts/ocr_patent_figures.py",
}


def test_registry_matches_the_code():
    """A constant retuned without updating its recorded evidence fails here.

    This is the point of the registry: the danger is not a wrong value, it is a value
    whose justification no longer describes it. A scalar that moves silently has quietly
    become a law nobody can date."""
    assert drifted() == []


def test_every_registered_constant_resolves():
    """The registry names things by dotted path, including function keyword defaults —
    several fitted values ARE kwarg defaults, which is how they escaped notice as
    constants in the first place. A rename must break this, not rot silently."""
    for c in FITTED:
        live_value(c)          # raises if the name no longer resolves


def test_every_fitted_constant_records_evidence_and_a_falsifier():
    """Provenance without a falsifier is a story. The falsifier is the operative field:
    it tells the next agent what observation would prove the value does not transfer."""
    for c in FITTED:
        assert len(c.fitted_on) > 40, f"{c.name}: evidence too thin to act on"
        assert len(c.falsifier) > 30, f"{c.name}: no usable falsifier"
        assert c.scope in ("corpus", "domain", "universal"), c.name


def _module_tunables(rel: str) -> list[str]:
    """Module-level names bound to a literal value — the shape a tunable takes.

    AST rather than import, so this sees what a reader greps for and cannot be fooled by
    a value computed at import time."""
    tree = ast.parse((ROOT / rel).read_text(encoding="utf-8"))
    out = []
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        for tgt in node.targets:
            if not isinstance(tgt, ast.Name) or not tgt.id.lstrip("_")[:1].isupper():
                continue
            v = node.value
            is_literal_collection = isinstance(v, (ast.Tuple, ast.Set, ast.Dict, ast.List))
            is_number = isinstance(v, ast.Constant) and isinstance(v.value, (int, float))
            is_frozenset = (isinstance(v, ast.Call)
                            and getattr(v.func, "id", "") == "frozenset")
            if is_literal_collection or is_number or is_frozenset:
                out.append(tgt.id)
    return out


def test_no_unaccounted_tunable_in_a_fitted_module():
    """The teeth: adding a tunable to a fitted module without recording where its value
    came from fails the gate.

    Every constant in this repo was fitted to ONE 1995 patent or ONE 10-K, and every one
    was discovered by a human noticing a miss. A constant with no recorded provenance is
    indistinguishable from a law — so the registry is not allowed to fall behind the code.
    To fix a failure: add a FittedConstant with its evidence and falsifier, or add it to
    NOT_FITTED with a reason."""
    registered = {c.name.partition("(")[0] for c in FITTED}
    unaccounted = []
    for mod, rel in FITTED_MODULES.items():
        for name in _module_tunables(rel):
            dotted = f"{mod}.{name}"
            if dotted not in registered and dotted not in NOT_FITTED:
                unaccounted.append(dotted)
    assert not unaccounted, (
        "unaccounted tunables — register in corpus_fit.FITTED with evidence + a "
        f"falsifier, or exempt in NOT_FITTED with a reason: {unaccounted}")


def test_exemptions_carry_a_reason():
    for name, reason in NOT_FITTED.items():
        assert len(reason) > 25, f"{name}: exemption needs a real reason"


def test_the_corpus_specific_majority_is_visible():
    """Not a behavioural assertion — a standing reminder with a number attached. Most
    tunables on the evidence path are corpus-fitted, which is the fact a second-corpus
    run has to plan around rather than discover."""
    assert len(by_scope(CORPUS)) >= len(FITTED) // 2
