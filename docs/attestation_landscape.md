# Attestation landscape — prior art, standards, and adjacency

> **Provenance.** Authored by a 73-agent research swarm run from the ATTEST repo on
> 2026-07-26/28 (`.claude/workflows/attestation-landscape.js`, all agents Opus 4.8), at
> Julian's request: what considerations are we missing, and whose toes are we near.
> 8 lenses (attribution literature, claim verification, provenance standards, legal/patent
> AI, enterprise grounded-RAG, IP/trademark, cautionary tales, positioning).
>
> **Methodological caveat — read this before trusting the survivor count.** 63 of 64 items
> passed the adjacency challenge. That is not validation, it is a weak challenge phase: the
> reviewer was told to reject non-adjacent items and almost never did. Treat the item list
> as a *survey*, not a filtered set. The report's own [verified]/[reported]/[unverified]
> tags are the reliable signal — prefer them to the survivor count.
>
> **Status: research input. Subordinate to ROADMAP; authorizes no work.** Its two repo
> claims were reproduced before being acted on (D37, D38). Nothing in §5 is a legal
> conclusion: infringement, validity and FTO are a licensed attorney's calls, and this
> report does not make them.

---

> **Naming note (added 2026-07-28, D40).** The product was renamed **ATTEST → Cairn**
> as a direct result of §5 of this report. This document is left **verbatim**: its
> trademark findings are factual claims about the *ATTEST* mark specifically, and a
> mechanical rename would have turned a record into fiction (a first pass produced
> "YOUCAIRN", "cosign cairn" and "askcairn.com" — all fabricated). Read every "ATTEST"
> below as the former name. The same applies to `ocr_failure_modes.md`.

---

# ATTEST Landscape Report

**Date:** 2026-07-28 · **Scope:** academic attribution/verification literature, claim-verification benchmarks, selective prediction, provenance standards, commercial legal/patent AI, enterprise grounded-RAG platforms, IP/naming.

**Reading rule for this report:** claims are marked **[verified]** (I or a surveyor read the primary source or the repo code), **[reported]** (secondary source only), or **[unverified]** (could not be confirmed — do not put in front of a client).

---

## 1. What ATTEST is that the field is not

### The differentiators that survive scrutiny

**Offsets into the SOURCE, re-checkable after the fact.** The industry converged on offsets into the *generated answer* plus a model-produced groundedness score: Google `checkGrounding` (byte positions in the answer candidate), AWS Bedrock `RetrieveAndGenerate` (`span.start/end` in the generated output), Azure `detectGroundedness` (offset/length into the LLM output). All three then score with a model. **[verified — vendor docs fetched]** Only Anthropic's Citations API ships offsets into the source document as a first-class primitive.

But Anthropic's guarantee is *generation-time and single-call*: the API extracts `cited_text` from the indices at the moment of generation, so the pointer is valid because the API built it. It cannot be re-checked later, by a third party, or against a document that may have changed. **[verified — docs line 309]** ATTEST's holds because `(doc_id, char_start, char_end)` plus a content hash can be re-verified by anyone, at any time, with no model. **That durability, not the offsets, is the pitch.**

**Determinism.** No incumbent asserts it. Every commercial groundedness check is a model call (GPT-4o, HHEM, Lynx, Luna). Clearbrief markets "non-generative" — but its patent claim recites a scorer that adds training samples in response to user actions, i.e. it retrains, so the same brief can score differently in six months **[verified — AU2022223275A1 claim 1]**. AWS markets "mathematically rigorous / provable" — but the formal claim rests on an LLM translating natural language into logic, which is why `TRANSLATION_AMBIGUOUS` is one of its finding types **[verified — AWS docs]**. ATTEST's evidence path makes no model call. That is the single loudest word available.

**Reading-time-per-citation is measurable here and structurally not elsewhere.** Char offsets make median-characters-per-citation computable from data already on disk. Document- and passage-level citation systems cannot report it. For a patent engagement where the billed deliverable is a professional's reading time, this is a differentiator sitting unused. Caveat: report it as a diagnostic, never gate on it — minimising it fights D13 coverage and D11 read-freely.

