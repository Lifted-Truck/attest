# Layer-0 deterministic gate

The **oracle's blocking half** (brief §3). Every eval here is a pure, seeded,
**deterministic** component test — *no model in the loop* (I6) — so it runs on
every push as required CI. **No merge on a red gate or a violated invariant.**
(The model-judged, end-to-end **Layer-E** evals are separate and *periodic*, not
blocking — see ROADMAP M2-T6.)

Run the gate locally:

```bash
pytest -m layer0      # the gate (equivalently: pytest, since tests/ is Layer-0)
```

Fast and deterministic by construction: the whole suite runs in well under a
second with zero network or model calls.

## Gate table

| # | Layer-0 eval (brief §3) | Guards | Test(s) | Status |
|---|---|---|---|---|
| 1 | **Span resolution 1:1** — every golden quote resolves to exactly one location; a non-unique quote hard-fails | D7 | `test_spans::test_resolution_invariant_on_golden_quotes`, `::test_duplicate_quote_fails_resolution`, `::test_missing_quote_fails_resolution` | ✅ |
| 2 | **Citation integrity** — a cited slice still matches the stored hash; tampered text/offset rejected | I3 | `test_ingest::test_tampered_*`, `test_spans::test_get_span_reverifies_doc_hash`, `test_verify::test_stale_hash_is_flagged` | ✅ |
| 3 | **Retrieval recall + reproducibility** — gold span in the candidate set; identical results across seeded runs | I6 | `test_retrieval::test_recall_on_answerable_golden`, `::test_retrieval_is_reproducible` | ✅ |
| 4 | **Abstention trigger** — content-absent question → `insufficient` (100% on that subset, D12) | I2 | `test_support::test_insufficient_on_content_absent_unanswerables` | ✅ |
| 5 | **`verify` rejects ungrounded claims** — a planted unbound/mismatched/derived-wrong atom is flagged | I1, D9 | `test_verify` (clean pass, planted-unbound, wrong-offset, derived) | ✅ |
| 6 | **Provenance binding** — `get_span` returns the exact slice; atoms bind to real offsets | I1, I3 | `test_spans::test_get_span_returns_exact_slice`, `test_verify::test_clean_answer_passes` | ✅ |
| 7 | **Plural & ranked** — multi-answer items surface all gold spans, ranked, uncollapsed | brief §4 | `test_support::test_plural_items_surface_all_gold_spans_ranked` | ✅ |
| 8 | **Deterministic ingest/normalization** — same raw → same canonical text → same hash | I3, I6 | `test_ingest::test_normalization_is_deterministic`, `test_spans::test_chunking_is_deterministic` | ✅ |
| — | **Corpus write rejected** | I4 | — | ⏳ M3 |
| — | **Audit log append-only + complete** | I5 | — | ⏳ M3 |

**M0 carryover (still gated):** `test_rig` holds the M0 audition gate (citation
precision / hallucination / abstention on the toy set); `test_toy_corpus` holds
toy-corpus integrity (sha256 + provenance + golden figures present).

## What is *not* here (by design)

Entailment — does a cited span actually *support* the claim? — is a model
judgment, **not** enforced at runtime in v1. It is measured offline by the
Layer-E judge (ROADMAP M2-T6). `verify` confirms a citation is *real and
located*, never that it *entails*. Don't let this gate's green status be read as
an entailment guarantee.
