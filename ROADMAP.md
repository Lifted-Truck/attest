# ATTEST — ROADMAP

**This file is the single source of truth for status and sequencing.** Architecture, invariants, and rationale live in `ATTEST_build_brief.md`; this file references it by `§` rather than duplicating it. When the two disagree, the brief wins on *design* and this file wins on *what to do next*.

**Cardinal rule:** Ground or abstain — never invent. (Invariants I1–I6: see brief §0.)

### Status legend
`TODO` · `WIP` · `BLOCKED` · `DONE` — task checkboxes mirror this (`- [ ]` / `- [x]`).

### ▶ Current focus
**M0 · M0-T1** — repo scaffold. Nothing else is started until M0 clears its gate.

---

## How the agent uses this file

1. Read **Current focus**. Take the topmost unchecked task in that milestone.
2. Branch per the task's `branch:` field. Implement to the task's **acceptance criteria (AC)**.
3. Open a PR. The **Layer-0 deterministic component evals (brief §3)** run as required CI. **No merge on a red gate or a violated invariant (I1–I6).** (Layer-E agent evals run periodically, not per-PR.)
4. On green: merge, check the box, append a line to the **Changelog**, and advance **Current focus** to the next task.
5. A milestone is `DONE` only when its **Gate** passes. Do not begin the next milestone until then.
6. Never start anything under **Backlog (v2)**. If a v1 task tempts you toward esoterica, see brief §9 (the trap): ambition goes into the oracle, nowhere else.

---

## Working agreements

- **Branch naming:** `feat/<milestone>-<slug>`, `fix/…`, `chore/…`. One subsystem per branch.
- **PR rules:** small, single-purpose, oracle-gated. Every PR states which invariants it touches and how its tests cover them.
- **Invariant tests are CI, not afterthoughts.** I3/I4/I5/I6 each have a standing test that runs on every PR once introduced (M1 onward).
- **Determinism:** anything on the evidence path runs seeded / temperature 0 (I6). Non-determinism there is a bug, not a tuning knob.
- **The oracle is sacred.** Don't weaken a gate to make a PR pass. If a gate is wrong, change it in its own PR with rationale logged in Decisions.

---

## Decisions log (append-only)

| ID | Date | Decision | Rationale | Revisit when |
|----|------|----------|-----------|--------------|
| D1 | 2026-06-23 | **Corpus = SEC EDGAR 10-K / 10-Q.** | Free, public, high-stakes, strong gig pipeline, shareable demo. Adapter isolated to ingestion (brief §8). | Reference build ships; then add corpus variants. |
| D2 | 2026-06-23 | **Read-only v1.** No write/act tools. | Faster ship, easier trust, lower eval bar. | v2 only. |
| D3 | 2026-06-23 | **`check_claim` ships in v1.** | "Paste your own sentence, see if your docs back it" is too strong a demo to defer. It's the one thing above the minimal read-only path that earns its place. | If a leanest-possible first ship is needed, this is the cut. |
| D4 | 2026-06-23 | **Hallucination gate = literal 0**, operationalized: CI hard-fails on any entailment-judge flag that is **not** human-adjudicated as a false positive. Adjudicated false positives are logged and don't count. | Preserves the "zero hallucination" claim for the pitch while absorbing LLM-judge noise honestly. ε is a *process*, not a tolerance on the number. | If adjudication volume becomes unmanageable. |
| D5 | 2026-06-23 | **Citation precision hard gate starts at 0.9.** | Defensible opening bar; tighten as the golden set grows. | After M2 baseline is measured. |
| D6 | 2026-06-23 | **v1 runtime = Claude Code tool.** ATTEST ships as an MCP server + CLI that Claude Code invokes; the agent is the reasoner; ATTEST makes no runtime model calls. API-wrapped service (with inline entailment-gating) is v2. | Relocates the grounding guarantee to deterministic tools + a mandatory verify/log step. Splits the oracle into Layer-0 (deterministic, CI-blocking) and Layer-E (agent end-to-end, periodic via headless Claude Code). See brief "Runtime model" + §3, §4, §5. | v2 is scoped. |
| D7 | 2026-06-23 | **Golden schema = quote + locator** (not span IDs). A resolver binds `verbatim_quote → span_id` at M1 and must match each quote exactly once (resolution invariant). | Span IDs/offsets can't exist before M1 and depend on M1 normalization. Supersedes the brief's original §3 span-id schema (brief §3 now updated). Seed lives in `golden_seed.json`. | — |

