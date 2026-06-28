# Layer-E baseline — first live agent pass

First end-to-end run of the **real Claude Code agent** over the 20-item golden set
through the ATTEST MCP tools (`scripts/run_layer_e.py --live`). Layer-E is
**periodic, not a blocking gate** (brief §3) and **non-deterministic** — these
numbers are a snapshot, not an oracle.

- **Date:** 2026-06-28
- **Agent:** headless `claude -p --bare` (Sonnet), tools via `.mcp.json`
- **Judge:** `claude -p --bare` entailment verdict per cited span
- **Cost:** ~$3 API (≈ $0.14/agent item, Sonnet + prompt caching)

## Headline

| Metric | Value | Reading |
|---|---|---|
| `abstention_accuracy` (unanswerable) | 6/7 = 0.857 | one is a scorer artifact (see G020) → effectively 7/7 |
| `answer_rate` (answerable) | 12/13 = 0.923 | one real miss (G008) |
| `abstention_correct_overall` | 18/20 = 0.90 | 19/20 once G020 is credited |
| `verify_catches` | 21 | ungrounded drafts `verify` rejected before presenting — it is doing real work |
| `entailment_rate` (presented) | 9/13 = 0.692 | mix of real over-claims + judge strictness; offline signal |
| `brier` / calibration | 0.296 | **overconfident** — stated mean 0.98 vs 0.69 actual on the top bucket |
| errored | 0/20 | every item ran the loop |

## The two flagged items

- **G008 — real miss.** "How much does Apple hold in marketable securities?"
  `check_support` returned **supported** (score 19.7), so the evidence was there,
  but the agent **abstained** instead of giving the plural answer (current
  $35,228M + non-current $91,479M). Under-answered a plural question.

- **G020 — scorer false-negative, not an agent miss.** "Why did Apple's total
  assets *decline* in fiscal 2024?" (false premise). The agent **correctly
  rejected** it with grounded evidence: "total assets did **not** decline; they
  increased from $352,583M to $364,980M." That is exactly right, but the scorer's
  `presented == answerable` rule cannot distinguish a *grounded rejection* from
  *answering a question it should refuse*, so it counts as wrong.

## Follow-ups this surfaced

1. **Scorer refinement (reject-false-premise).** Credit a grounded rejection of a
   false premise as correct — likely judge-assisted ("does the presented answer
   affirm or reject the premise?"). Needs a Decisions-log `D#`.
2. **G008 / plural answers.** The agent abstains when it should surface multiple
   ranked values; tighten the loop guidance toward plural-and-ranked (brief §4).
3. **Calibration / judge.** Agent is overconfident (0.98 → 0.69); and some
   `entailment=NO` verdicts are the agent over-claiming beyond its cited spans.
   Worth separating "agent over-claim" from "judge too strict" on the 4 misses.
