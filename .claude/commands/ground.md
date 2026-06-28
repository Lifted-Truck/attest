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
2. **Pick the outcome (D16)** — *answer* · *abstain* (content absent / wrong
   period/entity) · **grounded correction** (the question rests on a false premise →
   present a refutation citing the contradicting span) · **partial** (answer the
   in-corpus part, explicitly flag what's out of corpus).
3. **Ground the output** — bind every load-bearing figure/date/entity to its exact
   span; derived values declare their operands, never a cited result (D9).
4. **`verify(answer)` before presenting** — if `not ok`, fix the binding or abstain.
5. **Present** the grounded answer (or the structured refusal / correction). End with
   a line `Confidence: 0.NN`.

Then **rebuild the evidence view** from this session's audit log so I can review the
citations beside the document:

```
python scripts/build_evidence_view.py --from-audit
```

…and tell me to open `evidence_view.html`.
