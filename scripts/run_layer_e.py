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

The entailment judge (LLM-as-judge over the cited spans) and abstention
calibration (Brier) are the remaining Layer-E pieces; they are also model steps
and slot in beside the deterministic scoring here.
"""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

import _bootstrap  # noqa: F401  (puts src/ on sys.path)

from attest.audit import AuditLog
from attest.layer_e import aggregate, score_item

ROOT = Path(__file__).resolve().parent.parent
GOLDEN = ROOT / "golden_seed.json"
AUDIT = ROOT / "audit_log" / "agent.jsonl"
TREND = ROOT / "audit_log" / "layer_e_results.jsonl"

# Headless agent invocation. The agent reads the project CLAUDE.md (the runtime
# loop) and reaches ATTEST via .mcp.json; tools are auto-approved for the run.
CLAUDE_CMD = [
    "claude", "-p",
    "--mcp-config", str(ROOT / ".mcp.json"),
    "--allowedTools", "mcp__attest__search_corpus,mcp__attest__get_span,"
    "mcp__attest__get_document,mcp__attest__check_support,mcp__attest__verify,"
    "mcp__attest__check_claim",
]


def run_agent(question: str, timeout: int = 180) -> str:
    proc = subprocess.run(  # noqa: S603
        [*CLAUDE_CMD, question], cwd=ROOT, capture_output=True, text=True, timeout=timeout
    )
    return proc.stdout


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
        print("  " + " ".join(CLAUDE_CMD) + ' "<question>"')
        print("\nRe-run with --live to execute (billed, non-deterministic). Scoring reads")
        print(f"the audit log ({AUDIT.relative_to(ROOT)}) and writes a trend to "
              f"{TREND.relative_to(ROOT)}.")
        return 0

    AUDIT.parent.mkdir(parents=True, exist_ok=True)
    AUDIT.write_text("", encoding="utf-8")  # fresh log for this run
    log = AuditLog(AUDIT)

    scores = []
    for item in items:
        before = len(log.entries())
        run_agent(item["question"])
        segment = [e.payload for e in log.entries()[before:]]
        s = score_item(item, segment)
        scores.append(s)
        mark = "✓" if s.abstention_correct else "✗"
        print(f"  {mark} {item['id']:<5} presented={s.presented}  (answerable={s.answerable})")

    summary = {"timestamp": ns.timestamp, **aggregate(scores)}
    TREND.parent.mkdir(parents=True, exist_ok=True)
    with TREND.open("a", encoding="utf-8") as f:
        f.write(json.dumps(summary) + "\n")
    print("\n" + json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
