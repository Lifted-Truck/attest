<!-- Research input (like docs/landscape_lessons.md): subordinate to ROADMAP.md; authorizes
no work. Its D24–D27 are CANDIDATE decision rows pending human triage — not adopted.
Produced by the provability-research swarm (run wf_0522ac48-3e1, 2026-07-16): 8 Opus 4.8
literature lenses → 42 candidate techniques → hostile per-candidate review (default-refute)
→ 0 clean survivors → this synthesis of the demoted cores. 51 agents, ~2.6M tokens.
Julian's $2,000,000 refutation case was the concrete test injected into every prompt. -->

# ATTEST Research Report — Can the "$2,000,000 refutation" be caught at runtime, deterministically?

*Synthesis of the provability/veridicality sweep. Register: ATTEST house docs. Every claim below is marked GUARANTEED (a hard, Layer-0, seeded, model-free property) or MEASURED (a Layer-E number that can move, never a gate). The distinction is the entire point of the exercise.*

---

## 1. The verdict in five sentences

No — there is no deterministic, model-free, runtime check that catches the refutation case in general, because "asserted vs. mentioned-and-denied" is a pragmatic judgment about a speaker, not a formal property of the text, and a refutation carried without any surface cue ("the revaluation raises it to $3.4M", a figure silently superseded by a later table) leaves literally nothing for a deterministic method to see. **Partially yes for exactly one subset:** where the refutation is *lexically marked and span-local* to the cited figure ("...claimed $2M, but in fact this is incorrect"), a closed cue-set scan can deterministically force the outcome to *partial/abstain* — that slice, and only that slice, can become a Layer-0 GUARANTEE. That guarantee is one-directional: it can only *add* abstentions, never permit a present, so it cannot manufacture the confident-wrong answer ATTEST exists to prevent — which is also why it is contract-legal as a monotonic strengthening. Everything richer — veridicality tagging, NLI entailment, natural-logic projection, conformal bounds — either puts a model on the deciding path (breaks I6 and "AI never decides", forces a major contract bump) or delivers only a population-average MEASUREMENT that is provably silent about the single high-stakes query, and in the one place it matters most (numbers) is documented to be *weakest*. And a load-bearing honesty note that reframes the whole priority: the "$2M" sentence is **synthetic** — it does not occur in the golden corpus, whose actual false-premise trap ("did total assets decline?") is refuted by *arithmetic in a table row*, which no negation/veridicality machinery touches at all.

---

## 2. The ceiling — what is genuinely impossible, and what it is made of

Julian asked to know both how close we can push and where the wall actually is. The wall is real, and it is nearer than the famous one.

**What is provably/practically impossible:** a hard, Layer-0, theorem-grade guarantee that ATTEST *never* presents a mentioned-and-denied figure across *arbitrary* prose. This is impossible for a coverage reason, not an accuracy reason — no better parser closes it:

- **The near wall — irreducible pragmatics (the real one).** Whether a figure is *asserted* or *mentioned-and-denied* is a pragmatic property, context- and world-knowledge-sensitive. There is no total, deterministic function from a sentence to its assertion status. The consequence: **cue-less refutation is invisible to every deterministic surface method**, and its recall is unbounded-below — you can never promise you caught them all. This is a boundary of the problem, not a gap in the tool.

- **The far wall — undecidability (looser, only bites if you go through it).** Any route that cashes claim-checking out as general first-order entailment inherits semi-decidability of FOL (Church/Turing) and Rice's theorem. You escape only by retreating to a decidable fragment — and the fragments that stay decidable (monotonicity, quantifier-free SMT) cannot express the numeric-revaluation reasoning the case ultimately turns on. The error just migrates into the NL→logic translation step, which is itself the unsolved, model-driven, silently-failing part.

- **Gödel–Löb / provability logic is not part of the wall at all.** GL's box is "Peano Arithmetic proves φ." ATTEST's question is "does this passage *assert* Q." There is no honest reduction between them; treating a 10-K sentence as an arithmetic formula is a category error. Recording this kills the temptation to re-litigate it: the relevant fields are natural logic, veridicality, and conformal prediction — GL contributes nothing.

**What this means for the two model-based escape hatches, stated plainly:**

