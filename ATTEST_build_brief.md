# ATTEST — Build Brief

> **Codename:** ATTEST (*to bear witness; to certify as true*).
> Intellectual lineage, for your own amusement: a **critical apparatus** — the scholarly annotation layer that shows every reading's source and variants. The public-facing name stays ATTEST because the whole point of this project is legibility to a non-specialist buyer. Swap freely.

**One-line value proposition (use verbatim on the Upwork entry):**
> *An AI agent that answers questions and runs tasks over your documents where every claim is traceable to its source, it refuses to answer when the evidence isn't there, and a test suite proves it.*

---

## Runtime model — v1 is a Claude Code tool, not an API service

**v1:** ATTEST ships as a set of **deterministic tools** (an MCP server + CLI) that **Claude Code invokes during a session**. The reasoner *is* the Claude Code agent. ATTEST makes **no model calls of its own** — the only model in the loop at runtime is the agent driving the tools. (The eval harness is the one place a model-as-judge appears, isolated there.)

**v2 (later):** an API-wrapped service where ATTEST sits *between* a model and the user. Deferred.

This pivot relocates the grounding guarantee, and the relocation is the most important thing in this brief:

- In the v2/API design ATTEST **wraps** the model, so it can structurally intercept output and refuse anything ungrounded.
- As a Claude Code tool the agent sits **above** ATTEST and calls it, so ATTEST **cannot intercept** the agent's free text. The guarantee instead comes from (a) **deterministic tools** the agent calls and (b) a **mandatory `verify` + `log` step** the agent is bound to call before presenting an answer.

The honest boundary that follows — split along the determinism line:

| | Deterministic — ATTEST owns it (the real v1 guarantee) | A model judgment — NOT enforced at runtime in v1 |
|---|---|---|
| **What** | Span resolution (quote exists verbatim, exactly once, hash-matched), retrieval, abstention *trigger* (nothing over threshold → agent must abstain) | **Entailment** — does the cited span actually *support* the claim? |
| **How handled** | String + hash ops, seeded; CI-gated | Measured **offline by the eval judge** (§3), not at runtime. v2/API can pull it inline. |

So v1's provable claim is precise: *every citation points to real, verbatim, uniquely-resolvable source text, and the system provably abstains when retrieval finds nothing.* That is stronger in a pitch than a vague "no hallucinations," because it's a promise you can actually keep. Entailment quality is a measured score, not a runtime guarantee — yet.

A clean consequence: because ATTEST makes no runtime model calls, I6 (determinism) gets stricter, and the deterministic component tests become a fast, stable **per-PR CI gate**. Whole-agent end-to-end behavior ("does the agent abstain on G011?") is non-deterministic, so it runs as a **periodic eval via headless Claude Code**, not blocking CI.

---

## The two decisions you still own

Both are pre-filled with my recommended v1 defaults. Override in one line and the architecture is unaffected — these are parameters, not forks in the design.

| Decision | v1 default | Why | Override cost |
|---|---|---|---|
| **Corpus** | SEC EDGAR 10-K / 10-Q filings | Free public API, hallucination is obviously costly, strong freelance demand (analysts, IR, compliance, fintech), shareable demo with zero confidentiality risk | None structurally — ingestion adapter is the only corpus-specific module. Alternates: clinical guidelines, municipal code, regulatory text. |
| **Agency** | Read-only (retrieve + answer + verify) | Faster to ship, easier to trust, much lower eval bar | Action-taking (write/act via MCP) is a documented v2 extension; raises the oracle's burden substantially. Do not pull it into v1. |

> **Update (D10, 2026-06-25):** the **first paying engagement** retargets the corpus to a **patent
> refresh-and-update** (`ATTEST_Patent_Tailoring_Consideration.md`). EDGAR stays the reference build.
> Caveat to the Corpus row above: patents are **not** a clean one-file swap — they add a domain
> *pack* (richer document model, typed provenance, structural checks) on top of the corpus-agnostic
> engine. The patent-domain cardinal rule sharpens to **locate & evidence, never adjudicate**.

---

## §0 — Cardinal rule & invariants

