#!/usr/bin/env python3
"""Print the corpus-fit inventory — step 0 of the corpus-fitting protocol (RT-6, D42).

Read this before pointing Cairn at a corpus it has never seen. The `falsifier` line on
each corpus-scoped entry names the observation that would show the value does not
transfer, so this listing IS the test plan for a new corpus.

    python scripts/corpus_fit_report.py            # the whole inventory
    python scripts/corpus_fit_report.py --scope corpus   # just what to re-measure
"""

from __future__ import annotations

import argparse
import textwrap

import _bootstrap  # noqa: F401  (puts src/ on sys.path)

from cairn.corpus_fit import CORPUS, FITTED, NOT_FITTED, drifted

BAR = "─" * 78


def _wrap(label: str, text: str) -> str:
    return textwrap.fill(f"{label} {text}", width=78,
                         initial_indent="    ", subsequent_indent="      ")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--scope", choices=["corpus", "domain", "universal"],
                    help="only constants of this scope")
    ns = ap.parse_args()

    rows = [c for c in FITTED if not ns.scope or c.scope == ns.scope]
    n_corpus = sum(1 for c in FITTED if c.scope == CORPUS)

    print(BAR)
    print("  Corpus-fit inventory — values that came from evidence, not from principle")
    print(f"  {len(FITTED)} registered · {n_corpus} corpus-specific "
          f"({n_corpus * 100 // len(FITTED)}%) · {len(NOT_FITTED)} exempt")
    print(BAR)

    drift = drifted()
    if drift:
        # Loudly, and before the listing: a stale registry makes everything below a lie.
        print("\n  ⚠ REGISTRY IS STALE — a value was retuned without updating its")
        print("    evidence, so the provenance below no longer describes the code:")
        for d in drift:
            print(f"      · {d}")

    for scope in ("corpus", "domain", "universal"):
        group = [c for c in rows if c.scope == scope]
        if not group:
            continue
        note = {
            "corpus": "measured on ONE corpus — re-measure before trusting elsewhere",
            "domain": "follows a documented domain convention; transfers within it",
            "universal": "follows from arithmetic or geometry, not from any corpus",
        }[scope]
        print(f"\n{BAR}\n  {scope.upper()} — {note}\n{BAR}")
        for c in group:
            print(f"\n  {c.name} = {c.value!r}" if c.value is not None
                  else f"\n  {c.name}  (provenance-only; open-ended set)")
            print(_wrap("fitted on:", c.fitted_on))
            print(_wrap("falsified by:", c.falsifier))

    print(f"\n{BAR}")
    print("  Protocol: docs/corpus_fitting.md   Enforcement: pytest -m layer0")
    print(BAR)
    return 1 if drift else 0


if __name__ == "__main__":
    raise SystemExit(main())