---

## M0 — Audition rig  ·  `TODO`
**Goal:** prove the risky core cheaply before building anything real (brief §2).
**Gate:** on the ~20-item toy set — citation precision high, hallucination 0 on answerable items, **abstains on 100% of unanswerable items**. If it can't, iterate the rig; do not proceed.

- [ ] **M0-T1** · `branch: chore/scaffold` — Repo scaffold: directory layout, env, deps, place `ATTEST_build_brief.md` + this file, CI skeleton. **AC:** clean install runs an empty test suite green.
- [ ] **M0-T2** · `branch: feat/m0-toy-corpus` — Assemble 5–10 EDGAR excerpts as the toy corpus. **AC:** raw text stored verbatim; provenance (ticker, form, accession) recorded per excerpt.
- [x] **M0-T3** · `branch: feat/m0-golden-seed` — Hand-label ~20 golden items in the **quote + locator** schema (brief §3, D7), **≥5 deliberately unanswerable**. **AC:** schema-valid; answerable/unanswerable split recorded; honesty fields (`value_seen`/`source_status`) present. **DONE — see `golden_seed.json` (20 items, Apple FY2024 10-K). Still requires human verification pass (fill `verbatim_quote`s from canonical text; confirm `unverified_from_memory` items G008 non-current, G009 auditor).**
- [ ] **M0-T4** · `branch: feat/m0-rig` — `attest_rig.py`: trivial retrieval + draft-from-spans + verify + abstention + inline metrics (a Python stand-in for the agent loop, to prove the core). **AC:** runs end-to-end on the seed; prints the four gate metrics; **meets the M0 gate.**

---

## M1 — Ingestion + retrieval + span store  ·  `TODO`
**Goal:** subsystems 1–2 (brief §1). Evidence layer becomes real and immutable.
**Gate:** span hashes verify (I3); retrieval reproducible across two runs (I6); unit tests green.

- [ ] **M1-T1** · `branch: feat/m1-ingestion` — EDGAR adapter: fetch + normalize + **content-hash at ingest** (I3). Corpus-specific code lives *only* here. **AC:** every stored doc carries its hash; standing I3 hash test passes.
- [ ] **M1-T2** · `branch: feat/m1-spanstore` — Chunk + span index by char offset `(doc_id, start, end)`. **AC:** `get_span` returns the exact slice and re-verifies against the doc hash; mismatch raises a hard failure.
- [ ] **M1-T3** · `branch: feat/m1-retrieval` — Hybrid retrieval (BM25 + single embedding model), deliberately simple (brief §8). **AC:** returns candidate spans with offsets; **standing I6 reproducibility test** passes (identical results, two seeded runs).

---

## M2 — Deterministic verify + abstention tools  ·  `TODO`
**Goal:** the agent composes; ATTEST provides deterministic `verify` + `check_support` and the eval split goes live (brief §3, §4). No model calls inside ATTEST (D6).
**Gate:** all **Layer-0 component evals** pass on the golden set — span resolution 1:1, citation integrity (I3), retrieval recall, abstention trigger 100% on unanswerable, `verify` rejects planted ungrounded claims, invariant tests (I3–I6) green.

- [ ] **M2-T1** · `branch: feat/m2-verify` — `verify(answer_with_tags)` tool (I1): deterministically resolve every cited span, confirm hash-match, flag any sentence with no valid binding. **AC:** a planted unbound claim is flagged; a clean answer passes; result is logged.
- [ ] **M2-T2** · `branch: feat/m2-support` — `check_support(question)` (I2): returns supporting spans or `insufficient` via the relevance threshold — the deterministic abstention decision. **AC:** returns `insufficient` on 100% of unanswerable golden items; returns the gold span on answerable ones.
- [ ] **M2-T3** · `branch: feat/m2-plural` — `check_support` returns **all** qualifying spans (plural), ranked, never collapsing to one (brief §4; golden G007/G008). **AC:** multi-answer item returns ranked alternatives, each with its own evidence.
- [ ] **M2-T4** · `branch: feat/m2-claude-md` — Project `CLAUDE.md` documenting the required agent loop: search → draft from returned spans only → `check_support` → `verify` → present-or-abstain. **AC:** loop is unambiguous; references the tool contracts.
- [ ] **M2-T5** · `branch: feat/m2-layer0` — Layer-0 deterministic component-eval suite as required CI (brief §3). **AC:** PR shows the Layer-0 gate table; suite is fast and deterministic.
- [ ] **M2-T6** · `branch: feat/m2-layer-e` — Layer-E agent end-to-end eval: drive the Claude Code agent over the golden set in headless mode; score the transcript (hallucination/entailment via judge, abstention correctness, calibration → Brier + reliability curve to a results file). **AC:** runs on demand; produces the trend file. **Periodic, NOT a blocking CI gate.**