- The veridicality/NLI family *can* see cue-less refutation in principle, but (a) it is a runtime model → non-deterministic → breaks I6 and puts AI on the deciding path; and (b) its measured ceiling is ~80% macro-F1, and its single dominant error class is *fine-grained numeric/date/name insensitivity* (~66% of errors, ~43% of false positives). It is weakest **exactly** on numeric claims — the class a financial/patent client is most exposed on. So even paying the architecture change buys a soft ~80% classifier that fails hardest where ATTEST needs it most.
- The conformal/selective-prediction family gives a genuine *distribution-free* guarantee, but it is **marginal** (population-average) — provably not per-answer (Barber et al. 2021: distribution-free conditional coverage is impossible). A marginal α-bound is satisfied whether the α-fraction of errors are benign near-misses or the one catastrophic $2M disaster. It is an insurance policy over a corpus, not a certificate about a claim, and it voids *silently* the moment the corpus is swapped (EDGAR→patents) or a client changes — exactly ATTEST's first-engagement conditions.

**How close we can push:** to deterministic abstention on the *lexically-marked, span-local* subset. That moves the defect from *silently presented* to *often caught*. It cannot reach *never missed*, and it cannot decide truth — only "is there a denial/correction marker sitting on top of this figure."

---

## 3. The staircase — increments, cheapest and most certain first

The hostile review returned **zero clean survivors**. What survives is the *honest, demoted core* of several refuted candidates — each stripped to the smaller claim the evidence actually supports. They are ordered so each rung is cheap, certain, and a prerequisite for judging whether the next is worth building.

### Rung 0 — Already shipped; no action (name it so we stop re-proposing it)
The "proof-carrying certificate" idea adds no catch and no new honesty: truth-contract v1.1 already names `verified ≠ entailed` as its one deliberate non-guarantee, `verify` already stamps the rigor version (TC-2) it was produced under, and its frame+coverage result is already appended to the append-only audit log (I5), deterministically re-checkable offline. Importing theorem-prover vocabulary onto a string-co-occurrence + hash check is the CLAUDE.md "trap." **Guarantees: nothing new. Layer: n/a. Contract bump: no. Verdict: do not build.**

### Rung 1 — Denial/correction cue-scan as a Layer-E MEASUREMENT + advisory flag  *(build first)*
A deterministic scan (regex over a *closed evaluative-denial/correction* cue set — `incorrect, erroneous, mistaken, overstated, restated, superseded, corrected, revalued` — plus offset proximity to a bound figure atom). Run it as a **measured signal**, not a gate: on the golden set and the real corpus, count how often a citation sits span-local to a denial/correction marker, and surface a non-blocking "possible denial cue near citation — human review" flag in the evidence view.
- **GUARANTEES: nothing at runtime.** It is a measurement instrument.
- **MEASURES:** the base rate of cue-marked refutation in the actual corpus — i.e. *whether Rung 2 is even worth building.* If cue-marked refutation is rare-to-absent in real patents/10-Ks (plausible — the golden trap is arithmetic, not lexical), the whole gate project is correctly deprioritized on evidence.
- **Deterministic (I6-clean), no model, legible cue list.** Layer: **E**. Dependencies: none (stdlib regex). **Contract bump: no** (a measurement is not a guarantee).
- **Why it's Rung 1 and not skipped:** it is the cheapest way to learn the one fact that decides everything downstream, and it cannot regress anything because it gates nothing.

**Critical caveat carried from the sweep:** do NOT include attribution verbs (`reported, claimed, stated, alleged`) in the cue set. Those are the *primary assertion vocabulary* of both corpora ("the Company reported net sales of $391,035 million"; "What is claimed is..."). Including them fires on nearly every good citation. The scan is viable *only* if restricted to evaluative-denial/correction markers.

