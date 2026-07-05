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
    CORRECTION,
    aggregate,
    brier_score,
    claims_and_spans,
    claude_ask,
    judge_entailment,
    judge_refutes_premise,
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
# Headless agent invocation. `--bare` forces ANTHROPIC_API_KEY auth (never the
# keychain/OAuth) so a CI/eval env authenticates by key; it also skips CLAUDE.md
# auto-discovery, so we re-add the repo (--add-dir, loads the loop) and a compact
# system prompt. The agent reaches ATTEST via a PER-RUN mcp config (written next
# to the audit log) whose env points at the requested store/threshold, so any
# engagement corpus can be evaluated — not just the default EDGAR store.
AGENT_SYSTEM = (
    "Answer the question ONLY using the attest MCP tools. Loop: search_corpus / "
    "check_support to locate; get_span / get_document to read; draft, binding every "
    "load-bearing figure to its exact span; call verify(answer) before presenting; "
    "abstain (structured refusal) if unsupported or if the text doesn't answer THIS "
    "question. If the question asks for a LEGAL CONCLUSION (validity, infringement, "
    "obviousness, claim construction, freedom-to-operate, enablement sufficiency), "
    "REFUSE TO ADJUDICATE: decline the conclusion, offer the located evidence, and "
    "do not call verify. End your reply with a line: Confidence: 0.NN"
)


def claude_flags(mcp_config: Path) -> list[str]:
    return [
        "--bare",
        "--add-dir", str(ROOT),
        "--mcp-config", str(mcp_config),
        "--permission-mode", "bypassPermissions",
        "--append-system-prompt", AGENT_SYSTEM,
        "--allowedTools", "mcp__attest__search_corpus,mcp__attest__get_span,"
        "mcp__attest__get_document,mcp__attest__check_support,mcp__attest__verify,"
        "mcp__attest__check_claim",
    ]


def write_mcp_config(path: Path, store: str, audit: Path, threshold: float | None) -> None:
    env = {"ATTEST_STORE": str(store), "ATTEST_AUDIT": str(audit)}
    if threshold is not None:
        env["ATTEST_SUPPORT_THRESHOLD"] = str(threshold)
    path.write_text(json.dumps({"mcpServers": {"attest": {
        "command": str(ROOT / ".venv" / "bin" / "python"),
        "args": ["-m", "attest.mcp_server"], "env": env,
    }}}, indent=2), encoding="utf-8")


def run_agent(question: str, flags: list[str], timeout: int = 360) -> subprocess.CompletedProcess:
    """One slow/hung item must not kill the run: a timeout comes back as a failed
    CompletedProcess and is scored as an errored item, not an exception."""
    try:
        return subprocess.run(  # noqa: S603
            ["claude", "-p", question, *flags], cwd=ROOT, capture_output=True,
            text=True, stdin=subprocess.DEVNULL, timeout=timeout
        )
    except subprocess.TimeoutExpired:
        return subprocess.CompletedProcess(
            args=["claude"], returncode=124, stdout="", stderr=f"timeout after {timeout}s"
        )


def main() -> int:
    ap = argparse.ArgumentParser(description="Layer-E: drive + score the agent over a golden set")
    ap.add_argument("--live", action="store_true", help="actually run the agent (BILLED)")
    ap.add_argument("--limit", type=int, default=0, help="only the first N items (0 = all)")
    ap.add_argument("--timestamp", default="", help="stamp for the trend record (caller-supplied)")
    ap.add_argument("--golden", default=str(ROOT / "golden_seed.json"))
    ap.add_argument("--store", default=str(ROOT / "corpus" / "store"))
    ap.add_argument("--threshold", type=float, default=None,
                    help="ATTEST_SUPPORT_THRESHOLD for the run (per-engagement floor, D20)")
    ap.add_argument("--audit-dir", default=str(ROOT / "audit_log"),
                    help="where the run's agent log, mcp config, and trend line go")
    ns = ap.parse_args()

    audit_dir = Path(ns.audit_dir)
    audit = audit_dir / "agent.jsonl"
    trend = audit_dir / "layer_e_results.jsonl"
    mcp_config = audit_dir / "run_mcp.json"

    items = json.loads(Path(ns.golden).read_text(encoding="utf-8"))["items"]
    if ns.limit:
        items = items[: ns.limit]

    if not ns.live:
        print("DRY RUN — would drive the agent over", len(items), "golden items")
        print(f"  golden={ns.golden}\n  store={ns.store}  threshold={ns.threshold}")
        print(f"  audit/trend under {audit_dir}")
        print("Re-run with --live to execute (billed, non-deterministic).")
        return 0

    audit_dir.mkdir(parents=True, exist_ok=True)
    audit.write_text("", encoding="utf-8")  # fresh log for this run
    write_mcp_config(mcp_config, ns.store, audit, ns.threshold)
    flags = claude_flags(mcp_config)
    log = AuditLog(audit)
    store = SpanStore.from_store(DocumentStore(ns.store))

    scores, entailed_items, calib, errored, refutations = [], [], [], [], []
    for item in items:
        before = len(log.entries())
        proc = run_agent(item["question"], flags)
        stdout = proc.stdout
        segment = [e.payload for e in log.entries()[before:]]

        # A process failure (auth/MCP breakage, timeout) is an ERROR, not an
        # abstention — surface it loudly instead of silently scoring
        # presented=False. But an agent that exited cleanly WITH prose and no tool
        # calls did run: e.g. an immediate refuse-to-adjudicate (D22) needs no
        # tools. That scores normally (no verify-ok → not presented).
        if proc.returncode != 0 or (not segment and not stdout.strip()):
            errored.append(item["id"])
            why = (stdout or proc.stderr or "(no output)").strip().splitlines()
            snip = (why[0] if why else "")[:80]
            print(f"  ⚠ {item['id']:<5} agent error / no output — {snip}")
            continue

        s = score_item(item, segment)
        scores.append(s)
        mark = "✓" if s.decision_correct else "✗"
        print(f"  {mark} {item['id']:<5} {s.expected:<10} presented={s.presented}")

        if s.presented:
            # entailment: LLM-judge each cited span against its claim (billed)
            payload = next(
                e for e in reversed(segment) if e.get("kind") == "verify" and e.get("ok")
            )
            pairs = list(claims_and_spans(payload, store.get_span))
            verdicts = [
                judge_entailment(claim, "\n".join(spans), claude_ask).yes
                for claim, spans in pairs
            ]
            item_ok = bool(verdicts) and all(verdicts)
            entailed_items.append(item_ok)
            # calibration: the agent's stated confidence vs whether it was right
            conf = parse_confidence(stdout)
            if conf is not None:
                calib.append((conf, item_ok))
            # grounded correction (D16): did it actually refute the false premise?
            if s.expected == CORRECTION:
                answer = " ".join(c for c, _ in pairs) or stdout
                refutations.append(judge_refutes_premise(item["question"], answer, claude_ask).yes)

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
        "correction_refute_rate": round(sum(refutations) / len(refutations), 4)
        if refutations else None,
        "n_errored": len(errored),
        "errored": errored,
    }
    with trend.open("a", encoding="utf-8") as f:
        f.write(json.dumps(summary) + "\n")
    print("\n" + json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
