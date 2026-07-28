export const meta = {
  name: 'attestation-landscape',
  description: 'Survey attestation/grounded-citation prior art: academic, commercial, standards, and IP toes',
  whenToUse: 'Before committing to ATTEST\'s positioning, naming, or claim language — find what already exists and whose toes are nearby.',
  phases: [
    { title: 'Survey', detail: '8 lenses across research, products, standards, IP (Opus 4.8)' },
    { title: 'Challenge', detail: 'hostile check: is this actually adjacent to ATTEST? (Opus 4.8)' },
    { title: 'Position', detail: 'synthesis: gaps, overlaps, risks (Opus 4.8)' },
  ],
}

// Motivation: ATTEST is heading toward a first paying engagement and a public-facing
// identity. Two questions the owner asked, which are NOT the same question:
//   (1) what considerations are we missing that this field already knows?
//   (2) whose toes are we near — IP, trademark, standards, or a competitor's claim?
// A swarm is the right shape because the answer spans four disjoint literatures that
// no single search sweep covers.

const ATTEST = `
WHAT ATTEST IS (judge every finding against this, not against a generic RAG system):
· A grounded-retrieval system. Cardinal rule: "ground or abstain — never invent." Every
  claim binds to a verifiable source span (doc_id + char offsets) or is not made.
· Ships as DETERMINISTIC TOOLS (MCP server + CLI) that an agent calls. ATTEST itself makes
  NO model calls at runtime. Same corpus + query -> byte-identical results, seeded.
· Deliberately does NOT do entailment at runtime. "verify" confirms a cited span EXISTS
  and hash-matches; it does not confirm the span SUPPORTS the claim. Entailment is
  measured offline in a behavioral eval layer, never enforced as a runtime guarantee.
  This distinction ("verified != entailed") is treated as load-bearing honesty, not a
  limitation to engineer away.
· Invariants: span-level provenance; abstain over fabricate; content-hash immutability;
  read-only corpus with an append-only hash-chained audit log; deterministic evidence layer.
· Five outcome classes: answer / abstain / correction (grounded refutation of a false
  premise) / partial / refuse-to-adjudicate.
· First engagement is a PATENT refresh. Cardinal rule there: "locate & evidence, never
  adjudicate" — never conclude on novelty, obviousness, validity, infringement, or claim
  construction. A patent professional is in the loop (UPL boundary).
· Small, boring-on-purpose stack. Legibility to a non-specialist is treated as the product.
`

const FINDINGS = {
  type: 'object',
  required: ['lens', 'items', 'sources'],
  properties: {
    lens: { type: 'string' },
    items: {
      type: 'array',
      items: {
        type: 'object',
        required: ['name', 'what_it_is', 'relation_to_attest', 'what_attest_could_learn',
                   'collision_risk', 'evidence'],
        properties: {
          name: { type: 'string', description: 'system, paper, standard, company, or filing — be specific and real' },
          what_it_is: { type: 'string' },
          relation_to_attest: { type: 'string', enum: ['same-problem', 'adjacent', 'upstream-dependency', 'competitor', 'standard-we-should-meet', 'cautionary-tale'] },
          what_attest_could_learn: { type: 'string', description: 'concrete: a mechanism, a metric, a failure they hit' },
          collision_risk: { type: 'string', description: 'naming/trademark/IP/positioning overlap, or "none". Describe the overlap factually; do NOT opine on infringement or validity.' },
          evidence: { type: 'string', description: 'paper + venue + year, product URL, filing number, or standard id. Never invent one.' },
        },
      },
    },
    sources: { type: 'array', items: { type: 'string' } },
  },
}

const VERDICT = {
  type: 'object',
  required: ['item', 'genuinely_adjacent', 'why', 'action'],
  properties: {
    item: { type: 'string' },
    genuinely_adjacent: { type: 'boolean' },
    why: { type: 'string' },
    action: { type: 'string', enum: ['adopt-idea', 'meet-standard', 'differentiate-from', 'watch', 'legal-review', 'ignore'] },
    one_line_for_owner: { type: 'string' },
  },
}

