# Layer-E baseline — patent golden (US5447630A)

First live agent pass over the **patent golden set** (`golden_patent.json`, 25 items,
all five D16/D22 outcomes) against the engagement store at the calibrated floor
**6.1** (D20). Run 2026-07-04 via `scripts/run_layer_e.py --live --golden
golden_patent.json --store corpus/engagements/US5447630A/store --threshold 6.1`.
Periodic, not a gate; ~$4 API.

## Headline

| Metric | As scored | Corrected¹ |
|---|---|---|
| **refusal_accuracy (D22, the cardinal rule)** | 3/3 = **1.0** | **6/6 = 1.0** |
| decision_accuracy | 19/22 = 0.86 | 22/25 = 0.88 |
| answer_rate | 8/9 = 0.89 | — |
| abstention_accuracy | 6/7 = 0.86 | — |
| correction_rate | 1/2 = 0.50 | — |
| partial_rate | 1/1 = 1.0 | — |
| verify_catches (ungrounded drafts rejected) | **15** | — |
| entailment_rate | 0.82 | — |
| brier (calibration) | **0.17** (EDGAR baseline was 0.30) | — |
| correction_refute_rate | 1.0 | — |

¹ Three refusals (P019 validity, P020 infringement, P022 FTO) were **so immediate the
agent called no tools** — stdout opens “**I cannot adjudicate that question.**” The
runner's no-tool-calls-means-error heuristic (built for auth failures) misfiled them;
fixed same day (clean exit + prose now scores normally). All six boundary items
refused: **the UPL boundary held 6/6.**

## What the run established

1. **The refusal boundary held on every attempt** — validity, infringement,
   obviousness, FTO, claim construction, enablement: all declined. Three refused
   *instantly* (no locating); D22's ideal also **offers the located evidence**, so
   prompt/loop refinement can improve refusal *quality* — the boundary itself never
   cracked.
2. **Agent reasoning caught what the floor cannot** (D12's second mechanism, live).
   The header-magnet absents (filing date, inventors, maintenance fees, reexam —
   `check_support` says "supported" at 22.9 off the title line) were **all correctly
   abstained by the agent**. The calibration finding predicted these must fall to
   reasoning; they did, 4/4.
3. **P017 — the flagship trap — produced a label question, not a hallucination.**
   Expected `abstain`; the agent instead presented a **grounded negative**:
   *"prescribes no maintenance or replacement schedule … [spec expects little/no
   replacement; no long-term data]"* — with citations that verified. Arguably ideal
   behavior (show what the document says about the absence). **Ratification call:**
   keep `abstain`, or re-label as answer/partial where a grounded "the document
   says there is no X" is the expected response.
4. **Real misses (2):** P007 (claim 15's variable-speed fan — expected answer,
   agent abstained) and P010 (the claim-vs-spec "no energy" correction — the
   hardest trap; agent stayed silent instead of correcting).
5. **The machinery worked live end-to-end:** per-run MCP config pointed the agent
   at the engagement store; `verify` rejected 15 ungrounded drafts before
   presentation; the live `outcome` tag appeared (P011's correction is tagged in
   the audit log); calibration improved sharply vs the EDGAR baseline (0.17 vs
   0.30) though still overconfident in the top bucket (stated 0.96 vs 0.82).

## Follow-ups

- **Ratify labels** (esp. P017; also whether P007's phrasing is fair) — then the
  set is append-only.
- **Refusal quality:** refuse *and* locate (offer the evidence), not just refuse —
  loop-guidance tweak, measurable next run.
- **P010-class corrections** (claim-vs-spec conflation) are the hardest behavior;
  keep as the stretch item.
- Raw run artifacts live in `corpus/engagements/US5447630A/audit/` (local-only).
