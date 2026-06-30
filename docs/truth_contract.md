# ATTEST — the truth contract

**Version: 1.0** · governed by [`ROADMAP.md`](../ROADMAP.md) decision **D21**.

This is the single, declared statement of what ATTEST guarantees about anything it
asserts — and how each guarantee is enforced or measured. It exists so that
**epistemic rigor can be raised over time without a rewrite and without silently
breaking what past outputs promised.** When the guarantees change, *this document's
version changes*, and outputs are stamped with the version they were produced under
(see Provenance).

## The cardinal guarantee

> **Ground or abstain — never invent.** Every load-bearing claim ATTEST presents is
> bound to a verifiable source span, or it is not presented. When the evidence is
> absent or doesn't answer the question, ATTEST **abstains, corrects, or partials**
> (D16) — it does not fabricate.

Everything below is the machinery that makes that guarantee real and checkable.

## The guarantees (v1)

| Guarantee | What it promises | Enforced by | Layer | Strength (v1) |
|---|---|---|---|---|
| **I1 — span provenance** | every cited atom points to a real `(doc_id, char_start, char_end)` | `verify` atom resolver (D9) | runtime + Layer-0 | **hard** — enforced live, gated |
| **I2 — abstain over fabricate** | below the support floor → structured refusal, not an answer | `check_support` (content-absence, D12); agent reasoning for traps | runtime; Layer-0 (deterministic half); Layer-E (semantic) | **hard** for content-absence; **measured** for semantic traps |
| **I3 — verified immutability** | content-hash at ingest; any span/hash drift is a hard failure | content-hash + `verify` hash check | runtime + Layer-0 | **hard** |
| **I4 — read/write asymmetry** | the corpus is read-only; the only writable surface is the audit log | structural (only write tools hold the log) | runtime + Layer-0 | **hard** |
| **I5 — append-only audit** | every interaction logged immutably and replayably | `AuditLog` (hash-chained) | runtime + Layer-0 | **hard** |
| **I6 — deterministic evidence** | same corpus + query → reproducible results; no runtime model calls | seeded/temperature-0 evidence path | runtime + Layer-0 | **hard** |
| **Outcome honesty (D16)** | answer / abstain / **correction** / **partial** — a false premise is refuted with evidence, not silently dropped | agent + `verify(outcome=…)` | runtime; Layer-E | **hard** (present/abstain decision); **measured** (correctness) |
| **Locate-never-adjudicate (D10)** | patent domain: surface & evidence; never conclude novelty/validity/infringement/claim-construction | agent refusal class + design | runtime; Layer-E negative test | **hard** (boundary); **measured** (adherence) |

### The one deliberate non-guarantee — `verified ≠ entailed`

`verify` confirms a citation is **real and located** — *not* that the span **supports**
the claim. Entailment (does the evidence actually answer *this* question?) is
**measured offline at Layer-E**, not gated at runtime in v1. This is stated plainly
so it is never overclaimed — and it is **the frontier**: the guarantee most likely to
strengthen as research arrives (toward runtime entailment-gating; see Backlog v2).

## Layers (where a guarantee lives)

- **Runtime** — enforced on every interaction (the deterministic tools; no model calls).
- **Layer-0** — the blocking, per-commit deterministic gate (the oracle). A guarantee
  marked *hard* has a standing Layer-0 test; a red gate means *not done*.
- **Layer-E** — periodic, model-in-the-loop, **measured not gated** (entailment,
  abstention calibration, adjudication-refusal). This is where rigor is *quantified*.

## Versioning + the monotonic rule (D21)

The contract is **monotonic**: rigor may **strengthen** freely (a strengthening is a
minor version bump + a Decisions-log note). A change that would **weaken** a guarantee
is not allowed silently — it requires a **new major version**, a logged rationale, and
the oracle re-run. The Decisions log + the sacred oracle are what enforce "no quiet
weakening."

- `1.x` — additive strengthenings (new verify ops, a better calibrator, a sharper
  abstention) that don't reduce any guarantee.
- `2.0` — a structural change to what is guaranteed (e.g., entailment becomes
  runtime-gated, or a guarantee is relaxed) — logged and ratified.

## The upgrade ratchet (how new rigor is adopted)

New understanding/technology/research is adopted **behind an existing seam**, and
ships only if it passes the oracle:

> swap a component behind its interface → **the Layer-0 gate must hold** and
> **Layer-E must improve-or-hold** → otherwise it does not ship.

That is the whole forward-compatibility mechanism: ambition goes into the eval
harness; the harness decides what is real.

### The seams (today's extension points)

| Component | Seam | Upgrades it absorbs |
|---|---|---|
| retrieval | `RetrievalBackend` Protocol | embeddings, rerankers, hybrid fusion |
| support floor | `calibrate_threshold` (D20), `ATTEST_SUPPORT_THRESHOLD` | better calibration; per-corpus / per-engagement floors |
| verify math | the derived-op set (D18/D19) | new operations (kept pure, recompute-from-cited) |
| entailment | the injected judge (`ask`) | better judges; later, a formal entailment provider |
| corpus | the ingestion adapter (`edgar.py`, `patents.py`) | new corpora / domain packs |

## Provenance (TC-2 — implemented)

Every audit record carries a `provenance` block stamping the **rigor it was produced
under**, so it stays interpretable after an upgrade and rigor is **comparable across
versions**:

- `check_support` / `check_claim` → `{contract, retrieval, threshold}`
- `verify` → `{contract, verify_ops}`

`contract` is the version of *this* document ([`attest.contract.CONTRACT_VERSION`](../src/attest/contract.py)).
Replay reads the recorded floor (not the default), so a record made under a
per-engagement threshold reproduces byte-identically (I6). The evidence view renders
the line — e.g. *"truth-contract v1.0 · retrieval bm25 · floor 15 · verify-ops 1"*.
Additive and backward-compatible: records without a stamp read as pre-provenance.

The remaining seam is **entailment provenance** — stamped when a runtime entailment
method exists (today entailment is Layer-E only, recorded in the eval trend, not the
runtime record).

## The anti-trap

Forward-compatibility here is **declaration + provenance + the upgrade rule** — not a
speculative plugin framework. The seams above already exist; you formalize a new
interface (e.g. `EntailmentProvider`) **only when a second real implementation
arrives**, never preemptively. Legibility to a non-specialist remains the product.
