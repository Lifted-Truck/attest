# ATTEST — Patent-Domain Tailoring
## Design Consideration for the Build Agent

**Status:** Provisional / v0.1. Expect refinement as client details emerge (see §10 and the companion `ATTEST_Client_Intake_Questions.md`). Subordinate to `ROADMAP.md`: where this document conflicts with the roadmap, the roadmap governs until the two are reconciled.

**Context:** ATTEST's first corpus was SEC EDGAR 10-K/10-Q. This document retargets the system for a single patent *refresh-and-update* engagement. It does **not** replace the core architecture — provenance-first retrieval, the zero-hallucination oracle, and the two-layer eval stack (Layer-0 deterministic / CI-blocking + Layer-E agent end-to-end). It specializes that architecture for the patent domain.

---

### 1. Domain thesis (read this first)

Three shifts distinguish a patent from a financial filing. Internalize them before implementing anything; they justify every requirement below.

1. **The claims are the operative unit.** In a 10-K the meaningful content is prose to be retrieved and grounded. In a patent the claims are the legally controlling text; nearly every useful operation traces relationships *into or out of* the claims rather than summarizing prose.
2. **The provenance graph becomes internal and typed.** It is no longer "source citation → assertion." It is a graph of typed edges within and across the document: claim term → specification support → figure → reference numeral, plus a priority/prosecution dimension that lives outside the document body.
3. **The topology is multi-document.** A refresh involves the base patent, its family/priority chain, (often) its prosecution history, a prior-art set, and possibly a new draft. This is a different retrieval topology than the single-10-K anchor, and provenance must carry document identity so answers never silently conflate members of the set.

---

### 2. Scope boundary — the adjudication line (NORMATIVE)

This is the single most important constraint and supersedes any helpfulness heuristic.

- The system **MUST** retrieve, locate, and evidence.
- The system **MUST NOT** adjudicate. Specifically, it must not assert or conclude on: novelty, obviousness, patentability, validity, infringement, freedom-to-operate, or definitive claim construction.
- In-scope example: *"The term 'thermal regulator' in claim 1 is described at [0042]–[0044] and shown in Fig. 3 as element 104."*
- Out-of-scope example: *"Claim 1 is novel over reference X"* / *"Claim 1 is invalid for lack of written description."*
- **Assume a patent professional (attorney or agent) is in the loop.** The tool supports their judgment; it does not substitute for it. This is both an epistemic-integrity commitment and an unauthorized-practice-of-law boundary.
- Encode the boundary as an explicit **refusal class** in the agent loop and as **negative evals** in Layer-E (the system is penalized for producing an adjudicative conclusion even when the user requests one).

The roadmap's cardinal discipline carries over, sharpened: **locate and evidence, never adjudicate** (the patent-domain form of "reduce, never invent").

---

### 3. Document model & addressability (requirements)

The parser **MUST** produce these as first-class, individually addressable objects:

- **Claims** as discrete objects, each tagged independent vs. dependent, with parsed dependency edges (`claim 7 depends_on claim 1`), and each decomposable into its limitations/elements.
- **Specification paragraphs** addressed by their native numbering (`[0001]`, `[0042]`). Paragraph numbers — not page numbers — are the citation unit.
- **Reference numerals** extracted and bound to (a) the figure(s) in which they appear and (b) their first and subsequent textual mentions.
- **Front-matter / bibliographic fields**: title, inventors, assignee, application & publication numbers, filing/priority/grant dates, classification codes (CPC/IPC), references cited (applicant- and examiner-cited, distinguished).
- **Priority chain**: every priority claim and its date (provisional, parent, foreign).
- **Prosecution history** (file wrapper): office actions, applicant responses, examiner amendments, IDS filings — **conditional on mechanism (see §9); do not build until the mechanism is confirmed.**

---

### 4. Provenance model changes (requirements)

- Replace the single source-citation edge with **typed internal edges**, minimally: `CLAIM_TERM→SPEC_SUPPORT`, `SPEC→FIGURE`, `NUMERAL→ELEMENT`, `CLAIM→PARENT_CLAIM`, `APPLICATION→PRIORITY_DOC`.
- Every provenance record **MUST** carry a **document-identity field** (which member of the family/chain/prior-art set it resolves to).
- Cross-document retrieval **MUST NOT** merge or conflate sources; an answer spanning two documents must keep their provenance distinct and labeled.
- The append-only annotation / verified-immutability model from the earlier `patent_reader` work is the right substrate here; reuse it rather than reinventing.

---

### 5. Deterministic structural checks → Layer-0 evals

These four checks are purely structural, have deterministic ground truth, and are exactly the failure modes a refresh introduces. They are high-value, CI-blocking, and require no model in the loop.

