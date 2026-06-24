# ATTEST

> *An AI agent that answers questions and runs tasks over your documents where every claim is traceable to its source, it refuses to answer when the evidence isn't there, and a test suite proves it.*

ATTEST (*to bear witness; to certify as true*) is a grounded-retrieval system whose
cardinal rule is **ground or abstain — never invent.** Every assertion it makes is bound
to a verifiable source span, or it is not made; where the evidence isn't there, it returns
a structured refusal instead of a guess.

## What v1 actually guarantees

The honest, defensible claim — and it is deliberately precise:

> *Every citation points to real, verbatim, uniquely-resolvable source text, and the
> system provably abstains when retrieval finds nothing.*

That is stronger in practice than a vague "no hallucinations," because it is a promise that
can be kept and tested. The split between what is **guaranteed** and what is **measured**:

| | Deterministic — ATTEST guarantees it at runtime | A model judgment — measured offline, not enforced at runtime in v1 |
|---|---|---|
| **What** | Span resolution (quote exists verbatim, exactly once, hash-matched), retrieval, abstention *trigger* | **Entailment** — does the cited span actually *support* the claim? |
| **How** | String + hash ops, seeded; CI-gated | Scored by the eval judge (LLM-as-judge); the v2/API design pulls it inline |

So "verified" means a citation **exists and is real** — not that it *supports* the claim.
Entailment quality is a measured score, foregrounded in the eval harness, not an overclaim.

## See it run

A guided, dependency-free walkthrough over Apple's FY2024 10-K — grounded answers
with their verbatim source spans, and structured refusals that show the system
looked and where:

```bash
python demo.py          # narrated tour of seven representative questions
python attest_rig.py    # the full 20-item gate: precision, hallucination, abstention
```

The demo needs no install (pure standard library). It exercises the M0 audition
rig — the deterministic evidence layer (retrieval → cite → verify → abstain). At
M2+ the Claude Code agent drafts the prose, calling these same tools; the demo's
abstention guards are documented stand-ins for the agent's reasoning until then.

## Runtime model — v1 is a Claude Code tool, not an API service

ATTEST ships as a set of **deterministic tools** (an MCP server + a CLI mirror) that
**Claude Code invokes during a session**. The reasoner *is* the Claude Code agent; ATTEST
makes **no model calls of its own** at runtime. The agent composes prose from returned
spans; ATTEST provides the deterministic machinery plus a mandatory **verify + log** step
the agent is bound to call before presenting an answer.

Because the agent sits *above* ATTEST and calls it, ATTEST cannot structurally intercept the
agent's free text (as the deferred v2/API design would). The guarantee instead comes from
(a) deterministic tools and (b) the verify-and-log step — an honest weakening, and the
reason the eval harness measures end-to-end compliance.

The only place a model-as-judge appears is the **Layer-E eval harness**, isolated there.

## Invariants

Non-negotiable; each maps to a test in the oracle. A PR that violates one does not merge.

- **I1 — Span-level provenance.** Every asserted claim carries a verifiable pointer (`doc_id`, `char_start`, `char_end`) to a source span.
- **I2 — Abstention over fabrication.** When evidence doesn't clear threshold, emit a structured refusal, not an answer.
- **I3 — Verified immutability of source.** Documents are content-hashed at ingest; spans reference immutable offsets; any drift is a hard failure.
- **I4 — Read/write asymmetry.** The corpus is read-only to the agent. The only writable surface is the append-only audit log.
- **I5 — Append-only audit log.** Every query, retrieval set, answer, citation set, abstention, and confidence is logged immutably and replayably.
- **I6 — Deterministic evidence layer.** Same corpus + query → reproducible retrieval and span-mapping (seeded). ATTEST makes no runtime model calls, so every tool is a pure deterministic function.

## The MCP surface

The MCP server (and a CLI mirror) is the **only** interface in v1. There is no
`answer_with_citations` tool — composition is the agent's job — so the tools decompose into
*retrieve → (agent drafts) → verify → log*. Read/write asymmetry (I4) is enforced here.

| Tool | Purpose | Side effects |
|---|---|---|
| `search_corpus(query)` | Ranked candidate spans | none (read) |
| `get_span(doc_id, start, end)` | Fetch + hash-verify a span | none (read) |
| `check_support(question)` | Supporting spans or `insufficient` — the abstention decision | append to log |
| `verify(answer_with_tags)` | Confirms every cited span resolves + hash-matches; flags unbound claims | append to log |
| `check_claim(claim)` | Resolve a *user-supplied* claim to supporting spans (or none) | append to log |
| `get_audit_log(filter)` | Replay past interactions | none (read) |

## The eval harness (the hero)

The oracle splits along the runtime boundary:

- **Layer 0 — deterministic component evals** (block every PR; fast, stable). Span resolution 1:1, citation integrity (I3), retrieval recall + reproducibility (I6), abstention trigger 100% on unanswerable items, `verify` rejects planted ungrounded claims, invariant tests (I3–I6).
- **Layer E — agent end-to-end evals** (periodic, via headless Claude Code; non-blocking). Hallucination/entailment via LLM-as-judge, citation precision/recall, answer correctness, abstention correctness, and abstention **calibration** (Brier + reliability curve) — the metric almost no one measures, foregrounded here.

## Corpus

v1 reference corpus is **SEC EDGAR 10-K / 10-Q filings** (free, public, high-stakes, shareable
demo). The seed golden set ([`golden_seed.json`](golden_seed.json)) ships 20 hand-labeled
items grounded in Apple's FY2024 10-K, with a deliberate unanswerable fraction. The
corpus-specific adapter is isolated to the ingestion module — a corpus swap touches one file.

## Demo UI

A clean React/TS surface that **replays from the audit log** (no API backend in v1). Three
flows, nothing more: (1) answer with each sentence highlighting back to its source span,
(2) a pre-loaded unanswerable question that visibly shows the system refusing, and (3) an
audit panel showing retrieval + citations + confidence for the last answer.

## Status & roadmap

Single source of truth for status and sequencing is [`ROADMAP.md`](ROADMAP.md); the full
architecture, invariants, and rationale live in
[`ATTEST_build_brief.md`](ATTEST_build_brief.md).

Build order is **M0 → M5**, each milestone gated by the oracle:

- **M0** — Audition rig: prove the risky core cheaply on the 20-item seed. ✅ *gate met — `python attest_rig.py`*
- **M1** — Ingestion + retrieval + span store (immutable evidence layer). *(current)*
- **M2** — Deterministic `verify` + `check_support`; Layer-0 / Layer-E evals go live.
- **M3** — Append-only audit log (replayable; write-asymmetry enforced).
- **M4** — MCP server + CLI (the primary v1 interface).
- **M5** — Demo UI (replays from the audit log).

**v2 (do not start):** API-wrapped service with inline entailment-gating, action-taking
tools, multi-corpus, reranker upgrades, larger golden set.

## License

TBD.
