#!/usr/bin/env python3
"""Build the Cairn console — one frame around every surface (RT-10, D48).

Runs whichever generators apply to this store, then writes an `index.html` that carries
the corpus's state above all of them. Panes with nothing to show say what is missing and
why, rather than being hidden — a stage that silently disappears is indistinguishable from
one that has no findings.

    python scripts/build_console.py --store corpus/store --audit audit_log/agent.jsonl \\
        --on 2026-07-28 --out console/

Opens with `open console/index.html`. No server; every page inside is self-contained and
still works on its own if opened directly.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

import _bootstrap  # noqa: F401  (puts src/ on sys.path)

from cairn.calibration import load as load_calibration
from cairn.console import ConsoleState, Pane, render
from cairn.contract import CONTRACT_VERSION
from cairn.ingest import DocumentStore
from cairn.locate_pane import render as locate_pane

ROOT = Path(__file__).resolve().parent.parent


def _run(script: str, args: list[str]) -> bool:
    """Run a generator. Returns whether it produced its page.

    Failures are reported and survived, not raised: a console missing one pane is far
    more useful than no console, and the pane will say what went wrong.
    """
    r = subprocess.run([sys.executable, str(ROOT / "scripts" / script), *args],
                       capture_output=True, text=True)
    if r.returncode != 0:
        first = (r.stderr or r.stdout).strip().splitlines()
        print(f"  ✗ {script}: {first[-1] if first else 'failed'}")
    return r.returncode == 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Build the Cairn console (RT-10)")
    ap.add_argument("--store", required=True)
    ap.add_argument("--audit", required=True)
    ap.add_argument("--doc", help="document id — enables the patent panes")
    ap.add_argument("--on", required=True, metavar="YYYY-MM-DD")
    ap.add_argument("--engagement")
    ap.add_argument("--out", default="console")
    ns = ap.parse_args()

    out = Path(ns.out)
    out.mkdir(parents=True, exist_ok=True)
    store_dir = Path(ns.store)
    doc_store = DocumentStore(store_dir)
    ids = doc_store.list_docs()

    print(f"building console for {len(ids)} document(s) → {out}/")

    # --from-audit takes the LOG PATH as its value; passing it as a bare flag silently
    # fell through to the demo path and its hardcoded EDGAR document.
    ok_evidence = _run("build_evidence_view.py",
                       ["--store", ns.store, "--from-audit", ns.audit,
                        "--out", str(out / "evidence.html")])
    ok_record = _run("build_review_report.py",
                     ["--store", ns.store, "--audit", ns.audit, "--on", ns.on,
                      *(["--engagement", ns.engagement] if ns.engagement else []),
                      "--out", str(out / "record.html")])
    ok_figures = False
    fig_dir = store_dir.parent / "figures"
    if ns.doc and (fig_dir / "ocr_manifest.json").exists():
        ok_figures = _run("patent_figures_view.py",
                          ["--store", ns.store, "--doc", ns.doc,
                           "--out", str(out / "figures.html")])

    # Adjudications and outstanding flags ride in the header, so they cannot scroll away.
    adjudications = 0
    adj_path = fig_dir / "adjudications.jsonl"
    if adj_path.exists():
        from cairn.adjudication import AdjudicationLog
        log = AdjudicationLog(adj_path)
        log.verify_chain()
        adjudications = len(log.effective())

    rec = load_calibration(store_dir)
    calibration = (
        f"Support floor {rec.threshold}, calibrated {rec.calibrated_on} against this "
        f"corpus ({rec.method}). Abstentions here are fitted to these documents."
        if rec else
        "This corpus has NO calibration record — the support floor was fitted elsewhere. "
        "A relevance score does not transfer between corpora, so abstentions here are "
        "unreliable and skew toward refusing questions the documents can in fact answer. "
        "Run scripts/calibrate_threshold.py --write.")

    panes = [
        Pane("corpus", "Corpus", "what are we searching?", None,
             "Corpus management has no page yet (RT-2). Documents, hashes and calibration "
             "state are summarised in the header above; adding and removing documents is "
             "still done with scripts/ingest_files.py."),
        Pane("locate", "Locate", "ask, and find or abstain", "locate.html",
             ""),
        Pane("evidence", "Evidence", "show the work and its limits",
             "evidence.html" if ok_evidence else None,
             "The evidence view could not be generated for this store."),
        Pane("figures", "Drawings", "located reference numerals",
             "figures.html" if ok_figures else None,
             "No OCR manifest for this store, so there are no drawing sheets to show. "
             "Run scripts/fetch_patent_figures.py then scripts/ocr_patent_figures.py, and "
             "pass --doc." if not ok_figures else ""),
        Pane("adjudicate", "Adjudicate", "the reviewer writes back", None,
             f"{adjudications} judgment(s) are on record and already folded into the "
             "Drawings pane. Recording them from inside the console — drawing a box on a "
             "sheet, correcting a reading — is RT-7b/c and not built; use "
             "scripts/adjudicate.py for now."),
        Pane("record", "Record", "the signable deliverable",
             "record.html" if ok_record else None,
             "The record of inquiry could not be generated for this store."),
    ]

    state = ConsoleState(
        engagement=ns.engagement or store_dir.parent.name,
        doc_ids=ids, calibration=calibration, calibrated=rec is not None,
        contract=CONTRACT_VERSION, adjudications=adjudications,
        generated_on=ns.on, panes=panes)

    # The Locate pane is static HTML that CALLS the real tools; it needs
    # scripts/serve_console.py running, and says so itself when it cannot reach one.
    (out / "locate.html").write_text(
        locate_pane(calibrated=rec is not None, calibration=calibration), encoding="utf-8")
    (out / "index.html").write_text(render(state), encoding="utf-8")
    built = [p.label for p in panes if p.page]
    print(f"\nOK — {out / 'index.html'}")
    print(f"  panes with content: {', '.join(built) or 'none'}")
    print(f"  placeholders      : {', '.join(p.label for p in panes if not p.page)}")
    print(f"  calibration       : {'recorded' if rec else 'ABSENT — stated in the header'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
