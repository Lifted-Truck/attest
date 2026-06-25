# ATTEST — ROADMAP

**This file is the single source of truth for status and sequencing.** Architecture, invariants, and rationale live in `ATTEST_build_brief.md`; this file references it by `§` rather than duplicating it. When the two disagree, the brief wins on *design* and this file wins on *what to do next*.

**Cardinal rule:** Ground or abstain — never invent. (Invariants I1–I6: see brief §0.)

### Status legend
`TODO` · `WIP` · `BLOCKED` · `DONE` — task checkboxes mirror this (`- [ ]` / `- [x]`).

### ▶ Current focus
**M1 · M1-T3** — hybrid retrieval (BM25 + single embedding) over the span store, with a standing I6 reproducibility test. M1-T1 (ingestion/I3) and M1-T2 (span store + resolution invariant) are `DONE`.

> **Golden set is now fully bound:** all 21 `verbatim_quote`s resolve 1:1 to the
> canonical text (`scripts/resolve_golden_quotes.py`; guarded by `tests/test_spans.py`).
> G016 was split into current/non-current term-debt entries to keep each quote
> singly resolvable. A broader human verification pass remains welcome but the
> seed is no longer `null`-quoted.

> **Working mode:** single primary agent develops directly on `main` (no PR-per-task gate
> in this repo). CI still runs on every push to `main`; a red gate or a violated invariant
> is treated as not-done and must be fixed before advancing focus.

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
| D8 | 2026-06-24 | **Highlighted evidence-view GUI is pulled forward** to a small, server-less static-HTML renderer (`render_evidence_view`, new **M2-T7**) the moment `verify` exists; the polished React/audit-log replay app stays at **M5** and upgrades it. **Contract:** the agent drafts an answer with each sentence tagged by `span_id`(s) → `verify` confirms every tag resolves + hash-matches (I1/I3) → `log` records it (I5) → the renderer deterministically emits a two-pane page (canonical document left with `<mark>` highlights, answer right with click-to-source hyperlinks). The agent's tagged markdown is an *authoring surface that passes through verify/log* — never a hand-maintained source of truth; hyperlinks are generated, never asserted. Render the **normalized canonical text** (the hashed, cited text), not the original filing HTML. | Visual payoff is the conversion surface (brief §6) and worth pulling to mid-project, but faithful highlighting needs char-offset spans (M1-T2) + validated citations (M2-T1), so the earliest *honest* viewer is post-M2. Hand-authored citation links would reintroduce the exact unverified-claim failure ATTEST exists to prevent (I1). Refines brief §6. | If the React app at M5 fully subsumes the static renderer, retire the latter. |
| D9 | 2026-06-24 | **Atom-resolver contract for `verify` / `check_claim`.** The agent decomposes an answer into **atoms** (load-bearing tokens: numbers, currency, %, dates, named entities) and binds each to a specific source location `(doc_id, content_hash, char_start, char_end)`. A **fixed, deterministic resolver** confirms the slice *at that offset* equals the atom **exactly** (literal match — defined whitespace normalization, word-boundary, accounting-`( )`-negative aware), hash-matches (I3), and lies within the **spans retrieved for this query** (no whole-corpus fishing). The agent **parameterizes** (supplies atoms + bindings); it **never authors** the resolver (oracle-is-sacred; extends D8's tag contract). Crucially, `verify` also runs its **own** atom extraction over the final answer and requires every detected load-bearing token to be bound — confabulation can't hide in untagged prose. **Derived** values (e.g. a computed delta) are not atoms: they declare operands (each an atom that resolves) + an operation the resolver recomputes. | Makes every figure/quote the agent ships **machine-checkable and located**, killing invented citations while keeping the checker deterministic and CI-gated. It is the user's "bounded lookup" idea, hardened. Existence ≠ support remains the runtime limit: right-number/wrong-line or a misphrased reading is caught offline (Layer-E), structurally in v2. Open implementation contingencies are tracked under **M2-T1**. | Revisit if the atom taxonomy proves too coarse, or when v2 pulls entailment inline. |

---

## M0 — Audition rig  ·  `DONE`
**Goal:** prove the risky core cheaply before building anything real (brief §2).
**Gate:** on the ~20-item toy set — citation precision high, hallucination 0 on answerable items, **abstains on 100% of unanswerable items**. If it can't, iterate the rig; do not proceed.
**Gate met (2026-06-24):** `attest_rig.py` → answer correctness 100%, citation precision 100% (gate ≥90%, D5), recall 100%, hallucination 0%, abstention accuracy 100% on all 7 unanswerable items, 0 false abstentions. Standing test `tests/test_rig.py` locks the gate into CI.

- [x] **M0-T1** · `branch: chore/scaffold` — Repo scaffold: directory layout, env, deps, place `ATTEST_build_brief.md` + this file, CI skeleton. **AC:** clean install runs an empty test suite green. **DONE** — src-layout `attest` package, pytest+ruff, CI skeleton; clean-venv install runs ruff + smoke suite green; CI green on merge.
- [x] **M0-T2** · `branch: feat/m0-toy-corpus` — Assemble 5–10 EDGAR excerpts as the toy corpus. **AC:** raw text stored verbatim; provenance (ticker, form, accession) recorded per excerpt. **DONE** — 5 verbatim excerpts from AAPL FY2024 10-K (cover, operations, balance sheets, cash flows, auditor report) in `corpus/toy/`; provenance + per-excerpt sha256 in `manifest.json`; rebuilt deterministically by `scripts/build_toy_corpus.py` (raw cached under gitignored `data/raw/`); standing integrity test in `tests/test_toy_corpus.py`. **Finding for human review:** golden item **G008 labels are inverted** — the filing reports *current* marketable securities $35,228M and *non-current* $91,479M; G008 calls $91,479M "current." Fix in M0-T3's verification pass, not by an unreviewed agent edit.
- [x] **M0-T3** · `branch: feat/m0-golden-seed` — Hand-label ~20 golden items in the **quote + locator** schema (brief §3, D7), **≥5 deliberately unanswerable**. **AC:** schema-valid; answerable/unanswerable split recorded; honesty fields (`value_seen`/`source_status`) present. **DONE — see `golden_seed.json` (20 items, Apple FY2024 10-K). Still requires human verification pass (fill `verbatim_quote`s from canonical text; confirm `unverified_from_memory` items G008 non-current, G009 auditor).**
- [x] **M0-T4** · `branch: feat/m0-rig` — `attest_rig.py`: trivial retrieval + draft-from-spans + verify + abstention + inline metrics (a Python stand-in for the agent loop, to prove the core). **AC:** runs end-to-end on the seed; prints the four gate metrics; **meets the M0 gate.** **DONE** — BM25 (unigram+bigram) over line/block spans with section breadcrumbs; citation = score band (plural-and-ranked); verify = assert only values present in cited spans; abstention via relevance threshold + agent-judgment guards (temporal / entity-scope / false-premise / not-disclosed-in-10-K). Gate passes (see milestone line). Guards are documented stand-ins for the runtime agent's reasoning — the real reasoner replaces them at M2+.

---

## M1 — Ingestion + retrieval + span store  ·  `TODO`
**Goal:** subsystems 1–2 (brief §1). Evidence layer becomes real and immutable.
**Gate:** span hashes verify (I3); retrieval reproducible across two runs (I6); unit tests green.

- [x] **M1-T1** · `branch: feat/m1-ingestion` — EDGAR adapter: fetch + normalize + **content-hash at ingest** (I3). Corpus-specific code lives *only* here. **AC:** every stored doc carries its hash; standing I3 hash test passes. **DONE** — `src/attest/ingest/` package: `document.py` (Document + sha256 content hash + `verify_document`, corpus-agnostic), `store.py` (on-disk store; re-verifies hash on every load), `edgar.py` (the *only* corpus-specific module — filing registry, fetch+cache, deterministic HTML→canonical-text normalization). Apple FY2024 10-K ingested to `corpus/store/` (219K chars, hash in `meta.json`) via `scripts/ingest_corpus.py`; M0's `build_toy_corpus.py` now reuses `edgar.normalize` (no duplicated corpus code). Standing I3 tests in `tests/test_ingest.py`: hash re-verifies, tamper (text or hash drift) rejected, normalization deterministic (I6), golden evidence preserved.
- [x] **M1-T2** · `branch: feat/m1-spanstore` — Chunk + span index by char offset `(doc_id, start, end)`. **AC:** `get_span` returns the exact slice and re-verifies against the doc hash; mismatch raises a hard failure. **DONE** — `src/attest/spans.py`: deterministic line-level `chunk_document` (exact offsets, `canonical_text[start:end] == span.text`), `SpanStore.get_span` (re-verifies doc hash via `verify_document` before serving; out-of-range → `SpanError`), and `resolve_quote` enforcing the **resolution invariant** (D7: exactly-once, else `ResolutionError`). All **21 golden `verbatim_quote`s bound 1:1** to the canonical text via `scripts/resolve_golden_quotes.py` (G016 split into current/non-current so each resolves singly; `source_status` → `grounded`). Standing tests in `tests/test_spans.py`: exact-slice, hash re-verify on drift, deterministic chunking (I6), resolution invariant, duplicate/missing quote rejected.
- [ ] **M1-T3** · `branch: feat/m1-retrieval` — Hybrid retrieval (BM25 + single embedding model), deliberately simple (brief §8). **AC:** returns candidate spans with offsets; **standing I6 reproducibility test** passes (identical results, two seeded runs).

---

## M2 — Deterministic verify + abstention tools  ·  `TODO`
**Goal:** the agent composes; ATTEST provides deterministic `verify` + `check_support` and the eval split goes live (brief §3, §4). No model calls inside ATTEST (D6).
**Gate:** all **Layer-0 component evals** pass on the golden set — span resolution 1:1, citation integrity (I3), retrieval recall, abstention trigger 100% on unanswerable, `verify` rejects planted ungrounded claims, invariant tests (I3–I6) green.

- [ ] **M2-T1** · `branch: feat/m2-verify` — `verify(answer_with_tags)` tool (I1): deterministically resolve every cited span, confirm hash-match, flag any sentence with no valid binding. Implements the **atom-resolver contract (D9)**. **AC:** a planted unbound claim is flagged; a clean answer passes; a number bound to the wrong offset (same digits, different line) is *not* falsely passed by binding to the literal alone; `verify`'s own atom extraction flags an untagged load-bearing token; result is logged.

  <br>**Open contingencies for the resolver (D9) — decide while building, don't pre-bake:**
  - **Atom taxonomy** — which token types are mandatory-bound (numbers, currency, %, dates, named entities) vs free prose; how the agent demarcates them (reuse D8's `span_id` tags).
  - **Match normalization** — exact literal, but define whitespace handling (`"$ 364,980"` vs `"$364,980"`), string case, and **word-boundary** matching so `"100"` ≠ inside `"100,544"`. Resist numeric-fuzzy matching — it's a new trust surface.
  - **Accounting formats** — negatives in parens `"(19,154)"`, thousands separators, and scale/units stated in a table caption (the "million" lives in the header, not the cell → its own atom resolving to the caption span).
  - **Multiplicity** — 0 matches → abstain; 1 → bind; many → bind to a *specific offset* (the `364,980`-appears-twice case must verify at the right line, not merely "exists"); plural answers surface all (brief §4).
  - **Scope** — resolve against spans retrieved for *this* query, not the whole corpus (prevents out-of-context fishing).
  - **Independent extraction** — `verify` re-extracts candidate atoms from the final answer and requires coverage, so the agent can't evade by leaving a figure untagged.
  - **Derived values** — operands-as-atoms + a recomputed operation; the result itself is not cited (e.g. G005/G019 deltas).
  - **Offset stability** — bindings carry the doc `content_hash`; a stale offset against a new hash is a hard fail (I3).
  - **Logging** — every resolve/verify call appended to the audit log for replay (I5).
  - **Residual (state plainly, don't overclaim)** — right-number/wrong-*meaning* and misphrasing are *not* caught here (existence ≠ entailment); that's Layer-E offline, structural in v2.
- [ ] **M2-T2** · `branch: feat/m2-support` — `check_support(question)` (I2): returns supporting spans or `insufficient` via the relevance threshold — the deterministic abstention decision. **AC:** returns `insufficient` on 100% of unanswerable golden items; returns the gold span on answerable ones.
- [ ] **M2-T3** · `branch: feat/m2-plural` — `check_support` returns **all** qualifying spans (plural), ranked, never collapsing to one (brief §4; golden G007/G008). **AC:** multi-answer item returns ranked alternatives, each with its own evidence.
- [ ] **M2-T4** · `branch: feat/m2-claude-md` — Project `CLAUDE.md` documenting the required agent loop: search → draft from returned spans only → `check_support` → `verify` → present-or-abstain. **AC:** loop is unambiguous; references the tool contracts. **NOTE (2026-06-23):** `CLAUDE.md` already exists at repo root and carries a provisional "Runtime agent loop" section. This task is therefore *expand-in-place*, not create — flesh that section out against the **actual M4 tool contracts** (exact tool names, arg/return shapes, error modes) rather than authoring a second file. Keep it the single canonical CLAUDE.md.
- [ ] **M2-T5** · `branch: feat/m2-layer0` — Layer-0 deterministic component-eval suite as required CI (brief §3). **AC:** PR shows the Layer-0 gate table; suite is fast and deterministic.
- [ ] **M2-T6** · `branch: feat/m2-layer-e` — Layer-E agent end-to-end eval: drive the Claude Code agent over the golden set in headless mode; score the transcript (hallucination/entailment via judge, abstention correctness, calibration → Brier + reliability curve to a results file). **AC:** runs on demand; produces the trend file. **Periodic, NOT a blocking CI gate.**
- [ ] **M2-T7** · `branch: feat/m2-evidence-view` — `render_evidence_view`: a deterministic, server-less generator that turns one verified interaction (a `verify` result over a span-tagged answer) into a **self-contained two-pane HTML** — canonical document on the left with `<mark>` highlights, answer on the right with click-to-source hyperlinks (D8). Reads the span store + verify output; mutates nothing (I4). **AC:** for a sample tagged answer, every cited sentence hyperlinks to the exact highlighted span in the document pane; an unbound sentence is shown flagged, not silently linked; opening the HTML needs no server or network. **Not part of the M2 Layer-0 gate** — a deliverable that rides on `verify`; M5 upgrades it to the React replay app.

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
**Goal:** subsystem 7 (brief §6). The conversion surface — the polished **upgrade** of the M2-T7 static evidence view (D8): two-pane document-beside-response with click-to-source hyperlinks, now replaying from the audit log. Three flows, nothing more.
**Gate:** the three demo flows work end-to-end on EDGAR.

- [ ] **M5-T1** · `branch: feat/m5-scaffold` — React/TS app that **replays from the audit log** (no API backend in v1; brief §6), in the **two-pane layout** (canonical document beside the answer) established by M2-T7. **AC:** loads a logged interaction and renders document + answer side by side.
- [ ] **M5-T2** · `branch: feat/m5-highlight` — Sentence → source-span highlight via click-to-source hyperlinks (the M2-T7 contract, D8): clicking a claim flashes its exact `<mark>`ed span in the document pane. **AC:** clicking a sentence reveals its exact span; an unbound sentence is shown flagged, never silently linked.
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
- 2026-06-23 · M0-T1 · Repo scaffold merged: src-layout `attest` package, pytest+ruff, CI skeleton; clean install runs smoke suite green. Switched to single-agent-on-main working mode.
- 2026-06-23 · M0-T2 · Toy corpus assembled: 5 verbatim AAPL FY2024 10-K excerpts + provenance/sha256 manifest (`corpus/toy/`), deterministic build script, integrity test. Flagged inverted current/non-current marketable-securities labels in golden G008 for M0-T3 human review.
- 2026-06-24 · M0-T3 · Golden verification: corrected G008 (inverted labels → current $35,228M / non-current $91,479M) and grounded G009 (Ernst & Young LLP) against the canonical filing; both marked grounded + verification_note.
- 2026-06-24 · M0-T4 · Audition rig `attest_rig.py` clears the M0 gate (precision/recall/correctness 100%, hallucination 0%, abstention 100%). Standing gate test added. **M0 DONE** — advancing to M1.
- 2026-06-24 · — · Added `demo.py` (guided M0 walkthrough) + README "See it run".
- 2026-06-24 · — · D9: atom-resolver contract for `verify`/`check_claim` (agent supplies located atoms; fixed resolver checks exact literal at offset + hash + scope; independent re-extraction; derived-value operands). Open contingencies tracked under M2-T1; brief §5 updated.
- 2026-06-25 · M1-T2 · Span store (`attest.spans`): char-offset chunking, `get_span` with hash re-verify (I3), `resolve_quote` enforcing the resolution invariant (D7). All 21 golden quotes bound 1:1 to canonical text; G016 split; standing `tests/test_spans.py`.
- 2026-06-24 · M1-T1 · EDGAR ingestion adapter: `attest.ingest` (Document + content-hash I3, store with verify-on-load, isolated `edgar.py`). Apple FY2024 10-K ingested to `corpus/store/`; standing I3 tests (tamper rejected, deterministic normalization, evidence preserved). build_toy_corpus reuses the adapter's normalize.
- 2026-06-24 · — · D8: highlighted two-pane evidence-view GUI pulled forward to **M2-T7** (server-less static-HTML renderer on the verify result); M5 becomes its polished log-replay upgrade. Contract: agent tags spans → verify → log → deterministic render (hyperlinks are verified span refs, not hand-authored). Brief §6 + M5 reworded.