const LENSES = [
  { key: 'attribution', prompt: `ACADEMIC — ATTRIBUTED / GROUNDED GENERATION. The literature on citation-bearing QA and attribution: RARR, ALCE, AIS (Attributable to Identified Sources), self-citation, retrieve-then-read with provenance, "citation faithfulness" and its metrics. What are the established EVALUATION constructs, and what does the field consider solved vs open? Pay attention to anything that bears on ATTEST's deliberate refusal to do runtime entailment — has the field concluded that span-existence checking without entailment is worthless, or is the separation recognised?` },
  { key: 'verification', prompt: `ACADEMIC — CLAIM VERIFICATION & FACT-CHECKING SYSTEMS. FEVER and successors, SciFact, evidence retrieval + stance/veridicality classification, abstention and selective prediction, calibration, "I don't know" as a first-class output. What is known about the ceiling of DETERMINISTIC (non-model) evidence checks, and about the cost of abstention to user trust? Include the selective-prediction / risk-coverage literature.` },
  { key: 'provenance', prompt: `STANDARDS & PROVENANCE INFRASTRUCTURE. C2PA / Content Credentials, W3C PROV, in-toto and SLSA (software attestation — note the NAME COLLISION risk with "attestation"), remote attestation / TPM / confidential computing, signed manifests, transparency logs (Certificate Transparency, Sigstore/Rekor). ATTEST uses an append-only hash-chained audit log — how does that compare to what these standards specify, and is there a standard it should simply MEET rather than reinvent? Be explicit about how loaded the word "attestation" already is in security/computing.` },
  { key: 'legaltech', prompt: `COMMERCIAL — LEGAL & PATENT AI. Harvey, Casetext CoCounsel, Hebbia, Luminance, Robin AI, Patlytics, Edge/PatSnap/Questel/Clarivate/IPRally, Solve Intelligence, and patent-prosecution copilots. Specifically: what do they claim about citation accuracy and hallucination, how do they handle the UPL / "not legal advice" boundary, and what has publicly gone WRONG (sanctions for fabricated citations, the Stanford RegLab hallucination study of legal research tools)? What does a patent professional actually get sold today for a refresh/update task?` },
  { key: 'enterprise', prompt: `COMMERCIAL — ENTERPRISE GROUNDED RAG & CITATION PRODUCTS. Vertex AI grounding + check-grounding API, Azure AI Search / "groundedness detection", Bedrock Knowledge Bases + Guardrails contextual grounding, Vectara's Hughes Hallucination Evaluation Model and factual-consistency score, Elastic/Glean/Perplexity citation surfaces, Galileo/Arize/Patronus evaluation vendors. Which of these do span-level provenance vs document-level? Which make a DETERMINISTIC claim? Does anything already ship "the citation is verified to exist at these offsets" as a product primitive?` },
  { key: 'ip', prompt: `IP LANDSCAPE — the "whose toes" question. Search granted patents and published applications around: grounded generation with source attribution, citation verification, hallucination detection, provenance-tracked retrieval, span-level source binding, audit logs for AI outputs. Note assignees (the big labs, IBM, legal-tech incumbents) and filing dates. ALSO trademark: "ATTEST" / "Attest" as a mark — there is a known UK market-research company called Attest, and "attestation" is heavily used in security. REPORT FACTUALLY: name filings, classes, and owners. Do NOT assess validity, infringement, or freedom-to-operate — that is a licensed professional's call and out of scope for this report. Flag what a professional should look at.` },
  { key: 'failures', prompt: `CAUTIONARY TALES — where similar products died or damaged trust. AI legal-research tools that fabricated citations and the sanctions that followed; IBM Watson for Oncology; Zillow Offers; enterprise RAG pilots that failed to reach production and the published post-mortems on why; "demo-to-deployment" gaps; the specific failure of tools that over-claimed accuracy. What is the pattern, and what would a buyer in 2026 be ALREADY SUSPICIOUS of when a new grounded-retrieval vendor walks in?` },
  { key: 'positioning', prompt: `POSITIONING & BUYER FRAME. How is this category named and sold — "grounded AI", "verifiable AI", "provenance", "AI assurance", "trustworthy retrieval"? What do analysts (Gartner/Forrester) call it? What regulatory pressure creates budget (EU AI Act transparency obligations, NIST AI RMF, sector rules for legal/finance)? What evidence do buyers demand — benchmarks, audits, certifications, insurance? And: is there an established buyer expectation that ATTEST's honest "verified != entailed" line will read as a WEAKNESS against competitors who over-claim, and how have others handled that?` },
]

phase('Survey')
log(`Surveying ${LENSES.length} lenses: research, products, standards, IP…`)