1. **Antecedent basis** — every `the X` / `said X` must have a prior `a X` in the same claim chain (§112(b) failure mode).
2. **Claim dependency integrity** — no dependent claim references a non-existent claim or violates multiple-dependency rules.
3. **Element-numeral consistency** — numerals in figures appear in the spec and vice versa; one numeral never names two different elements.
4. **Term-usage consistency** — claim terms appear in the specification (a coarse written-description tripwire).

Implement these as Layer-0 evals with fixtures drawn from the actual engagement patent.

---

### 6. Core retrieval capabilities

**6.1 Claim → specification support mapping (the primary capability).**
For each claim limitation, retrieve the supporting specification passages. Output **MUST** be ranked, plural, and evidenced (paragraph- and figure-level provenance). This is the §112 written-description/enablement question rendered as grounded retrieval. **Gaps in support are the actionable signal** for the refresh: an unsupported limitation is where new matter would be required (i.e., the difference between a continuation and a continuation-in-part). The tool surfaces the gap; it does not conclude that support is legally insufficient (see §2).

**6.2 Priority chain → effective filing date → prior-art cutoff.**
Extract priority claims and dates, compute the effective filing date, and flag the governing regime (pre-AIA vs. AIA). This date gates the entire prior-art universe for the refresh, so it warrants its own extractor and its own golden-dataset entries.

---

### 7. Data sources & ingestion

*Verified June 2026; this landscape is actively migrating — re-confirm endpoints before relying on them.*

- **Prosecution history / file wrapper:** USPTO **Open Data Portal (ODP)** at `data.uspto.gov`. PEDS has been retired; its data now lives under the **Patent File Wrapper** feature. The documents endpoint (`api.uspto.gov/api/v1/patent/applications/{appNumber}/documents`) covers published applications and issued patents filed after 2001-01-01, refreshed daily. **An ODP account + API key is required**, and account-field requirements tightened in 2026 — provision credentials early.
- **Corpus full-text:** ODP Bulk Data Directory.
- **Family / landscape:** Google Patents and EPO OPS for family members and counterparts.
- **Confidentiality branch:** if the engagement patent is an **unpublished** application, it is confidential and **will not be in any public corpus**. The client must supply it directly, and the system must treat it as non-public (see §G of the intake questions and §10 below).
- If the earlier `patent_reader` MCP package wrapped any USPTO endpoints, audit them against ODP — the legacy Developer Hub was decommissioned in June 2026.

---

### 8. Golden dataset guidance

Mirror the Apple-FY2024-10-K methodology, anchored in the **actual patent being refreshed**. Seed with deterministic, checkable Q&A across these categories:

- Counts & structure: independent-claim count, total-claim count, dependency tree.
- Dates: priority date, effective filing date, regime flag.
- Support mapping: "which paragraphs support term *T* in claim *N*."
- Figure/numeral: "all numerals in Fig. *k* with their first textual mention."
- Negative/boundary: a question whose only correct response is a refusal-to-adjudicate (anchors the §2 boundary in Layer-E).

---

### 9. Mechanism-dependent branches (DEFERRED — do not build until confirmed)

"Refresh and update" maps to legally distinct mechanisms with different document needs. The mechanism is **not yet confirmed** (see intake questions §A). Build the mechanism-agnostic core (§§3–6, 8) first; defer the following:

- **Continuation / continuation-in-part** → emphasis on prior-art landscape since the priority date and on claim→spec support mapping (to distinguish supported scope from new matter).
- **Reissue (35 U.S.C. § 251)** → prosecution-history ingestion becomes first-class (recapture, estoppel); broadening reissue has a two-year-from-grant window worth surfacing as a date check.
- **Amending a pending application** → prosecution-history ingestion (office actions, responses) is central.

---

### 10. Open decisions — DO NOT INVENT

The agent **MUST** treat the following as unresolved and **MUST NOT** assume defaults. Where a decision blocks progress, surface it rather than guessing; route to the client questionnaire.

1. The refresh mechanism (§9) — gates prosecution-history ingestion.
2. Jurisdiction(s) — US-only vs. EP/PCT/other (changes claim conventions and data sources).
3. Whether the patent is published or confidential (§7) — gates corpus strategy and data handling.
4. Whether a prior-art set is supplied vs. to be assembled.
5. The consuming audience and required output format (report / in-Claude-Code annotations / structured data).
6. Single patent vs. portfolio.

---

### 11. Recommended build order (given current unknowns)

1. Document model & addressability for a single base patent (§3, minus prosecution history).
2. The four Layer-0 structural checks (§5).
3. Claim → spec support mapping + provenance typing (§§4, 6.1).
4. Priority-chain / effective-filing-date extractor (§6.2).
5. Golden dataset seeded from the engagement patent (§8).
6. *Pause for client input* → then mechanism-specific layer (§9) and multi-document / prior-art topology.

Steps 1–5 are mechanism-agnostic and confidentiality-agnostic; they can proceed in parallel with client intake.