**Cardinal rule:** **Ground or abstain — never invent.** Every assertion the system makes is bound to a source span, or it is not made. Outputs are evidenced; where multiple supported answers exist they are returned **plural and ranked**, never collapsed into one fabricated answer. (Direct descendant of Tonality's *reduce, never invent*.)

These are non-negotiable and each maps to a test in the oracle (§3). A PR that violates an invariant does not merge.

- **I1 — Span-level provenance.** Every asserted claim in an output carries a verifiable pointer (`doc_id`, `char_start`, `char_end`) to a source span. No claim ships without one.
- **I2 — Abstention over fabrication.** When retrieved evidence does not support an answer above threshold, the system emits a structured refusal, not a generated answer.
- **I3 — Verified immutability of source.** Ingested documents are content-hashed at ingest. Spans reference immutable offsets into the hashed text. Any drift between a cited span and the stored hash is a hard failure.
- **I4 — Read/write asymmetry.** The source corpus is read-only to the agent. The *only* writable surface in the entire system is the append-only audit log.
- **I5 — Append-only audit log.** Every query, retrieval set, composed answer, citation set, abstention, and confidence score is logged immutably, enough to replay any interaction for eval or dispute.
- **I6 — Deterministic evidence layer.** Given the same corpus + query, retrieval and span-mapping are reproducible (seeded). In v1 ATTEST makes **no model calls at all** at runtime — the reasoner is the Claude Code agent, so every ATTEST tool is a pure deterministic function and the oracle's component tests are stable by construction.

---

## §1 — Scope decomposition

Eight subsystems. Each is a branch; each merges only behind the oracle. Build order is M0→M5 (§7), not this list order.

1. **Ingestion & normalization** — corpus → cleaned text → content hash → span-indexed chunk store. Corpus-specific adapter lives *only* here.
2. **Retrieval layer** — query → ranked candidate spans with offsets. Hybrid (lexical + dense); deliberately simple in v1.
3. **Answer verification + abstention (deterministic)** — the agent composes; ATTEST provides a `verify` tool that resolves every cited span and a deterministic abstention *trigger*. ATTEST does not compose prose in v1.
4. **Provenance binding** — maps each output sentence → span id(s); enforces I1; rejects any unbound assertion before it reaches the user.
5. **Audit log** — append-only, replayable (I5).
6. **Eval harness (the hero)** — §3. This is the portfolio asset; give it disproportionate care.
7. **Demo UI** — the conversion surface; span-highlight + abstention + audit panel.
8. **MCP server** — exposes the agent's tools with read/write asymmetry enforced at the tool boundary.

---

## §2 — Audition rig first

Before any of the real build, prove the one genuinely risky thing cheaply, the way `springlab.py` / the Curvature rig did. **Do not build subsystems 1–8 until the rig clears.**

**`attest_rig.py`** (single script / notebook):
- ~1 tiny doc set (5–10 filings or excerpts).
- ~20 hand-labeled golden items in the **quote + locator** schema (see `golden_seed.json`, which already exists): each is `{question, expected_answer, supporting:[{locator, verbatim_quote}], answerable, difficulty}`. Include **at least 5 deliberately unanswerable** questions — the corpus genuinely doesn't contain the answer. (Schema note: spans are referenced by verbatim quote + locator, not by span IDs, because span IDs/offsets don't exist until M1 — see §3.)
- Dead-simple retrieval (BM25 or a single embedding call — no infra).
- The answer-with-citations prompt + the abstention path.
- Metrics computed inline by hand (§3 definitions).

**Gate to proceed:** on the toy set, citation precision is high, hallucination rate is ~0 on answerable items, and the rig **abstains correctly on every unanswerable item**. If it can't do that on 20 hand-picked questions, the full build won't save it — iterate the prompt/retrieval in the rig until it does. This rig is also your first eval fixture; it grows into the golden set.

---

## §3 — The oracle (eval harness) — the hero

The oracle now splits along the runtime boundary (see Runtime model, above): **deterministic component evals** that block CI, and **agent end-to-end evals** that run periodically via headless Claude Code.

### Layer 0 — deterministic component evals (block the PR; fast, stable)
These test ATTEST's pure-function tools directly, no agent in the loop:
- **Span resolution** — every golden `verbatim_quote` resolves to exactly one location in the canonical text (resolution invariant); a planted near-duplicate quote fails correctly.
- **Citation integrity** — a cited span's slice still matches the stored hash (I3); a tampered offset is rejected.
- **Retrieval recall** — for answerable items, the gold span appears in the candidate set; reproducible across two seeded runs (I6).
- **Abstention trigger** — on unanswerable items, no candidate clears threshold → the tool returns `insufficient` (100% required; the strongest selling point).
- **`verify` rejects ungrounded claims** — feed it an answer containing a claim bound to no valid span; it must flag it.
- **Invariant tests** — I4 (corpus write rejected), I5 (log append-only + complete).

