#!/usr/bin/env python3
"""Layer-E runner — drive the real Claude Code agent over the golden set (M2-T6).

For each golden item it (optionally) invokes **headless Claude Code** with the
ATTEST MCP server (`.mcp.json`), so the agent answers through the tools and its
calls are logged (I5). It then scores each item's log segment with the
deterministic Layer-E scorer (`attest.layer_e`) and writes a results-trend line.

Layer-E is **periodic, not a blocking gate** (brief §3), and the live run is
**billed + non-deterministic**, so it is opt-in:

    python scripts/run_layer_e.py                 # DRY: print the plan + the claude command
    python scripts/run_layer_e.py --live          # BILLED: actually run the agent + score
    python scripts/run_layer_e.py --live --limit 1   # smoke one item

In `--live` it also runs the **entailment judge** (LLM-as-judge over each cited
span, billed) and **calibration** (Brier + reliability over the agent's stated
`Confidence: 0.NN` vs whether the answer entailed). So one live pass yields the
full metric set: abstention accuracy, entailment rate, and calibration.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path

import _bootstrap  # noqa: F401  (puts src/ on sys.path)

from attest.audit import AuditLog
from attest.ingest import DocumentStore
from attest.layer_e import (
    aggregate,
    brier_score,
    claims_and_spans,
    claude_ask,
    judge_entailment,
    reliability,
    score_item,
)
from attest.spans import SpanStore

_CONF = re.compile(r"confidence[:\s]+(0?\.\d+|1(?:\.0+)?|0)", re.IGNORECASE)


def parse_confidence(text: str) -> float | None:
    """The agent ends its answer with 'Confidence: 0.NN' (documented convention)."""
    m = _CONF.search(text or "")
    return float(m.group(1)) if m else None

ROOT = Path(__file__).resolve().parent.parent
GOLDEN = ROOT / "golden_seed.json"
AUDIT = ROOT / "audit_log" / "agent.jsonl"
TREND = ROOT / "audit_log" / "layer_e_results.jsonl"

# Headless agent invocation. The agent reads the project CLAUDE.md (the runtime
# loop) and reaches ATTEST via .mcp.json; tools are auto-approved for the run.
# The prompt is the value of -p; flags follow.
CLAUDE_FLAGS = [
    "--mcp-config", str(ROOT / ".mcp.json"),
    "--permission-mode", "bypassPermissions",
    "--allowedTools", "mcp__attest__search_corpus,mcp__attest__get_span,"
    "mcp__attest__get_document,mcp__attest__check_support,mcp__attest__verify,"
    "mcp__attest__check_claim",
]


def run_agent(question: str, timeout: int = 180) -> subprocess.CompletedProcess:
    return subprocess.run(  # noqa: S603
        ["claude", "-p", question, *CLAUDE_FLAGS], cwd=ROOT, capture_output=True,
        text=True, stdin=subprocess.DEVNULL, timeout=timeout
    )


def main() -> int:
    ap = argparse.ArgumentParser(description="Layer-E: drive + score the agent over the golden set")
    ap.add_argument("--live", action="store_true", help="actually run the agent (BILLED)")
    ap.add_argument("--limit", type=int, default=0, help="only the first N items (0 = all)")
    ap.add_argument("--timestamp", default="", help="stamp for the trend record (caller-supplied)")
    ns = ap.parse_args()

    items = json.loads(GOLDEN.read_text(encoding="utf-8"))["items"]
    if ns.limit:
        items = items[: ns.limit]

    if not ns.live:
        print("DRY RUN — would drive the agent over", len(items), "golden items.")
        print("per-item command:")
        print('  claude -p "<question>" ' + " ".join(CLAUDE_FLAGS))
        print("\nRe-run with --live to execute (billed, non-deterministic). Scoring reads")
        print(f"the audit log ({AUDIT.relative_to(ROOT)}) and writes a trend to "
              f"{TREND.relative_to(ROOT)}.")
        return 0

    AUDIT.parent.mkdir(parents=True, exist_ok=True)
    AUDIT.write_text("", encoding="utf-8")  # fresh log for this run
    log = AuditLog(AUDIT)
    store = SpanStore.from_store(DocumentStore(ROOT / "corpus" / "store"))

    scores, entailed_items, calib, errored = [], [], [], []
    for item in items:
        before = len(log.entries())
        proc = run_agent(item["question"])
        stdout = proc.stdout
        segment = [e.payload for e in log.entries()[before:]]

        # An agent that called NO tools didn't actually run the loop (auth/MCP
        # failure, refusal to use tools). That is an ERROR, not an abstention —
        # surface it loudly instead of silently scoring presented=False.
        if proc.returncode != 0 or not segment:
            errored.append(item["id"])
            why = (stdout or proc.stderr or "(no output)").strip().splitlines()
            snip = (why[0] if why else "")[:80]
            print(f"  ⚠ {item['id']:<5} agent error / no tool calls — {snip}")
            continue

        s = score_item(item, segment)
        scores.append(s)
        mark = "✓" if s.abstention_correct else "✗"
        print(f"  {mark} {item['id']:<5} presented={s.presented}  (answerable={s.answerable})")

        if s.presented:
            # entailment: LLM-judge each cited span against its claim (billed)
            payload = next(
                e for e in reversed(segment) if e.get("kind") == "verify" and e.get("ok")
            )
            verdicts = [
                judge_entailment(claim, "\n".join(spans), claude_ask).entails
                for claim, spans in claims_and_spans(payload, store.get_span)
            ]
            item_ok = bool(verdicts) and all(verdicts)
            entailed_items.append(item_ok)
            # calibration: the agent's stated confidence vs whether it was right
            conf = parse_confidence(stdout)
            if conf is not None:
                calib.append((conf, item_ok))

    if not scores:
        print("\nNo items scored — the agent produced no tool calls on any item.")
        print("Check headless Claude Code: a 401 means the spawned `claude -p` is not")
        print("authenticated (set ANTHROPIC_API_KEY or run in an authenticated env), and")
        print("confirm the ATTEST MCP server starts (.venv has attest + mcp installed).")
        return 1

    summary = {
        "timestamp": ns.timestamp,
        **aggregate(scores),
        "entailment_rate": round(sum(entailed_items) / len(entailed_items), 4)
        if entailed_items else None,
        "brier": brier_score(calib),
        "reliability": reliability(calib),
        "n_calibrated": len(calib),
        "n_errored": len(errored),
        "errored": errored,
    }
    TREND.parent.mkdir(parents=True, exist_ok=True)
    with TREND.open("a", encoding="utf-8") as f:
        f.write(json.dumps(summary) + "\n")
    print("\n" + json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
