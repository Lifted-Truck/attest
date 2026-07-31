#!/usr/bin/env python3
"""Record a reviewer's judgment into the append-only adjudication log (RT-7a, D47).

The durable input channel for the expert Cairn exists to support. Nothing here can edit
or delete a recorded judgment: a revision is a new entry naming what it supersedes, and
the earlier call stays in the record.

    # confirm a mark OCR cannot see
    python scripts/adjudicate.py --store corpus/engagements/US5447630A/store \\
        --id fig2-A --confirm --page 3 --numeral A --x 0.84 --y 0.19 \\
        --by "J. Smith" --on 2026-07-28 --note "visually confirmed on the sheet"

    # withdraw a mark the tool located that is not there
    python scripts/adjudicate.py … --id p2-99 --refute --page 2 --numeral 99 \\
        --x 0.50 --y 0.50 --by "J. Smith" --on 2026-07-28

    # revise an earlier call (the original REMAINS in the log)
    python scripts/adjudicate.py … --id fig2-A-v2 --correct --to 14a \\
        --supersedes fig2-A --page 3 --numeral 140 --x 0.84 --y 0.19 …

    python scripts/adjudicate.py --store … --list      # what is on record
    python scripts/adjudicate.py --store … --migrate --by "…" --on YYYY-MM-DD
"""

from __future__ import annotations

import argparse
from pathlib import Path

import _bootstrap  # noqa: F401  (puts src/ on sys.path)

from cairn.adjudication import (
    CONFIRM,
    CORRECT,
    NOTE,
    REFUTE,
    Adjudication,
    AdjudicationLog,
    import_legacy_sidecar,
)


def main() -> int:
    ap = argparse.ArgumentParser(description="Record a reviewer judgment (append-only)")
    ap.add_argument("--store", required=True)
    ap.add_argument("--id", help="stable id for this judgment (yours to choose)")
    kind = ap.add_mutually_exclusive_group()
    kind.add_argument("--confirm", action="store_true", help="this mark IS there")
    kind.add_argument("--refute", action="store_true", help="the tool located it; it is NOT there")
    kind.add_argument("--correct", action="store_true", help="the reading is wrong; see --to")
    kind.add_argument("--note", dest="is_note", action="store_true", help="reasoning only")
    ap.add_argument("--page", type=int)
    ap.add_argument("--numeral")
    ap.add_argument("--x", type=float)
    ap.add_argument("--y", type=float)
    ap.add_argument("--w", type=float, default=0.02)
    ap.add_argument("--h", type=float, default=0.02)
    ap.add_argument("--to", help="the corrected label, for --correct")
    ap.add_argument("--by", help="who is recording this — provenance is not optional")
    ap.add_argument("--on", metavar="YYYY-MM-DD", help="date, supplied (no clock — I6)")
    ap.add_argument("--text", default="", help="note text")
    ap.add_argument("--supersedes", help="adj_id this revises; that entry REMAINS")
    ap.add_argument("--list", action="store_true", help="show the record and exit")
    ap.add_argument("--migrate", action="store_true",
                    help="import the legacy manual_annotations.json (read-only)")
    ns = ap.parse_args()

    fig_dir = Path(ns.store).parent / "figures"
    log = AdjudicationLog(fig_dir / "adjudications.jsonl")

    if ns.list:
        if not log.path.exists():
            print(f"no adjudications recorded at {log.path}")
            return 0
        log.verify_chain()
        live = {a.adj_id for a in log.effective()}
        print(f"{log.path}  (chain verified)")
        for a in log.all():
            mark = " " if a.adj_id in live else "×"   # × = superseded, still on record
            sup = f"  supersedes {a.supersedes}" if a.supersedes else ""
            print(f"  {mark} {a.adj_id:<16} {a.kind:<8} {a.target} by {a.by} on {a.on}{sup}")
        return 0

    if ns.migrate:
        if not ns.by or not ns.on:
            print("--migrate needs --by and --on: migrated entries still need provenance")
            return 1
        got = import_legacy_sidecar(fig_dir / "manual_annotations.json", by=ns.by, on=ns.on)
        if not got:
            print("nothing to migrate — the legacy file is absent or empty.")
            print("NOTE: an empty legacy file is not proof nothing was ever confirmed. "
                  "It kept no history, so anything it once held is unrecoverable and "
                  "must be re-recorded by the person who saw it.")
            return 0
        for a in got:
            log.append(a)
        print(f"migrated {len(got)} judgment(s) into {log.path}")
        return 0

    for req in ("id", "by", "on"):
        if not getattr(ns, req):
            print(f"--{req} is required (provenance is not optional)")
            return 1

    k = (CONFIRM if ns.confirm else REFUTE if ns.refute
         else CORRECT if ns.correct else NOTE if ns.is_note else None)
    if k is None:
        print("choose one of --confirm / --refute / --correct / --note")
        return 1
    if k == CORRECT and not ns.to:
        print("--correct needs --to <corrected label>")
        return 1

    target = {kk: vv for kk, vv in
              (("page", ns.page), ("numeral", ns.numeral), ("x", ns.x), ("y", ns.y),
               ("w", ns.w), ("h", ns.h)) if vv is not None}
    value = ({"numeral": ns.to, "x": ns.x, "y": ns.y, "w": ns.w, "h": ns.h}
             if k == CORRECT else {})

    log.append(Adjudication(adj_id=ns.id, kind=k, target_kind="figure-numeral",
                            target=target, by=ns.by, on=ns.on, note=ns.text,
                            value=value, supersedes=ns.supersedes))
    print(f"recorded {ns.id} ({k}) in {log.path}")
    print(f"  {len(log.all())} judgment(s) on record, {len(log.effective())} in force")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