---

## M3 — Audit log  ·  `TODO`
**Goal:** subsystem 5 (brief §1; I4, I5).
**Gate:** append-only + full-replay tests pass; write-asymmetry (I4) test passes.

- [ ] **M3-T1** · `branch: feat/m3-audit` — Append-only log of query / retrieval set / answer / citations / abstention / confidence (I5). **AC:** entries immutable; tampering test fails the build.
- [ ] **M3-T2** · `branch: feat/m3-replay` — Reconstruct any past interaction from the log alone. **AC:** replayed interaction is byte-identical on the evidence path (I6).
- [ ] **M3-T3** · `branch: feat/m3-asymmetry` — Enforce + test I4: agent can write **only** the log; corpus is read-only. **AC:** standing I4 test attempts a corpus write and is rejected.

---

## M4 — MCP server + CLI (primary v1 interface)  ·  `TODO`
**Goal:** subsystem 8 (brief §1, §5). The only interface Claude Code uses. Read/write asymmetry enforced at the tool boundary.
**Gate:** boundary asymmetry test; the documented agent loop runs end-to-end over the tools on the golden set.

- [ ] **M4-T1** · `branch: feat/m4-mcp-scaffold` — Server + CLI mirror + tool registration. **AC:** server starts; tools enumerated; CLI invokes the same functions.
- [ ] **M4-T2** · `branch: feat/m4-tools` — Expose `search_corpus`, `get_span`, `check_support`, `verify`, `check_claim`, `get_audit_log` (brief §5). **AC:** each tool's contract tested; `check_claim` resolves a user claim to supporting spans or none.
- [ ] **M4-T3** · `branch: feat/m4-boundary` — Read tools have no side effects; `check_support` / `verify` / `check_claim` append to log only; corpus never writable (I4). **AC:** boundary test confirms read/write asymmetry.
- [ ] **M4-T4** · `branch: feat/m4-agent-loop` — Run the actual Claude Code agent loop over the MCP tools on the golden set. **AC:** agent searches, drafts, calls `check_support` + `verify`, and abstains where required — end-to-end through MCP.

---

## M5 — Demo UI  ·  `TODO`
**Goal:** subsystem 7 (brief §6). The conversion surface. Three flows, nothing more.
**Gate:** the three demo flows work end-to-end on EDGAR.

- [ ] **M5-T1** · `branch: feat/m5-scaffold` — React/TS app that **replays from the audit log** (no API backend in v1; brief §6). **AC:** loads a logged interaction and renders its answer.
- [ ] **M5-T2** · `branch: feat/m5-highlight` — Sentence → source-span highlight on hover/click. **AC:** clicking a sentence reveals its exact span.
- [ ] **M5-T3** · `branch: feat/m5-abstain-demo` — Pre-loaded unanswerable question that visibly shows the system refusing. **AC:** abstention is shown, not hidden.
- [ ] **M5-T4** · `branch: feat/m5-audit-panel` — Audit panel: retrieval + citations + confidence for the last answer. **AC:** panel opens and reflects the real last interaction.

---

## Backlog (v2) — do not start
API-wrapped service with **inline entailment-gating** (the structural-interception design) · action-taking / write tools · multi-corpus support · reranker upgrades · golden set to 200+ items · auth + multi-tenant for client deployments.

---

## Changelog (append-only)
*(Agent appends one line per merged PR: `YYYY-MM-DD · M#-T# · short note`.)*

- 2026-06-23 · — · ROADMAP created; M0 set as current focus.
- 2026-06-23 · M0-T3 · golden_seed.json added (20 items, Apple FY2024 10-K); pending human verification.
- 2026-06-23 · — · Runtime pivot to Claude Code tool (D6) + schema reconciliation to quote+locator (D7); brief and ROADMAP updated; M2/M4 restructured, oracle split into Layer-0/Layer-E.