### Layer E — agent end-to-end evals (periodic; via headless Claude Code, non-blocking)
Run the actual Claude Code agent + ATTEST tools over the golden set in print/headless mode and score the transcript:
- **Hallucination rate** — asserted claims whose cited span doesn't *entail* them (LLM-as-judge; this is the entailment check that v1 does **not** enforce at runtime). Target 0 per the D4 policy (judge flags adjudicated; false positives logged, don't count).
- **Citation precision / recall**, **answer correctness** (judge vs `expected_answer`).
- **Abstention correctness** end-to-end — did the agent actually abstain on unanswerable items / reject false premises?
- **Abstention calibration** — Brier + reliability curve over the agent's stated confidence. *The metric almost no freelancer measures; foreground it.*

Persist every run's scores to a results file. A graph of "hallucination held at 0 across N runs" plus "100% deterministic abstention-trigger" is worth more in a pitch than prose.

### Golden dataset schema
Spans are referenced by **verbatim quote + locator**, not span IDs — span IDs and char offsets don't exist until M1 builds the store and they depend on M1 normalization. A resolver at M1 binds `verbatim_quote → span_id` and **must find each quote exactly once** in the canonical text, else hard-fail (the *resolution invariant*).
```
{
  "id": "...",
  "question": "...",
  "answerable": true|false,
  "expected_answer": "...",                 // null if unanswerable
  "expected_behavior": "abstain | reject-false-premise | partial-abstain",  // for non-answerable cases
  "supporting": [                            // empty list == unanswerable
    { "locator": "doc · section · line", "verbatim_quote": null }  // quote filled + resolved at M1
  ],
  "difficulty": "easy|medium|hard",
  "tests": [ "numeric-exact", "plural-and-ranked", ... ]
}
```
Seed (`golden_seed.json`) ships 20 items grounded in Apple's FY2024 10-K. Grow toward 40–80, keeping a healthy unanswerable fraction.

---

## §4 — Provenance & abstention mechanics

In v1 the **Claude Code agent composes**; ATTEST provides the deterministic machinery and the verify-and-log step that re-imposes the guarantee (see Runtime model).

- **Span binding (deterministic).** Retrieval returns spans as `(doc_id, char_start, char_end, text, hash_of_doc)`. The agent is instructed (via the tool contracts + a project `CLAUDE.md`) to compose only from returned spans and tag each sentence with the span id(s) it rests on. Before presenting, the agent calls **`verify(answer)`**, which deterministically confirms each tagged span resolves to a live, hash-matched slice (I1, I3) and flags any sentence with no valid binding. The verification result is logged (I5). The guarantee is *verified-and-logged*, not structurally intercepted — an honest weakening from the v2/API design, and the reason Layer-E exists to measure end-to-end compliance.
- **Entailment is out of scope at runtime.** `verify` confirms a cited span *exists and is real*; it does not confirm the span *supports* the claim — that's a model judgment, scored offline by the Layer-E judge. Say this plainly in the README; don't let "verified" overclaim.
- **Abstention trigger (deterministic).** If no retrieved span clears the relevance threshold, the support tool returns `insufficient`; the agent is bound to emit a structured refusal plus the closest spans it did find (so the user sees it looked, and where). Refusal is a first-class, logged outcome — not an error.
- **Plural & ranked.** When the corpus supports more than one defensible answer (different periods, segments, restatements — see golden items G007/G008), return them as a ranked list, each with its own evidence and the ranking basis stated. Never silently pick one.

---

## §5 — MCP surface

The MCP server (plus a CLI mirror) is the **primary and only** interface in v1 — it's how Claude Code reaches ATTEST. No `answer_with_citations` tool: composition is the agent's job, so the tools decompose into retrieve → (agent drafts) → verify → log. Read/write asymmetry (I4) is enforced at this boundary: read tools have no side effects; only verify/check/log append to the audit log.

| Tool | Purpose | Deterministic? | Side effects |
|---|---|---|---|
| `search_corpus(query)` | Ranked candidate spans | yes | none (read) |
| `get_span(doc_id, start, end)` | Fetch + hash-verify a span | yes | none (read) |
| `check_support(question)` | Returns supporting spans or `insufficient` — the abstention decision | yes | append to log |
| `verify(answer_with_tags)` | Confirms every cited span resolves + hash-matches; flags unbound claims | yes | append to log |
| `check_claim(claim)` | Resolve a *user-supplied* claim to supporting spans (or none) | yes (resolution); entailment left to agent/judge | append to log |
| `get_audit_log(filter)` | Replay past interactions | yes | none (read) |