### Rung 2 — Promote the cue-scan to a Layer-0 abstain-trigger on the closed set  *(only if Rung 1 shows a tolerable false-positive rate)*
Same deterministic scan, now with teeth: if a cited span carries an evaluative-denial/correction cue within N chars of the bound figure atom, `verify` downgrades the outcome to `partial`/`abstain` instead of permitting `answer`.
- **This is the one rung that converts a Layer-E residual into a Layer-0 GUARANTEE — say it loudly.** GUARANTEED: on any answer whose cited span contains a closed-set denial/correction cue span-local to the bound figure, ATTEST will not present; it downgrades. Deterministic, seeded, model-free, I6-clean.
- **Does NOT guarantee:** catching cue-less refutation (unbounded false negatives — the ceiling), nor refutations outside the proximity window (page-40 figure restated in a page-240 footnote). It will also occasionally over-abstain on a benign-but-cue-adjacent span — but that is the *safe* direction (blocks a good answer, never passes a bad one).
- **Why it's contract-legal:** it is a pure *monotonic strengthening* — it can only move outcomes toward abstain, never toward a present it would otherwise refuse. That is a minor contract bump under D21, **but the upgrade ratchet still applies**: it ships only if Layer-0 holds AND Layer-E improves-or-holds. The refutations are right that mass *spurious* abstention would fail the ratchet — which is exactly why Rung 1's measurement is a hard prerequisite, not optional.
- Layer: **0**. Dependencies: none. **Contract bump: yes — minor (strengthening), new D#.**
- **The legibility trap to respect:** the cue *list* is legible; the *scope rule* ("within N chars / same clause") is the illegible part. Keep N small and clause-bounded, document it as an admitted heuristic, and never let the flag read as "refuted" (a discourse claim it cannot substantiate) — only as "denial cue in scope → downgraded."

### Rung 3 — Veridicality/NLI entailment as a Layer-E oracle for the residual  *(measurement only, never a gate)*
The full veridicality/NLI signal (there is already a seam: `layer_e.py` has `judge_entailment` and `judge_refutes_premise`). Use it to *measure the size of the permanent hole* — how often cue-less refutation slips past Rung 2 — on the golden set, billed, offline.
- **GUARANTEES: nothing.** It is a model call → non-deterministic → can never gate. **MEASURES** the residual risk and feeds calibration.
- **Does NOT convert anything to guaranteed;** it quantifies what is unguardable. Its own numeric blind spot means it will under-report on exactly the numeric cases — so read it as a *floor* on the residual, not a true estimate.
- Layer: **E**. Dependencies: a billed model at eval time (already the Layer-E posture). **Contract bump: no** (Layer-E measurement changes no runtime guarantee) — but if it were ever moved onto the runtime path, that is a **major** bump + new D#, and it is explicitly out of scope for v1.

**Not on the staircase (measurement-only, adopt if cheap, but not for the $2M case):** conformal / selective-prediction *reporting* vocabulary on the Layer-E harness — a marginal, population-level presented-error number, stamped with the calibration-set version and voided-visibly on corpus swap. Honest as a fleet metric; it is *not* a per-answer certificate and must never be printed as one.

---

## 4. Testing protocol

The governing constraint on every rung: **the golden sets are append-only and frozen; a new check must not silently re-label a currently-correct item.** Concretely, before any rung merges, run it against `golden_seed.json` (EDGAR, 20 items) and the ratified patent golden set (D23) and confirm **zero currently-`answer` items flip to a wrong `abstain`** and **zero currently-`abstain`/`reject` items flip to `answer`**. A flip is a regression, not a tuning result.

### Rung 1 (Layer-E measurement + advisory)
- **Design:** deterministic function `denial_cue_hits(span, atom_offsets) -> list[CueHit]`. Layer-E harness (`scripts/run_layer_e.py`) reports, per golden item and per corpus document, the count and location of hits.
- **Layer-0 test (the *scanner itself* is deterministic, so it gets a real gate):** a fixture table of `(text, atom_offset) -> expected_hits`, asserted exactly. This is CI-blocking on the *scanner's determinism*, not on any answer outcome.
- **Fixtures needed:** (a) the synthetic $2M sentence (positive control); (b) 10–15 *benign* real spans containing contrast/attribution words that must NOT hit (`"net sales rose, but cost of sales also rose"`, `"the Company reported net sales of $391,035 million"`) — these guard the false-positive boundary; (c) a cue-less refutation (negative control that SHOULD be missed, documented as a known ceiling miss, so a future "improvement" that appears to catch it is scrutinized as a possible over-trigger).
- **Regression signal:** the fixture table changes output, or the corpus-wide false-positive rate on benign spans exceeds a pre-registered threshold.
- **Oracle interaction:** none dangerous — it gates nothing; it only prints numbers next to existing outcomes.

