#!/usr/bin/env python3
"""Bind the golden set's verbatim quotes to the canonical text (ROADMAP M1-T2, D7).

The golden seed ships `verbatim_quote: null` by design — the exact span text can
only be pulled once M1 defines canonical normalization. This binder fills each
quote from the canonical document and enforces the **resolution invariant**:
every quote must resolve to exactly one location, or it hard-fails.

Idempotent: re-running sets the same quotes and re-validates. The standing guard
is `tests/test_spans.py`; this script is how the quotes were derived, kept for
provenance. It edits the seed as text to preserve its formatting.

Usage:  python scripts/resolve_golden_quotes.py
"""

from __future__ import annotations

import json
from pathlib import Path

from attest.ingest import DocumentStore
from attest.spans import SpanStore

ROOT = Path(__file__).resolve().parent.parent
SEED = ROOT / "golden_seed.json"
DOC_ID = "AAPL-10K-FY2024"

# A unique locator substring → the exact canonical line that supports it.
QUOTES = {
    "'Total assets' line · FY2024 column": "Total assets $ 364,980 $ 352,583",
    "'Commercial paper' · FY2024 column": "Commercial paper 9,967 5,985",
    "'Property, plant and equipment, net' · FY2024 column":
        "Property, plant and equipment, net 45,680 43,715",
    "'Total current liabilities' · FY2024 column": "Total current liabilities 176,392 145,308",
    "'Total assets' · FY2024 column": "Total assets $ 364,980 $ 352,583",
    "'Total assets' · FY2023 column": "Total assets $ 364,980 $ 352,583",
    "'Other current liabilities' · FY2024 column": "Other current liabilities 78,304 58,829",
    "'Other current liabilities' · FY2023 column": "Other current liabilities 78,304 58,829",
    "'Term debt' (current liabilities section) · FY2024 column": "Term debt 10,912 9,822",
    "'Term debt' (non-current liabilities section) · FY2024 column": "Term debt 85,750 95,281",
    "'Marketable securities' (current assets) · FY2024 column":
        "Marketable securities 35,228 31,590",
    "'Marketable securities' (non-current assets) · FY2024 column":
        "Marketable securities 91,479 100,544",
    "cover / period of report": "For the fiscal year ended September 28, 2024",
    "'Other current assets' · FY2024 column": "Other current assets 14,287 14,695",
    "'Deferred revenue' (current liabilities) · FY2024 column": "Deferred revenue 8,249 8,061",
    "'Term debt' (current) · FY2024 column": "Term debt 10,912 9,822",
    "'Term debt' (current) · FY2023 column": "Term debt 10,912 9,822",
    "'Total assets' · FY2024 and FY2023 columns": "Total assets $ 364,980 $ 352,583",
}


def _entry(locator: str, quote: str, value_seen: str) -> str:
    return (
        f'{{ "locator": "{locator}", "verbatim_quote": {json.dumps(quote)}, '
        f'"value_seen": "{value_seen}", "source_status": "grounded" }}'
    )


# G016 lumps two non-contiguous lines into one entry; split it so each carries
# one resolvable quote (mirrors G007).
_BS = "AAPL-10K-FY2024 · Consolidated Balance Sheets"
G016_OLD = (
    f'{{ "locator": "{_BS} · term debt lines (Apple portion only)", '
    '"verbatim_quote": null, '
    '"value_seen": "Apple term debt: $10,912M current + $85,750M non-current", '
    '"source_status": "fetched_value_quote_to_resolve" }'
)
G016_NEW = (
    _entry(f"{_BS} · 'Term debt' (current) · FY2024 column", "Term debt 10,912 9,822",
           "$10,912 million (current)")
    + ",\n        "
    + _entry(f"{_BS} · 'Term debt' (non-current) · FY2024 column", "Term debt 85,750 95,281",
             "$85,750 million (non-current)")
)


def main() -> int:
    store = SpanStore.from_store(DocumentStore(ROOT / "corpus" / "store"))
    canonical = store._docs[DOC_ID].canonical_text

    # G009 needs context to be unique ("Ernst & Young LLP" appears 4×): the signature
    # plus the tenure line that follows only the financial-statements report.
    tenure = next(
        ln for ln in canonical.splitlines() if ln.startswith("We have served as the Company")
    )
    g009_quote = f"/s/ Ernst & Young LLP\n\n{tenure}"
    assert canonical.count(g009_quote) == 1, "G009 quote not unique"

    text = SEED.read_text(encoding="utf-8")

    def fill(locator_key: str, quote: str) -> None:
        nonlocal text
        anchors = [
            ln for ln in text.splitlines()
            if locator_key in ln and '"verbatim_quote": null' in ln
        ]
        if not anchors:
            return  # already filled (idempotent)
        assert len(anchors) == 1, f"locator key not unique: {locator_key!r}"
        filled = anchors[0].replace(
            '"verbatim_quote": null', f'"verbatim_quote": {json.dumps(quote)}'
        )
        text = text.replace(anchors[0], filled)

    for key, quote in QUOTES.items():
        fill(key, quote)
    fill("(signature/firm name)", g009_quote)
    if G016_OLD in text:
        text = text.replace(G016_OLD, G016_NEW)
    text = text.replace(
        '"source_status": "fetched_value_quote_to_resolve"', '"source_status": "grounded"'
    )

    data = json.loads(text)  # validates JSON
    SEED.write_text(text, encoding="utf-8")

    bound = unresolved = 0
    for item in data["items"]:
        for s in item.get("supporting", []):
            q = s.get("verbatim_quote")
            if not q:
                continue
            try:
                start, end = store.resolve_quote(DOC_ID, q)
                bound += 1
                print(f"  {item['id']:<5} ✓ @{start}-{end}  {q[:46]!r}")
            except Exception as e:  # noqa: BLE001
                unresolved += 1
                print(f"  {item['id']:<5} ✗ {e}")
    status = "OK" if not unresolved else "FAIL"
    print(f"\n{status} — {bound} quotes bound 1:1, {unresolved} unresolved")
    return 1 if unresolved else 0


if __name__ == "__main__":
    raise SystemExit(main())