**The outcome taxonomy.** Bedrock's only presentation-layer outcome is block-vs-pass; a grounded correction and an abstention collapse into the same canned message **[verified — Guardrails docs; note the API *does* expose which policy tripped, so do not claim they are indistinguishable to a developer]**. AVeriTeC has four verdicts and no refusal class. Nobody ships `refuse-to-adjudicate` as a typed, logged outcome.

### Differentiators that are NOT differentiators — say this out loud

This is the most valuable part of the report.

- **"We cite exact character spans."** Commodity since Jan 2025 (Anthropic Citations). Dead as a headline.
- **"We abstain rather than answer wrongly."** A 55-year-old named idea with a canonical citation trail: Chow 1970, El-Yaniv & Wiener 2010, Geifman & El-Yaniv 2017, Kamath 2020. Claiming novelty invites a one-line rebuttal. The defensible claim is the conjunction — selective prediction *with* span provenance *and* a deterministic replayable layer.
- **"We check the citation is real."** Thomson Reuters filed that in 2007; US 8,201,085 B2 is live to a public-record anticipated expiry of 2030-03-05 **[verified — Google Patents]**. Reference-existence checking predates the LLM era.
- **"We decompose claims into verifiable sub-units."** ProgramFC (ACL 2023) and the whole claim-decomposition line occupy that ground.
- **"Verified ≠ entailed" is our honest innovation.** It is the field's *founding definition*. AIS (Rashkin et al., Computational Linguistics 49(4), 2023) defines attribution as explicitly NOT truth. C2PA's spec certifies assertions are "associated with the underlying asset, correctly formed, and free from tampering" and disclaims value judgments **[verified — spec text]**. AWS pairs "provable assurance" with "statements outside the scope of your policy's variables are not validated." LexisNexis was forced into the same line publicly. **This is alignment, not originality — and alignment is worth more, because it means you stop defending it from first principles and start citing it.**
- **"We do content provenance."** After the UMBC formal-methods analysis of C2PA (arXiv:2604.24890, 27 Apr 2026, 11 authors — **[verified: I fetched the abstract]**), which explicitly cautions against relying on C2PA for financial disclosures and legal evidence, a 2026 technical buyer meets "we do provenance" with skepticism. ATTEST's narrower framing is an asset in that room.

---

## 2. What we are missing — ranked

**1. Layer-E grades the verdict, not the citation.** `src/attest/layer_e.py::score_item` computes `presented = any(verify record with ok)` and `decision_correct = (presented == expected in PRESENTS)`. It never reads the golden item's `supporting[]`. **[verified — I read the code]** Every headline metric is label-only accuracy in FEVER's exact sense. For a system whose entire product claim is span provenance, the eval measures the verdict and not the provenance. FEVER's published 50.91% → 31.87% drop is the size of that illusion. `scripts/resolve_golden_quotes.py` already binds each `verbatim_quote` 1:1 to a span, so the second number is a scorer change, not a research project. Two adaptations FEVER cannot give you: match by offset overlap against a *set* of acceptable gold spans (a figure recurs across a 10-K), and extend conjunctive scoring to `abstain` (D12 `closest`) and `refuse` (D22 locate-first), which FEVER structurally cannot do.

**2. A real bug: `verify` counts figures as a set.** `unbound = sorted(salient_tokens(sent.text) - covered)` where `covered` is a `set[str]`. **[verified — verify.py:294-301, and reproduced]** "Revenue was 391,035 and total cost was 391,035." with one binding for 391,035 yields `unbound: []`. The same number can be silently re-used for a second, uncited metric. Fix: `Counter`, so N occurrences need N bindings or a declared derivation.

**3. No no-corpus control arm.** golden_seed's EDGAR items (total assets $364,980M, fiscal year end, the auditor) are near-certainly in pretraining, and G011–G015 are answerable-as-abstain from general knowledge of what a 10-K contains. Schuster et al. (EMNLP-IJCNLP 2019) is the canonical audit of exactly this. Mitigation ATTEST already has: `verify` + `coverage.complete` prevents a *fabricated* citation from priors. The residual risk is narrower — priors driving confirmation-shaped retrieval, and contamination of the two model-based Layer-E metrics (`judge_entailment` knows Apple's real figures; a memorised answer flatters Brier). Implementation is a store swap in `scripts/run_layer_e.py`. Expect the patent arm to be near-clean (US5447630A is obscure); **the EDGAR-vs-patent gap is itself the leakage measurement.**