### Rung 2 (Layer-0 abstain-trigger)
- **Design:** a standing Layer-0 eval `test_denial_cue_forces_downgrade`: the $2M positive-control fixture must produce `partial`/`abstain`; the benign real-span fixtures must remain `answer`. Both directions are asserted — the second is the one that protects answer-rate.
- **The false-positive test is the load-bearing one.** Precision >> recall means the failure we cannot tolerate here is *over-abstention on good answers*. The benign-span fixture set from Rung 1 becomes a CI gate: any regression that abstains on them fails the build. Report false-positive behavior on **real** 10-K/patent spans, not benchmark sentences.
- **Regression signal, two kinds:** (1) a golden `answer` item flips to abstain (hard fail — re-label of the frozen oracle); (2) the benign-span false-positive rate rises above the pre-registered ceiling (fail — answer-rate erosion).
- **Ratchet check:** merge only if the full Layer-0 gate stays green AND the Layer-E aggregate (`layer_e.py::aggregate`) does not lose utility/calibration. A rung that adds correct abstentions passes; one that adds spurious ones fails the ratchet by construction — this is the mechanism, not a promise.
- **Contract:** new `D#` row + minor version bump (strengthening); the version is stamped into records as `verify` already does for TC-2.

### Rung 3 (Layer-E entailment oracle)
- **Design:** extend the existing `judge_entailment`/`judge_refutes_premise` Layer-E path to score the *residual* — items where Rung 2 presented but a human label says refuted. Report as a MEASURED miss-rate, billed, non-blocking.
- **Fixtures:** a small human-labeled set of cue-less refutations drawn from the real corpus (this is expensive annotation and must be versioned like a prior, per D4).
- **Regression signal:** none in the gate sense (it never gates); drift is watched as a metric with the model + prompt version pinned and stamped.
- **Oracle interaction:** it *measures against* the golden sets; it never modifies outcomes, so it cannot re-label.

---

## 5. Candidate D# rows (ROADMAP house style)

| D# | Decision | Rationale | Revisit trigger |
|---|---|---|---|
| **D24** | **Denial/correction cue-scan ships as a Layer-E MEASUREMENT + non-blocking advisory flag first, not a gate.** Closed evaluative-denial/correction cue set only (`incorrect, erroneous, mistaken, overstated, restated, superseded, corrected, revalued`); attribution verbs (`reported, claimed, stated, alleged`) are **excluded** because they are the corpora's own assertion vocabulary. | The refutation case is only deterministically visible when lexically marked and span-local; a measurement is the cheapest way to learn the real-corpus base rate before spending a gate on it. Deterministic, no model, I6-clean, legible list. | Rung-1 corpus measurement shows cue-marked refutation occurs at a rate that would make a gate worth the answer-rate cost (→ D25); or shows it is rare/absent (→ deprioritize the gate, record the negative result). |
| **D25** | **Promote the D24 cue-scan to a Layer-0 abstain-trigger** (span-local denial/correction cue → downgrade `answer`→`partial`/`abstain`), gated on D24's measured false-positive rate on real spans being below a pre-registered ceiling. Minor contract bump (monotonic strengthening: can only add abstentions). | Converts the lexically-marked, span-local slice of the refutation residual from MEASURED to GUARANTEED, in the precision-safe direction, without any model on the deciding path. | The benign-span false-positive rate on real 10-K/patent prose exceeds the answer-rate ceiling (→ revert to advisory-only); or a golden `answer` item flips (→ hard revert, oracle protection). |
| **D26** | **Veridicality/NLI entailment stays Layer-E, billed, never a runtime gate**, used to measure the cue-less refutation residual D25 cannot reach. | A runtime NLI/veridicality call breaks I6 and puts AI on the deciding path; its ~80% ceiling is weakest on numeric claims (the exact class). It is a yardstick for the permanent hole, not a fix. | Only revisit as a *runtime* mechanism under a **major** contract version + full ratchet evidence — out of scope for v1. |
| **D27** *(documentary)* | **Provability logic (Gödel–Löb) and general FOL→prover entailment are recorded as inapplicable / out of scope.** GL is a category error for document assertion; general FOL entailment is undecidable and its decidable fragments cannot express numeric revaluation. | Stops re-litigation. The reachable win is deterministic scope-detection on the lexically-marked subset (D25), not a general entailment engine. | New evidence that a decidable fragment covers the numeric-refutation class faithfully and model-free (none in current literature). |

