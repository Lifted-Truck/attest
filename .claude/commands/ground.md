---
description: Answer a question through the ATTEST grounded-retrieval loop, then rebuild the evidence view
argument-hint: <question>
---

Run the **ATTEST grounded-retrieval loop** for the question below, using **only the
`attest` MCP tools** (do not answer from memory or the open repo — only cited spans).

QUESTION: $ARGUMENTS

Follow the loop in `CLAUDE.md` ("Runtime agent loop"):

1. **Locate** — `check_support` / `search_corpus`; read freely with `get_span` /
   `get_document` for the context a citation needs (D11).
2. **Pick the outcome (D16, D22)** — *answer* · *abstain* (content absent / wrong
   period/entity) · **grounded correction** (the question rests on a false premise →
   present a refutation citing the contradicting span) · **partial** (answer the
   in-corpus part, explicitly flag what's out of corpus) · **refuse-to-adjudicate**
   (the question asks for a legal conclusion — novelty/validity/infringement/claim
   construction: decline it and offer the located evidence; distinct from abstain).
3. **Ground the output** — bind every load-bearing figure/date/entity to its exact
   span; derived values declare their operands, never a cited result (D9).
4. **`verify(answer, frame, outcome)` before presenting** — decompose the question
   into a typed `frame` (entity/metric/period/… constraints; implicit ones
   `required: false`) and pass it: verify returns `coverage` over the cited spans.
   **Present only if `ok` AND `coverage.complete`** — otherwise re-bind to a span
   carrying the missing constraint, or downgrade to partial/abstain. Pass `outcome`
   (`answer` / `correction` / `partial`) so the review view tags it correctly.
5. **Present** the grounded answer (or the structured refusal / correction). End with
   a line `Confidence: 0.NN`.

Then **rebuild the evidence view** for *this* answer so I can review the citations
beside the document (`--latest` keeps it to the most recent interaction; drop it for
the whole session):

```
python scripts/build_evidence_view.py --from-audit --latest
```

…and tell me to open `evidence_view.html`.