`check_claim` is worth highlighting separately in the portfolio — "paste a sentence, find out if your own documents actually back it" is an instantly graspable client demo. A project `CLAUDE.md` documents the required loop (search → draft from spans only → `check_support` → `verify` → present-or-abstain) so the agent follows it every session.

Both `verify` and `check_claim` share one deterministic primitive — an **atom resolver** (ROADMAP **D9**): the agent decomposes its answer into load-bearing atoms (numbers, dates, named entities), binds each to a specific `(doc_id, content_hash, char_start, char_end)`, and the resolver confirms the slice at that offset equals the atom *exactly*, hash-matches (I3), and sits within the query's retrieved scope. The agent **parameterizes** the check (supplies atoms + bindings); it never **authors** it. `verify` independently re-extracts atoms from the final answer so an untagged figure can't slip through. This kills *invented* citations; it does **not** confirm entailment (existence ≠ support — measured offline at Layer-E, structural in v2). Open implementation contingencies live under ROADMAP M2-T1.

---

## §6 — Demo UI (the conversion surface)

Clean React/TS (your Audiology muscle). In v1 there's no API backend serving answers — so the demo **replays from the audit log** (I5): the agent runs a session over the tools, everything is logged, and the UI visualizes logged interactions. It exists to make a non-technical buyer *get it in one glance*. The **layout is two-pane** — canonical document beside the answer — and references are **click-to-source hyperlinks**. (See ROADMAP **D8**: a server-less static-HTML version of this view ships early, at **M2-T7**, the moment `verify` exists; M5 is its polished, log-replaying upgrade. The contract — agent tags sentences with `span_id`s → `verify` → `log` → deterministic render — keeps every hyperlink a *verified* span reference, never a hand-authored link.) Three things, nothing more in v1:
1. Ask a question → the answer renders with **each sentence highlighting back to its source span** on click/hover.
2. A pre-loaded **deliberately unanswerable** question whose answer is the system refusing — show the abstention, don't hide it.
3. An **audit panel** the user can open to see retrieval + citations + confidence for the last answer.

Resist adding a fourth feature. Legibility is the product here.

---

## §7 — ROADMAP.md & workflow

`ROADMAP.md` is the single source of truth (Tonality convention). A Claude Code agent leads development via branch-per-subsystem and PRs; **every PR is gated by the Layer-0 deterministic component evals (§3)**; no merge on a red gate or a violated invariant. Layer-E agent evals run periodically, not per-PR.

- **M0 — Audition rig** (§2). Gate: rig clears on the 20-item seed.
- **M1 — Ingestion + retrieval + span store** (I3 live). Gate: span hashes verify; resolver binds golden quotes 1:1; retrieval reproducible (I6).
- **M2 — Deterministic verify + abstention tools** (I1, I2). Gate: Layer-0 component evals pass on the golden set.
- **M3 — Audit log** (I4, I5). Gate: append-only + full-replay tests pass.
- **M4 — MCP server + CLI** (primary v1 interface; can land as early as needed). Gate: read/write asymmetry test; the agent loop runs end-to-end over the tools.
- **M5 — Demo UI** (replays from the audit log). Gate: the three demo flows work on EDGAR.

v2 backlog (do not start in v1): API-wrapped service with inline entailment-gating, action-taking tools, multi-corpus, hybrid rerankers, larger golden set.

---

## §8 — Stack notes (start boring on purpose)

- **Language:** Python for ATTEST tools (MCP server + CLI) and the rig; TypeScript/React for the demo.
- **Runtime:** Claude Code is the reasoner and the host. ATTEST ships as an **MCP server + CLI** with **no model calls of its own in v1** (I6). The only model-as-judge lives in the Layer-E eval harness and can be a scripted **headless Claude Code** invocation, isolated there.
- **Retrieval v1:** BM25 + a single embedding model, hybrid. Storage: sqlite + a vector extension, or even in-memory for v1. No Pinecone/Weaviate until the eval says you need it.
- **Corpus adapter:** EDGAR full-text + filing fetch, isolated in the ingestion module so a corpus swap touches one file.

---

## §9 — Anti-goals & the one trap

- **Read-only in v1.** Acting is v2.
- **One corpus.** Variants are your gig pipeline *after* the reference build ships, not a v1 feature.
- **The trap (named explicitly so the agent and you both watch for it):** the temptation, given how you're wired, will be to make ATTEST *cleverer* — esoteric retrieval, a richer ontology, a more elegant abstraction — until it's a research project only you can read. **Don't.** All architectural ambition goes into the **eval harness (§3)**, where depth is the selling point and legibility is unharmed. Everywhere else, choose the boring, legible option.

---

*End of brief. Hand to Claude Code at M0.*