---

## 6. What died, and why (one line each)

- **Monotonicity / polarity marking (NatLog polarity, ccg2mono, Udep2mono)** — catches only intra-clausal quantifier/negation flips; the $2M case is cross-clausal attribution + evaluative denial, which no polarity arrow reaches; needs a statistical parser on the deciding path.
- **Implicative/factive signatures (Nairn–Condoravdi–Karttunen)** — its `o/o` "merely reported" class *is* the assertion vocabulary of 10-Ks and patents, so it inverts and floods good figures with abstentions; needs a dependency parser on the path.
- **Full NatLog seven-relation join calculus** — puts an entailment DECISION at runtime (breaks `verified ≠ entailed`), needs a model, still misses the clause-level denial; least legible option in the lens.
- **Neuro-symbolic natural logic (NeuralLog / MonaLog / ProoFVer)** — neural beam search in the deciding path → non-deterministic (I6 violation); SOTA is on 10-word clean-parse benchmarks that collapse on 10-K/patent prose.
- **FactBank + De Facto factuality profiler** — ~30% macro error on clean *news*, worst on the rare counterfactual class ATTEST needs; its "dependency parser" is a learned model on the path.
- **NegEx / ConText scope negation** — the production clinical lexicon lacks `incorrect/erroneous` and misses the case; a new financial/patent lexicon is unbuilt, unvalidated, and has unbounded false-negatives on open-ended refutation phrasing.
- **Committed-belief / source-attribution tagging (Prabhakaran/Rambow/Diab)** — under-detects commitment flips inside long attributed spans (the one place it must fire); 64% F1 belongs to the parser+classifier on news, not the shippable deterministic lexicon.
- **BioScope / CoNLL-2010 hedge detection** — does not touch the $2M case at all (no speculation cue), and its trigger words fire on pervasive non-epistemic uses in both corpora.
- **Neural event-factuality regression (Rudinger/White/Van Durme)** — stochastic runtime model; scores verb-anchored *events*, not figures; fails invisibly under domain shift; illegible float.
- **Classic Boxer / DRS → FOL → prover** — deterministic but inert on real messy prose (parse failure near-total on OCR'd patents / nested 10-K sentences); the flagship $2M example isn't even in the corpus (the real trap is a table row); DRS/Vampire is unauditable to a patent attorney.
- **Neural DRS parsing (PMB) → prover** — a learned parser's output IS the logical form the prover decides on → AI on the deciding path; its characteristic failure is a *silently dropped negation* → confident false POSITIVE (the forbidden direction).
- **AMR (+ :polarity) as a red-flag feature** — labeled `deterministic:true` while `needs_runtime_model:true`; over-fires on ubiquitous benign negation ("not material") *and* abstracts away number/scope so it cannot separate `$2M` from `$2.1M`.
- **LLM→logic autoformalization (Logic-LM, LINC, SatLM, SMT)** — the compile step is a runtime model call that can emit a *compilable-but-unfaithful* form the solver then "proves"; moves the hallucination into the invisible logical form.
- **SMT solver (Z3/cvc5) on already-formal constraints** — never touches real prose; the risk lives entirely in the prose→constraint encoding it presupposes; D9 already recomputes derived values more legibly.
- **NL-premises → FOL → prover (Logic-LM/LINC)** — same GIGO: the prover certifies the formula, not the parse; determinism makes the wrong answer look *more* authoritative.
- **Declarative/SMT arithmetic checking (SatLM)** — off-target for the $2M case (no arithmetic chain) and strictly dominated by ATTEST's existing D9 recompute in its own home domain.
- **Split/inductive conformal prediction** — inert without a graded score ATTEST doesn't have; delivers a *marginal* bound that is provably silent about the single high-stakes query.
- **Selective prediction / reject option (Chow; El-Yaniv)** — bounds *average* selective risk, structurally tolerating the rare confident-wrong tail; the only validated score is the overconfident softmax.
- **Risk-Controlling Prediction Sets (RCPS)** — no score to control; marginal not per-query; guarantee voids silently under the corpus-refresh distribution shift that defines the first engagement.
- **Learn-then-Test** — marginal population bound, subpopulation-blind; presupposes a labeled exchangeable calibration set that doesn't exist for a first patent engagement.
- **Conformal factuality for NLG (Mohri & Hashimoto)** — average-case bound, not per-answer; needs a runtime entailment model and a deployment-distribution calibration set that voids silently on a fresh client.
- **Temperature scaling / ECE / Brier (Guo et al.)** — ATTEST has no logits, only a self-reported scalar; Brier + reliability are *already* computed in `layer_e.py`; ECE is a biased, illegible aggregate blind to the refutation subpopulation.
- **Gödel–Löb provability logic** — category error (arithmetic provability ≠ document assertion); does no work on either layer; honest null.
- **NLI three-way (SUPPORT/REFUTE/NEI; FEVER-NLI, TRUE)** — runtime model → soft argmax replacing hard I2 abstention; its worst false-positive class (numeric insensitivity, ~43% of FPs) coincides with ATTEST's flagship case.
- **Atomic claim decomposition (FActScore)** — the legible half (atom isolation) ATTEST already does deterministically in `verify`/`frame`; the added value (LLM extractor) is the one piece ATTEST deliberately keeps off the deciding path, and it doesn't catch refutation.
- **ALCE citation precision/recall via NLI autorater** — inherits the autorater's numeric blind spot, so on the $2M case it most likely scores *entailed* (false pass), the disqualifying direction; fine as a generic Layer-E metric, not as a $2M catcher.
- **AttrScore three-way (attributable/extrapolatory/contradictory)** — a *named* "contradictory" class is not a working detector; its documented failure is labeling a contradicted numeric claim "attributable" — the exact bug, waved through; 3B model on the deciding path.
- **RARR (research-and-revise)** — a generative edit loop that rewrites the answer to retrofit attribution: revising output IS invention; non-deterministic; no real span offsets; fits no layer.
- **Deterministic contrast/refutation cue-lexicon (span-local, as pitched as a gate)** — the attribution and contrast classes over-trigger pervasively on good citations while the refutations that matter are non-span-local; survives *only* in the demoted Rung-1/Rung-2 form above (closed evaluative-denial set, measurement-first).
- **Neural RST / discourse-relation parser** — runtime model, ~60 in-domain F1 dropping 11–16pts out-of-domain; a Contrast relation marks opposition, not which pole is factual — necessary-not-sufficient even at F1=100.
- **Event-factuality / committed-belief tagging (FactBank, MegaVeridicality)** — runtime model that *defaults ambiguous complements to "asserted"* → passes the refuted figure (forbidden direction); newswire numbers don't survive a 300-page filing.
- **Negation-scope resolution (NegEx + NegBERT)** — the extended cue list that would catch "is incorrect" leaves the cue set the 84.5% number describes; scope over-extension wrongly negates good adjacent figures; NegBERT is a non-deterministic out-of-domain model.
- **Abstract/event anaphora + coreference** — a non-deterministic connector whose mis-link would fabricate a grounded *correction* citing the wrong figure (confident wrong correction); the cross-sentence link it sells is already carried deterministically by the agent-authored `Answer` atom bindings + `verify`/`frame` coverage.

---

*Bottom line for the ROADMAP: build Rung 1 (D24) — a measurement — before deciding whether Rung 2 (D25) — the one real Layer-0 guarantee available here — is worth its answer-rate cost. Everything above Rung 2 stays MEASURED at Layer-E, and the ceiling (cue-less refutation) is permanent and honest. The most valuable output of this sweep is the negative result: no clever engine closes this case, and the one deterministic win is small, one-directional, and must be earned by measurement first.*

Key grounded file references: `src/attest/verify.py` (derived-value recompute + D18/D19 relational checks, stamped TC-2 — where a Rung-2 downgrade would live), `src/attest/layer_e.py` (`brier_score`, `reliability`, `judge_entailment`, `judge_refutes_premise` — the existing Layer-E seam for Rung 3), `docs/truth_contract.md` (v1.1 monotonic rule + upgrade ratchet + the `verified ≠ entailed` non-guarantee), `golden_seed.json` (false-premise trap is arithmetic/temporal, not lexical — the reason Rung 1 is measurement-first).
