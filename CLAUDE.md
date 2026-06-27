# CLAUDE.md

Guidance for Claude Code working in this repository. Read this before starting any task.

## What this project is

ATTEST is a grounded-retrieval system: **ground or abstain — never invent.** Every claim is
bound to a verifiable source span or it is not made. v1 ships as **deterministic tools** (an
MCP server + CLI) that Claude Code invokes — ATTEST makes **no model calls of its own at
runtime**. See [`README.md`](README.md) for the value proposition and the precise guarantee,
and [`ATTEST_build_brief.md`](ATTEST_build_brief.md) for full architecture and rationale.

## Source-of-truth hierarchy

- [`ATTEST_build_brief.md`](ATTEST_build_brief.md) — architecture, invariants, rationale. **Wins on *design*.**
- [`ROADMAP.md`](ROADMAP.md) — status and sequencing. **Wins on *what to do next*.** When the two disagree, that split holds.
- [`golden_seed.json`](golden_seed.json) — the ground-truth eval set (20 items, Apple FY2024 10-K).
- [`ATTEST_Patent_Tailoring_Consideration.md`](ATTEST_Patent_Tailoring_Consideration.md) — patent-domain specialization for the **first client engagement**. Provisional; **subordinate to `ROADMAP.md`**. Wins on patent-domain design where it doesn't conflict.
- [`ATTEST_Client_Intake_Questions.md`](ATTEST_Client_Intake_Questions.md) — the open client decisions. Treat its unresolved items as **DO NOT INVENT** (see ROADMAP D10/§10).

## Two corpora: EDGAR (reference) + patents (client)

EDGAR 10-K is the **architecture-proving reference build** (M0–M5). The first paying
engagement is a **patent refresh-and-update** — a *specialization* of the same engine,
not a rewrite (ROADMAP **D10** + the patent track). The corpus-agnostic engine
(ingestion+hash, span store, retrieval, verify, audit log, eval harness) is shared; the
patent domain adds a richer document model, typed provenance, and structural checks.
**Patent-domain cardinal rule (sharpened from "ground or abstain"): *locate & evidence,
never adjudicate*** — never conclude on novelty, obviousness, validity, infringement, FTO,
or definitive claim construction (a patent professional is in the loop; UPL boundary).

## How to pick up work

1. Read **▶ Current focus** in [`ROADMAP.md`](ROADMAP.md). Take the topmost unchecked task in that milestone. **Read the Decisions log (D1–D14)** — they are binding; don't contradict them.
2. Implement to the task's **acceptance criteria (AC)**. State which invariants (I1–I6) it touches and how its tests cover them.
3. A milestone is `DONE` only when its **Gate** passes. Don't begin the next milestone — or **anything under Backlog (v2)** — until then.

### Working mode (single primary agent on `main`)

