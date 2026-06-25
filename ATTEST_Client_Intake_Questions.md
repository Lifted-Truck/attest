# ATTEST Patent Engagement — Client Intake Questions

Each question is annotated with **→** the design decision it resolves, so you can see which build choices are still open. Grouped by theme; you don't need to ask them in order. Items marked **(blocking)** gate work that can't proceed until answered.

---

## A. The patent and the objective

1. **Which patent are we working from?** (Patent or application number, or the document itself.) Is it **issued** or **pending**?
   → Determines whether prosecution history is even available and which data sources apply.

2. **What is the actual goal of the "refresh and update"?** Are you pursuing a **continuation**, a **continuation-in-part** (adding new matter), a **reissue** (correcting an issued patent), an **amendment to a pending application**, or a **standalone analysis** to inform a later decision? **(blocking)**
   → This is the single biggest fork. It decides whether the tool needs to ingest the file wrapper and which capabilities are prioritized.

3. **Is this one patent, or part of a portfolio** you eventually want covered the same way?
   → Single-document vs. multi-document topology; affects provenance and scope.

---

## B. Family, jurisdiction, and timing

4. **Are there related applications** — parents, children, provisionals, or foreign counterparts?
   → Defines the priority chain and the effective filing date that gates the prior-art universe.

5. **Which jurisdictions matter** — US only, or also EP / PCT / other offices?
   → Changes claim-drafting conventions, data sources, and family-retrieval strategy.

6. **If a reissue is in play, when was the patent granted?**
   → A broadening reissue has a limited window from grant; worth flagging as a date check (this is a logistics flag, not legal advice — confirm with counsel).

---

## C. What the update needs to cover

7. **What's driving the refresh?** New product features to protect, competitor activity, a known weakness in the current claims, or a licensing/litigation posture?
   → Shapes which capability matters most (gap analysis vs. landscape vs. support mapping).

8. **Are there specific embodiments, features, or use cases not currently claimed** that you want to bring within scope?
   → These are the candidates for the claim→spec support / new-matter analysis.

9. **Is there already a new draft or disclosure**, or are we starting from the issued patent alone?
   → Determines whether a draft-vs-original diff capability is needed.

---

## D. Prior art and landscape

10. **Do you already have a prior-art set** (an IDS, a search report, references you're aware of), or should the tool help assemble one?
    → Decides whether prior art is an ingested corpus or an out-of-scope/manual input.

11. **Is the focus patentability (what can still be claimed) or freedom-to-operate (what others hold)?**
    → Different retrieval emphasis; also reinforces where the adjudication boundary sits.

---

## E. Prosecution history

12. **Do you have access to the file wrapper**, and do you want prosecution statements (arguments made during examination, examiner amendments) surfaced as part of the reading?
    → Gates the prosecution-history ingestion module; central for reissue/amendment paths, optional otherwise.

---

## F. Outputs, workflow, and who's in the loop

13. **What deliverable do you actually want from the tool?** An annotated reading of the patent, a claim-to-specification support map, a gap analysis, a comparison against a new draft, or structured data you'll consume elsewhere?
    → Defines the output contract and the golden-dataset question categories.

14. **Who consumes the output** — the inventor, in-house counsel, or outside patent counsel?
    → Sets the register and reinforces the boundary: the tool evidences and locates; it does not render legal conclusions.

15. **Is a patent attorney or agent in the loop** on this engagement?
    → Important. The tool is designed to support a professional's judgment, not replace it; confirming this anchors the scope boundary.

16. **In what form do you want results** — a written report, annotations inside the working environment, or machine-readable structured output?
    → Output format and integration surface.

---

## G. Confidentiality and data handling

17. **Is the patent published, or is it an unpublished (confidential) application?**
    → If unpublished, it's not in any public corpus; you must supply it directly and the system must handle it as non-public. **(blocking for ingestion strategy)**

18. **Are there NDA, data-residency, or local-only handling requirements** on the documents?
    → Determines whether ingestion can touch external services or must stay local.

---

## H. Success criteria and logistics

19. **What would make this tool a success for you?** What specific decision are you trying to reach, or question trying to answer?
    → The actual acceptance criterion; everything else serves this.

20. **What's the timeline**, and in what format do you have the source documents today (PDF, USPTO XML, other)?
    → Sequencing and parser input assumptions.

---

*Notes that aren't questions but worth confirming as understandings: an issued patent can't be edited in place — any "update" is a new filing of some kind (Q2); and the tool will locate and evidence rather than opine on novelty, validity, or infringement (Q14–15). Both are reflected in the build consideration.*