const surveyed = await parallel(LENSES.map(l => () =>
  agent(
    `You are researching the landscape around ATTEST for its owner, ahead of a first
paying engagement and possible public positioning. Search the web extensively. Cite
real papers (authors/venue/year), real products, real filings, real standard ids.
NEVER invent a citation, a patent number, or a company — an unverifiable item is worse
than a missing one. If you are unsure a thing exists, say so in the evidence field.

${ATTEST}

YOUR LENS: ${l.prompt}

Return 4-8 well-evidenced items. Two things matter most:
· 'what_attest_could_learn' — a CONCRETE mechanism, metric, or failure, not a platitude.
· 'collision_risk' — factual overlap only. You may describe that a filing or mark exists
  and what it covers. You may NOT opine on infringement, validity, or freedom to operate;
  that is a licensed professional's judgment. Flag it for review instead. (This mirrors
  ATTEST's own cardinal rule: locate & evidence, never adjudicate.)`,
    { label: `survey:${l.key}`, phase: 'Survey', schema: FINDINGS, model: 'opus', effort: 'high' }
  )
))

const got = surveyed.filter(Boolean)
const items = got.flatMap(f => (f.items || []).map(i => ({ ...i, lens: f.lens })))
log(`${got.length}/${LENSES.length} lenses · ${items.length} items`)

phase('Challenge')
const judged = await parallel(items.map(it => () =>
  agent(
    `Hostile check. A survey proposes this as relevant to ATTEST:

${JSON.stringify(it, null, 2)}

${ATTEST}

Decide whether it is GENUINELY adjacent, or merely topically similar. Reject:
· generic RAG/LLM material that says nothing specific about provenance or abstention
· products that do document-level citation when ATTEST does span-level (say so — the
  distinction is the whole point, and blurring it produces a useless "competitor" list)
· anything whose 'evidence' you cannot believe is real (unverifiable paper, invented
  patent number, company that may not exist). Reject rather than pass it through.
· "lessons" that restate what ATTEST already does deliberately

Set 'action'. Use 'legal-review' ONLY for factual IP/trademark overlaps a professional
should look at — never render the legal conclusion yourself. 'one_line_for_owner' should
be the single sentence worth the owner's attention, in plain language.`,
    { label: `check:${(it.name || 'item').slice(0, 26)}`, phase: 'Challenge',
      schema: VERDICT, model: 'opus', effort: 'high' }
  ).then(v => (v ? { ...v, detail: it } : null))
))

const graded = judged.filter(Boolean)
const live = graded.filter(v => v.genuinely_adjacent)
log(`${live.length} of ${graded.length} survived the adjacency check`)

phase('Position')
const report = await agent(
  `Write the landscape report for ATTEST's owner (Julian).

${ATTEST}

SURVIVING ITEMS:
${JSON.stringify(live.map(v => ({ ...v.detail, action: v.action, why: v.why, line: v.one_line_for_owner })), null, 2)}

REJECTED (one line each — the negative result stops us re-searching):
${JSON.stringify(graded.filter(v => !v.genuinely_adjacent).map(v => ({ name: v.item, why: v.why })), null, 2)}

Markdown, plain and concrete. Structure:

1. **What ATTEST is that the field is not** — the genuine differentiators, stated without
   flattery. If a differentiator turns out to be common, SAY SO; that is the most valuable
   finding in this report.
2. **What we are missing** — mechanisms, metrics, or evaluation constructs this field
   already has that ATTEST does not. Rank by value.
3. **Standards we should meet rather than reinvent** — especially for the audit log and
   provenance record. Name the specific standard and what conforming would cost.
4. **The "verified != entailed" question.** ATTEST treats this as load-bearing honesty.
   Competitors ship groundedness SCORES that imply entailment. Is the honest line a
   liability in a sale, and how have others positioned around it? Answer directly.
5. **Toes — factual only.** Naming/trademark overlap (note "attestation" is heavily loaded
   in security/computing: remote attestation, in-toto/SLSA), and IP filings in the space
   with assignees and dates. State what EXISTS. State plainly that infringement, validity
   and FTO are a qualified attorney's call and this report does not make them — then list
   exactly what to put in front of that attorney.
6. **Cautionary tales** — what a 2026 buyer is already suspicious of, and what that implies
   for how ATTEST demonstrates itself.
7. **Candidate ROADMAP items**, each with a one-line rationale and a revisit trigger.

Distinguish what is well-evidenced from what is inference. Where the swarm could not
verify something, say "unverified" rather than smoothing it over.`,
  { label: 'synthesis', phase: 'Position', model: 'opus', effort: 'high' }
)

return { lenses: got.length, items: items.length, adjacent: live.length,
         rejected: graded.length - live.length, report }