- **Commit directly to `main`** in small, single-purpose commits. There is **no PR gate** in this repo; CI runs on every push to `main`. If you do use a `feat/…` branch, **fast-forward merge it to `main` when done** — never leave finished work stranded on a branch.
- **Run the gate before every commit:** `ruff check . && pytest -m layer0`. **Never mask the exit code** (don't pipe `pytest` through `tail`/`head` in an `&&` chain — a failure will look like success). A red gate or violated invariant means *not done*.
- **Definition of done — do every item, every time** (a second agent skipped this and it had to be back-filled):
  1. `[x]` the task box in ROADMAP with a one-line **DONE** note (what + which tests).
  2. Append a **Changelog** line: `YYYY-MM-DD · M#-T# · short note`.
  3. Advance **▶ Current focus** to the next task.
  4. `git push` and confirm CI is green.
- **New design decisions get a new `D#` row** in the ROADMAP Decisions table with rationale. The Decisions log and the golden oracle are append-only and binding — don't quietly change behavior that a `D#` established.

## Setup, the gate, and where things live

- **Dev install:** `pip install -e ".[dev]"` (ruff + pytest). Optional MCP server: `pip install -e ".[mcp]"`.
- **The gate:** `pytest -m layer0` — the blocking Layer-0 deterministic evals ([`docs/layer0_gate.md`](docs/layer0_gate.md)); fast, seeded, **no model calls**. CI = `ruff check .` + this.
- **Scripts** run with plain `python scripts/<x>.py` from the repo root (they bootstrap `src/`). The **CLI** needs the install: `attest list` / `attest call <tool> '<json>'`.
- **Committed artifacts:** corpus at `corpus/store/` (regen: `python scripts/ingest_corpus.py`); golden quotes bound by `scripts/resolve_golden_quotes.py`; the review GUI via `python scripts/build_evidence_view.py` → `evidence_view.html`.
- **Module map** (`src/attest/`): `ingest/` = Document + content-hash (I3), `DocumentStore`, **`edgar.py` (the only corpus-specific file)**; `spans.py` = char-offset spans + resolution invariant (D7); `retrieval.py` = BM25 (I6); `support.py` = `check_support` / abstention (I2, D12); `verify.py` = atom resolver (D9/I1); `frame.py` = question frame + coverage (D13); `audit.py` = append-only log (I5); `session.py` = record/replay; `tools.py`/`cli.py`/`mcp_server.py` = the MCP+CLI surface; `evidence_view.py` = the review GUI. `attest_rig.py` (M0 audition rig) lives at the repo root.

## Invariants — non-negotiable

Each maps to a standing test. A change that violates one does not merge.

- **I1** Span-level provenance — every claim points to a real span (`doc_id`, `char_start`, `char_end`).
- **I2** Abstention over fabrication — below threshold → structured refusal, not an answer.
- **I3** Verified immutability — content-hash at ingest; any span/hash drift is a hard failure.
- **I4** Read/write asymmetry — corpus is read-only; the only writable surface is the audit log.
- **I5** Append-only audit log — every interaction logged immutably and replayably.
- **I6** Deterministic evidence layer — same corpus + query → reproducible results (seeded). No runtime model calls.

## Engineering rules

- **Determinism is law on the evidence path.** Anything touching retrieval, span-mapping, or verification runs seeded / temperature 0. Non-determinism there is a bug, not a tuning knob.
- **The oracle is sacred.** Don't weaken a gate to make a PR pass. If a gate is genuinely wrong, change it in its own PR with rationale logged in the Decisions table.
- **Invariant tests are CI, not afterthoughts.** I3/I4/I5/I6 each get a standing per-PR test from M1 onward.
- **ATTEST composes nothing in v1.** The agent drafts prose; ATTEST tools are pure deterministic functions. No `answer_with_citations` tool.
- **The corpus adapter is isolated.** All corpus-specific code lives in the ingestion module so a corpus swap touches one file.
- **"Verified" ≠ "entailed."** `verify` confirms a cited span *exists and is real*; it does not confirm the span *supports* the claim. Never let docs or output overclaim — entailment is measured offline (Layer E), not enforced at runtime in v1.

## The trap (watch for it)

The temptation will be to make ATTEST *cleverer* — esoteric retrieval, a richer ontology, a
more elegant abstraction — until it's a research project only its author can read. **Don't.**
All architectural ambition goes into the **eval harness**, where depth is the selling point.
Everywhere else, choose the boring, legible option. Legibility to a non-specialist is the
product.

## Runtime agent loop (M2+)

### Tool contracts (as built; MCP names land at M4)

| Loop role | Python (today) | Returns | Notes |
|---|---|---|---|
| locate | `retrieval.Retriever.search(q, k)` → `search_corpus` | `list[Hit{span, score}]` | deterministic, ranked (I6) |
| abstain-trigger | `support.check_support(q, retriever)` | `SupportResult{status, supporting[], closest[]}` | `insufficient` = content-absent abstain (D12) |
| read | `spans.SpanStore.get_span(doc_id, s, e)` / `get_document(doc_id)` | `str` (hash-verified, I3) | **read freely** (D11) |
| verify | `verify.verify(answer, store)` | `VerifyResult{ok, sentences[], unbound()}` | atom resolver (D9/I1) |
| *(forthcoming)* | `check_claim` (M4), `get_audit_log` (M3/M4) | — | per brief §5 |

`Answer` = `[Sentence{text, atoms:[AtomBinding{text, doc_id, char_start, char_end}], derived:[DerivedAtom]}]`.

### The loop (every session)

1. **Locate.** `check_support(question)` / `search_corpus`; **read freely** with `get_document` / `get_span` for the context a citation needs (D11) — retrieval is a navigational aid, not a cage.
2. **Abstain when unsupported (two mechanisms, D12):**
   - `check_support` → `insufficient` → **abstain**: structured refusal + the `closest` spans (show you looked, and where). *(deterministic, content-absence)*
   - Even when spans clear the floor, abstain/partial/reject by **reasoning** when the content doesn't answer *this* question — wrong period, wrong entity, false premise. *(your judgment; measured at Layer-E)* For the patent corpus this includes the **refusal-to-adjudicate** class (D10): locate & evidence, never conclude on novelty/validity/infringement/claim construction.
3. **Compose from the corpus, ground the output.** Bind each load-bearing atom (figure, date, entity) to its exact span; derived values declare operands, not a cited result (D9). The constraint is on *output*; reading is unrestricted.
4. **Plural & ranked.** When multiple defensible answers exist, return them all, ranked, each with its own evidence — never collapse to one (brief §4).
5. **`verify(answer)` before presenting.** It confirms every atom resolves at its offset + hash-matches (I1/I3), flags unbound figures, and recomputes derived values. If `not ok` → fix the binding or abstain. (`verify` confirms a citation is *real*, not that it *entails* — entailment is Layer-E.)
6. The verify/support result is appended to the audit log (I5, from M3). Present, or abstain.

## Stack (start boring on purpose)

- **Python** for ATTEST tools (MCP server + CLI), the rig, and the current GUI (a deterministic, server-less static HTML **evidence view**, `evidence_view.py`).
- **TypeScript/React** is the **M5** upgrade of that GUI (audit-log replay); not built yet — don't assume a React app exists.
- **Retrieval v1:** BM25 + a single embedding model, hybrid. Storage: sqlite (+ vector ext) or in-memory. No managed vector DB until the eval says you need it.