**4. Risk–coverage curve + AURC.** `abstention_accuracy` 0.857 and `answer_rate` 0.923 are two points on one curve, tradeable by moving `support.THRESHOLD`. AURC prices the trade and cannot be gamed by moving the floor. The confidence data is already collected (`Confidence: 0.NN` → `brier_score` / `reliability`). Adapt to five outcome classes first — a naive binary RC curve scores a grounded refutation as coverage-carrying-risk. Do **not** sell a client-settable "guaranteed risk level" off 20 items; the confidence interval is wider than the claim.

**5. Three-way entailment judge.** `layer_e.judge_entailment` is binary YES/no. ATTEST has a first-class `partial` outcome and a patent posture that generates partial support by design. Zhang et al. (LLM4Eval@SIGIR 2024) find the best faithfulness metrics fail specifically at separating partial from full or none. A binary judge forces every partial into a wrong bucket — and this is the open LE-2 item ("separate agent over-claim from judge-too-strict"). *(Note: that paper's first author is given as "Jiajun Zhang" in the survey; it appears to be Weijia Zhang. **[unverified]**)*

**6. Leave-one-out citation necessity (ALCE's precision mechanism, without the NLI).** `frame.check_coverage` concatenates all cited spans into one blob and asks whether each constraint literal appears anywhere in it. A span contributing to nothing is invisible; coverage returns `complete` either way. Drop each cited span, re-run coverage; if `complete` is unchanged, that citation is load-bearing for nothing. Model-free, cheap, and it stays inside verified-≠-entailed because it tests constraint coverage, not support.

**7. `prefix`/`suffix` on `AtomBinding` (W3C TextQuoteSelector).** You already have `exact` (the binding's `text`) and the offsets. The missing pair is the standard's answer to the ambiguity your D7 resolution invariant currently handles by *refusing to build*. It bites hardest on patents, where the load-bearing literals are the maximally ambiguous ones (reference numerals "12", claim numbers, dates). It also makes a citation checkable by an attorney holding only the PDF — offsets are meaningful only inside ATTEST's canonical text. **Reject the survey's framing that a stale citation should auto-re-anchor: that is a soft-fail of I3 and a weakening under the monotonic rule.** Strictly additive; hash drift stays a hard failure.

**8. Ingest chain of custody.** `ingest_file` normalises text *then* hashes it, storing only `{"source": path.name}`. **[verified]** There is no record connecting the client's original PDF, through four-rotation union OCR, to the hashed canonical text. FRE 902(14) certification is precisely about the copy matching the original, so the untracked transform is the link a certifying professional would be asked to vouch for. This would be a hole under I3's own logic even without the rule.

**9. Metric names the market already knows.** `entailment_rate` is a house coinage. AIS/ALCE's citation-recall / citation-precision pair is the lingua franca. Report the standard names *alongside* ATTEST's finer span measure — do not rename downward and lose the granularity that is the differentiator. **Corollary risk, already shipped:** README.md:108, demo.py:110 ("100% citation precision") and the D5 ≥0.9 gate compute `n_supporting / len(cited_spans)` by literal containment of a golden string **[verified — attest_rig.py:295]**. An ALCE-literate reader will hear "an NLI model confirmed every citation entails its statement." Either state the definition inline or rename it (`gold-evidence citation precision`).

**10. Patent Background sections are untyped.** A spec describes prior approaches *in order to distinguish them*, so a cited Background span may assert the opposite of the invention. `patents.py` uses "background" only as a regex marker for where the body starts; `parse_paragraphs` emits untyped spans. Unlike everything else in the veridicality literature, this has a *deterministic structural proxy* — section membership from header offsets — so it is I6-clean and Layer-0-legal. It also corrects a wrong impression left by D24's census (zero denial cues in US5447630A reads as "no mention-not-assert risk"; the patent risk is sectional, not lexical).

**11. `¶N` labels on a granted patent.** US5447630A (1995) has no native `[0042]` numbering, so every spec citation carries a synthetic `¶N` **[verified — patents.py:75,108]**. No attorney or examiner uses that unit; granted US patents are cited column:line, and competitors pin-cite exactly that. Rendering-layer fix over existing spans; touches no invariant.

**12. Human control-group baseline.** Nothing measures how well a competent analyst does on the same items. "Human 71%, us 80%, and we abstained on the 12 where we had no evidence" is interpretable; "94% accurate" is not. *(The VLAIR numbers themselves are **[reported]** — borrow the design, not the figures.)*

**13. `check_support` conflates two different problems.** Any query below `THRESHOLD` returns `insufficient` regardless of cause: content genuinely absent (widen the corpus) vs present but below the floor (fix retrieval). Barnett et al. (CAIN 2024) failure points 1 and 2. Different client conversations, different invoices.

**14. `THRESHOLD = 15.0` is a single module-level default shared across corpora.** D20 already fits the floor from labels and stamps it into run provenance, so the survey's "tuned constant" framing is out of date — but a patent run that doesn't pass an explicit threshold silently inherits a floor fitted on 10-Ks. Kamath's off-distribution result is the argument for per-corpus defaults.

**15. Offset encoding unstated.** `docs/truth_contract.md` never says what unit `char_start`/`char_end` are. They are Python `str` indices = Unicode code points over the stored canonical text, no NFC pass. The corpus has 836 non-ASCII and zero non-BMP characters, so UTF-16 divergence is theoretical — but *byte* offsets already diverge after the first non-ASCII character, and those integers cross a JSON wire. One clause. Do not write "NFC-normalized" — that would be false, and implementing it would invalidate every stored hash.

### Explicitly rejected (so we don't re-search this)

Conformal back-off for runtime `partial` (its "get vaguer to survive" move makes claims *less* span-checkable; its scorer needs the entailment judge you keep offline — but split conformal over the Layer-E confidences you already collect is worth considering). Negation-retrieval for false premises (your one false-premise item is refuted by arithmetic in the row the question already retrieves). Cue lists including "claimed"/"alleged" (your D24 census excluded them because they are the *assertion* vocabulary of both corpora — "What is claimed is:"). Borrowing "scope concepts" as reusable frame constraints (interpretive construal; breaches verbatim coverage and locate-never-adjudicate). Merkle trees / witness networks / full RFC 9943 conformance (solves a multi-party distrust problem you don't have). C2PA soft bindings (a match that survives content change is what I3 exists to prevent). A `groundingCheckRequired`-style "this atom isn't load-bearing" flag (hands the agent a lever to exempt itself from I1). Publishing a PCC-style transparency log. Hidden-state probes (white-box access, learned classifier on the deciding path).

---

## 3. Standards to meet rather than reinvent

| Standard | What conforming buys | Cost |
|---|---|---|
| **W3C Web Annotation Data Model** §4.2.4 TextQuoteSelector | `prefix`/`suffix` on each binding → attorney-checkable with only the PDF; disambiguates non-unique quotes without D7's build-breaking error | ~2 fields on `AtomBinding` + population at bind time. Keep hash drift a hard failure. |
| **FRE 902(13)–(14)** (US, eff. 2017-12-01) | Turns I3 from an engineering invariant into a certifiable one; the rule contemplates a human "qualified person," which fits professional-in-the-loop exactly | Record and hash each ingest stage (source bytes → OCR output → canonical text); add a certification block to an export artifact. **Never** call our own output "admissible" — that is counsel's conclusion. |
| **RFC 3161 external timestamp** (the durable lesson from RFC 9162/RFC 9943, not the architectures) | The audit log currently proves a sequence is self-consistent to whoever holds the file; anyone who can edit it can recompute every hash and it verifies clean. `audit.py` reads no clock, so time is whatever the caller wrote. | One TSA token per session, recorded alongside the log. I6 untouched — logging is off the evidence path, but write that reasoning into a D-row rather than assuming it. |
| **AIS / ALCE metric names** | Buyer's technical reviewer maps instantly; house coinages read as evasion | Rename + report alongside span-level numbers. |
| **ISO/IEC 42001 + NIST AI 600-1 + EU AI Act Art. 12** | A one-page control-mapping table (I5 → Art. 12 logging/Annex IV; I1/I3 → NIST Content Provenance & Confabulation; I6 → reproducibility evidence) is the procurement artifact. Buyers will not derive it from a README. | The truth contract is already 90% of the source; only the right-hand column is missing. Do **not** pursue certification — 42001 certifies a management system, not product accuracy, and implying otherwise is the AI-washing offence. Do **not** pitch on an imminent EU high-risk deadline: the Digital Omnibus moved Annex III to 2027-12-02 **[reported]**, and a buyer who knows that discounts everything else. |

**Vocabulary to stay off, because the standards bodies now own it:** "transparency service" and "receipt" (RFC 9943), "hard binding" / "C2PA-conformant" (would also be factually false — our hash is unsigned, with no cert chain or trust list), "provable / mathematically verifiable" (AWS), "verifiable" in the AIS sense (means supported-by-the-source, which is strictly stronger than resolves-and-hash-matches).

**in-toto Statement shape:** declined as an inheritance. The subject/predicate mapping is analogical, not drop-in (your corpus digests are *inputs*, not the subject), and "verify it with cosign" imports keys, identity, and a transparency log — swapping your actual trust claim (deterministic replay) for a different one (non-repudiation by a signer). File it as a shape to consider *if* you ever build a third-party export.

---

## 4. The "verified ≠ entailed" question — direct answer

**The honest line is not a liability. Stating it only in prose is.**

Three independent bodies of evidence:

1. **The field defines it your way.** AIS's founding move is that attribution is explicitly not truth. You do not have to defend this from first principles; cite it.
2. **The strongest players state scope alongside their strongest claim, and sell more for it.** AWS ships "mathematically rigorous guarantees" and, in the same document, "a VALID result guarantees validity only for the parts of the input captured through policy variables." C2PA's spec disclaims value judgments. Both run detect-only. **[verified]** This is the direct refutation of the fear.
3. **The absolute version got the incumbent audited.** LexisNexis's "hallucination-free linked legal citations" was narrowed under pressure to a claim about the *link*, not the support — Stanford's preregistered study is the reason. Vendors who overclaim now carry priced regulatory exposure (FTC/DoNotPay $193k; FTC/Workado for advertising a 98% figure measured on academic text where real-world was ~53%; SEC's Delphia $225k / Global Predictions $175k). "Hallucination-free" is spent currency and a magnet for a hostile side-by-side.

**Where the honesty *is* a liability:** Moffatt v. Air Canada — the chatbot linked the *correct* policy page while stating the opposite in prose, and the tribunal held the deployer liable anyway; disclaiming did not discharge the duty of reasonable care **[reported, widely]**. That is the exact shape of a misgrounded ATTEST answer, and our current mitigation for it is a paragraph in the README. Two conversions:

- **Measure it.** Stanford's "misgrounded" (correct answer + real citation + citation doesn't support) is a peer-reviewed name for our gap. Publish a named misgrounding rate instead of a binary `entailment_rate`. No incumbent reports that number.
- **Gate it.** Make a recorded human disposition on each load-bearing atom a *precondition of export*, not an artifact assembled afterward. RT-5 currently records dispositions after the fact; record-after vs gate-before is the whole difference, and it is your own house rule (hooks not instructions; L0010).

**The commercial upside nobody else has:** a parametric AI warranty (Armilla at Lloyd's, Munich Re aiSure) prices a measurable, contractually defined trigger. Probabilistic accuracy is unpriceable without a claims fight; a binary deterministic hash-and-offset check is the only clause in this category an underwriter could actually price. **Scope it to what `verify()` returns, not to what gets presented** — "or the answer is not presented" is a convention of the calling agent's loop, and nothing in v1 mechanically stops an agent from presenting an unverified answer.

**Do not soften the line in response to any of this.** It is a CONFIRMS-class guardrail. Adopt the gate; leave the honesty alone.

---

## 5. Toes — factual only

**This report makes no assessment of infringement, validity, scope, likelihood of confusion, or freedom to operate. Those are a licensed attorney's calls.** What follows is what exists.

### Name

- **ATTEST**, US Reg. **6,077,675** (Ser. 88/341,385), Attest Technologies Ltd., 25 Worship Street, London EC2A 2DX. Filed 2019-03-15, registered 2020-06-16, Classes **009, 035, 042**, status Issued and Active. **[verified — one surveyor read USPTO TSDR statusview directly; a second surveyor got 403s from mirrors and reported it as an application. Treat the TSDR read as the better source, and re-pull before relying on it.]** The registrant is the consumer-research SaaS at askattest.com (founded 2015, ~$147M raised **[reported]**).
- **ATTEST**, US Reg. 6,274,194 (Ser. 88/852,595), Solventum (former 3M line), Class 005, sterilisation indicators. **[reported]**
- Also in the space: **ATTEST.COM** (Attest Systems, Inc., Ser. 75758934), **ATTESTOR** (Ser. 87453042 / Reg. 5462276, Class 042), **WORLDSPACE ATTEST** (Deque, Ser. 87402912), **YOUATTEST** (Ser. 88199778 / Reg. 6380779), **ATTESTA**, **Attestiv Inc.** (media tamper/deepfake detection — the closest commercial adjacency by function). Reg. 5958512 (Class 009, electromagnetic imaging) also surfaced. **[reported / snippet-sourced — none of these individually verified on TSDR]**
- **"attestation" as a term of art:** in-toto Attestation Framework + SLSA provenance (in-toto graduated in CNCF; note the survey's claim that sigstore is CNCF is wrong — sigstore is OpenSSF, and the graduation year is more likely 2022 than 2023); Sigstore `cosign attest` / `cosign verify-attestation`; GitHub `gh attestation verify`; RFC 9334 (RATS remote attestation); RFC 9943 (SCITT); AICPA attestation standards (AT-C); and the word appears in your own committed EDGAR corpus in the SOX 404(b) sense.
- **Namespace:** `pyproject.toml` declares `name = "attest"` with a `[project.scripts]` console entry point — the same shell namespace as `cosign attest`. Check PyPI / npm / Homebrew availability independently of the trademark question.

### Patent filings that exist in the neighbourhood

| Document | Assignee | Dates | Note |
|---|---|---|---|
| **US 12,353,469 B1** — "Verification and citation for language model outputs" | Amazon Technologies | filed/priority 2024-06-28, granted 2025-07-08 | CPC includes G06Q50/18 (legal services). Abstract-level text describes per-quantitative-data-point citation and a DB connector confirming the response matches. **Claim text not exposed on the page I fetched — claim 1 recitation is [unverified verbatim].** |
| **US 8,201,085 B2** — "Method and system for validating references" | Thomson → Camelot UK Bidco (Clarivate) | filed 2007-06-21, granted 2012-06-12, status Active, anticipated expiry 2030-03-05 | Anchors on bibliographic reference records vs an authority database, not char spans. Clarivate is commercially adjacent to a patent-refresh engagement. **[verified]** |
| **US 11,803,560 B2 / US 12,189,637 B2** (+ continuations) — "Patent claim mapping" | Black Hills IP Holdings | priority 2011-10-03; grants 2023-10-31, 2025-01-07 | Scope concepts, claim charts, claim-to-prior-art mapping. Pre-LLM. A 14-year continuation chain exists because the chart is the artifact. **[verified]** |
| **US 12,468,899 B2** — "Hallucination prevention for natural language insights" | Adobe | priority 2023-05-08, granted 2025-11-11 | Template facts → LLM prose → gatekeeper that repairs and regenerates. Opposite direction of check from ours. **[verified via Google Patents + USPTO Official Gazette]** |
| **AU 2022223275 A1** — "Auditing citations in a textual document" | Clearbrief Inc. | priority 2021-02-19, filed 2022-02-16 | Direct competitor; family likely has counterparts not enumerated. **[verified]** |
| US 12,505,299 | — | — | **[unverified lead — a differently-numbered hallucination patent, 12,505,311, surfaced in the same neighbourhood. Do not repeat this number.]** |

### The packet to hand the attorney

1. Trademark clearance on **ATTEST** and ATTEST-formatives, US/UK/EU, Classes 009, 035 and 042, including common-law use — before the name goes on any client-facing deliverable. Attach: Reg. 6,077,675 and the crowded-field list above, plus the `cosign attest` / `gh attestation verify` namespace fact.
2. FTO/prior-art read of the five patent documents above against `verify` / `check_claim` / `check_coverage` contracts. Trigger a re-read if you adopt query embeddings per `docs/rag_extension_discussion.html`.
3. Scope any chart-shaped or claim-to-prior-art-mapping deliverable *before* it is quoted to the client (Black Hills family).
4. Marketing-claims review of final public copy, with the FTC DoNotPay and Workado orders in hand.
5. The engagement-description phrasing: "patent refresh-and-update" reads as performing the professional service; "evidence-gathering for a practitioner-led patent refresh" is the safer shape. Counsel's call, not ours.

---

## 6. Cautionary tales — what a 2026 buyer already distrusts

The pattern is identical across every case: an **absolute claim** about a **narrow measured distribution**, an **independent party measures a different distribution**, and the **liability lands on the deployer** — the sanctioned attorney, the airline, the refunding consultancy.

Five suspicions to pre-empt by name:

1. **Absolute language.** Lexis+ AI's "hallucination-free" is now the headline example of overclaiming in a peer-reviewed journal (17–33% measured). Scope every claim to its mechanism.
2. **Vendor-run benchmarks.** Vals AI's Oct 2025 legal-research round ran without Thomson Reuters, LexisNexis and Harvey, who had participated in February and opted out once legal research was isolated **[reported]**. Willingness to be measured is itself the signal now. Harvey's 0.2% hallucination rate divides by *sentences*, and their own page notes they scored lowest while producing substantially more sentences than the foundation models **[verified — I fetched the blog]**. When a prospect quotes it: "per what unit, out of how many?"
3. **Numbers from one corpus.** Every ATTEST metric is a claim about the one corpus it was measured on — 20 items of an Apple 10-K, 25 items of a single patent. Workado's consent order is exactly this offence. Bind every figure inline to corpus, N and date, and start writing the corpus hash and seed into `audit_log/layer_e_results.jsonl` as the substantiation record.
4. **Pilots that never ship.** S&P Global 2025: 42% of companies abandoned most AI initiatives, up from 17% **[reported, secondary]**. **Do not cite the viral MIT NANDA "95%" figure** — it is contested and NANDA sells a competing product.
5. **Disclaimers as liability transfer.** Air Canada tried "the chatbot is a separate legal entity." It failed.

**Our own two overclaims, both already shipped:**
- `ATTEST_Patent_Tailoring_Consideration.md:6` — "the zero-hallucination oracle." **[verified]** Our own truth contract forbids that sentence and nothing caught it.
- `demo.py:110` — "100% citation precision," computed as gold-string containment. **[verified]**

**What this implies for how ATTEST demonstrates itself.** Not an accuracy number. Three artifacts:

- **A replay demo.** Re-run a dated old audit-log entry against an archived corpus hash and produce the identical span, live. No model API can do that. It is the exact demo a compliance buyer or opposing counsel asks for, and it is what makes "durability, not offsets" concrete.
- **A signable report, not an API.** Clearbrief monetises the artifact a partner signs off on and sells it as policy compliance, not accuracy. `evidence_view.html` + the hash-chained log is ~90% of that already. Under 37 CFR 11.18(b) the certification is **non-delegable**, so the sellable object is not the answer — it is the record of the inquiry. That record should include the hits the retriever surfaced and the practitioner *rejected*, and must be worded to **evidence / document / support** the inquiry, never to **satisfy** or **ensure** it. Caveat it explicitly: BM25 top-k is a ranked slice, not an exhaustive search, and a document titled "reasonable inquiry record" that implies search breadth is a liability artifact.
- **A held-out set you did not write.** Watson for Oncology looked excellent in demo because the same small group built the system and defined "correct." You currently write both the system and the exam. Have the client's patent professional author a held-out set you never see, and publish the delta. In Lexos Media (D. Kan., patent case) sanctions reached attorneys fined purely *for signing without reviewing* **[reported: $12,000 across five attorneys]** — so record which items a named human actually *opened*, not just the ones they annotated.

---

## 7. Candidate ROADMAP items

Ordered by value. Each needs its own D-row; none should open before the current gate.

| # | Item | Rationale | Revisit trigger |
|---|---|---|---|
| 1 | **Conjunctive Layer-E scoring**: report outcome-accuracy AND outcome+evidence accuracy; make the second the headline. Offset-overlap against a set of acceptable gold spans; extend to abstain/refuse evidence obligations. | A span-provenance system whose eval never checks the span. Gold quotes already resolve 1:1. | Now. Blocks any published number. |
| 2 | **Fix figure multiplicity in `verify`** (Counter, not set). | Verified bug: a figure re-used for a second uncited metric passes. | Now. Small, Layer-0-testable. |
| 3 | **Named misgrounding rate** (correct + real span + span doesn't support) replacing binary `entailment_rate`; three-way full/partial/none judge; report disagreement on the partial band. | The one number that discredited the incumbents, which no one publishes. Closes LE-2. | Now — pairs with #1. |
| 4 | **Human-disposition export gate**: no deliverable leaves the system until a named human has recorded a disposition on each load-bearing atom, including silent approvals. | Moffatt: a correct link plus wrong prose plus a disclaimer did not discharge the duty. Converts our central caveat from prose to code (L0010). | Before the first client deliverable. Sharpens RT-5/RT-7. |
| 5 | **Ingest chain of custody**: hash each stage (source bytes → OCR output → canonical text) and record the transform. | The one link a certifying professional would be asked to vouch for; the OCR stage is the most lossy and least documented. FRE 902(14). | Before the first signable export. |
| 6 | **No-corpus / decoy-store control arm.** | Nothing checks whether the agent could answer the Apple questions without the corpus. Store swap; the EDGAR-vs-patent gap is the measurement. | Now — cheap, and needed before publishing any EDGAR number. |
| 7 | **col:line rendering for granted patents** (keep `¶N` only where native `[00xx]` exists). | The live billable corpus is currently cited in a unit no attorney or examiner uses. Rendering layer over existing spans. | Before any patent deliverable. |
| 8 | **Claims register**: every buyer-facing sentence maps to a named Layer-0 test id or a numbered Layer-E result, or it does not ship. First job: kill "the zero-hallucination oracle" and define or rename "100% citation precision." | FTC substantiation standard is "competent and reliable evidence held at the time the claim is made." Determinism makes our substantiation byte-reproducible by a skeptic — almost no competitor can offer that. | Now. |
| 9 | **`prefix`/`suffix` on `AtomBinding`.** | Makes citations checkable with only the PDF; the standard's answer to the ambiguity D7 handles by refusing to build. Additive only — hash drift stays hard-fail. | With the patent evidence packet. |
| 10 | **Risk–coverage curve + AURC**, replacing the two separate headline rates. Decide where each of the five outcomes sits first. | 55-year-old standard for what I2 does; cannot be gamed by moving the floor. Label it Layer-E offline, never a runtime guarantee. | With #1. |
| 11 | **Leave-one-out coverage necessity check.** | Detects decorative citations — the first thing a patent professional notices. Model-free. | With #9. |
| 12 | **Type patent Background paragraphs.** | Prior art described in order to be distinguished; a cited Background span can assert the opposite. Section membership is structural, so I6-clean. | When the second patent enters the corpus. |
| 13 | **External RFC 3161 timestamp per session** + split `check_support`'s `insufficient` into content-absent vs below-floor + per-corpus threshold defaults. | The log proves a sequence, not a date; `insufficient` conflates two problems with different remedies; one global floor fitted on 10-Ks. | If the log will ever be shown to a third party / when the second corpus lands. |
| 14 | **Standards-mapping table + offset-encoding clause + AIS metric names + median chars-per-citation (diagnostic, never a gate).** | Procurement artifact, one missing contract clause, market vocabulary, and the one number document-level systems cannot report. | Before any procurement or analyst conversation. |
| 15 | **Preregistration**: publicly timestamp the query set, the construction procedure and the scoring rubric at a named commit *before* the next Layer-E run. Plus a client-authored held-out set. | The specific move that made the Stanford study unanswerable, and you can push it further than any vendor it audited because Layer-0 replays byte-for-byte. **Note: Layer-E itself is *not* byte-reproducible — it drives a live agent with an LLM judge. Never claim otherwise.** | Before publishing any external number. |

**Two things to explicitly not do**, because they will be re-proposed: build an entailment gate at runtime (the ~80% macro-F1 ceiling, D26 — and the judges fail hardest exactly at `partial`), and soften `verified ≠ entailed` in response to the liability material in §6. The correct response to Moffatt is item #4, not a rewrite of the truth contract.