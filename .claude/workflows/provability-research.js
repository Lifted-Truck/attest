export const meta = {
  name: 'provability-research',
  description: 'Research swarm: formal/statistical routes to stronger deterministic claim checking in ATTEST',
  whenToUse: 'Queued 2026-07-08 at Julian\'s request. Explores decomposing complex claims into formal logic + statistical guarantees, so ATTEST can push runtime checking closer to its theoretical ceiling. Fire when ready — it is research-only and writes no code.',
  phases: [
    { title: 'Sweep', detail: '8 literature lenses in parallel (Sonnet)' },
    { title: 'Interrogate', detail: 'adversarial reality-check of each candidate (Opus)' },
    { title: 'Synthesise', detail: 'map onto ATTEST decisions + testing protocol + the honest ceiling (Opus)' },
  ],
}

// ── The problem this swarm exists to solve ───────────────────────────────────
// ATTEST today: `verify` proves a cited atom RESOLVES (exists at its offset, hash
// matches). `check_coverage` proves the cited span CONTAINS the question's literal
// constraints. Neither proves the span ASSERTS the claim. Julian's falsifying case,
// confirmed live 2026-07-08:
//
//   passage: "When speaking of total assets and liabilities, the number $2,000,000
//             has been claimed, but in fact this is incorrect when accounting for…"
//   question: "What are the total assets and liabilities?"   answer: "$2,000,000"
//   → verify ok = TRUE, coverage.complete = TRUE  → the loop PRESENTS it.
//
// The span mentions the figure and the metric, and refutes both. Co-presence is not
// assertion. The truth contract already lists "negation/attachment/coreference remain
// Layer-E" — this swarm asks what could move some of that to a RUNTIME, deterministic
// check, and, just as importantly, what provably cannot move.

const HOUSE_RULES = `
ATTEST's non-negotiable constraints — judge every candidate technique against these:
· I6 DETERMINISM on the evidence path: same corpus + query → identical result, seeded.
· v1 makes ZERO model calls at runtime. A technique needing an LLM at decide-time is
  not disqualified, but it is an ARCHITECTURE CHANGE requiring a new logged decision
  (D#) and a truth-contract version bump — say so explicitly if that's the case.
· AI may interpret/propose/judge; AI is NEVER in the deciding path. Deterministic code
  decides.
· The oracle is sacred: gates are never weakened to pass. Two layers — Layer-0
  (deterministic, CI-blocking, no model calls) and Layer-E (behavioural, measured,
  billed, never a gate). State which layer a candidate belongs in.
· MONOTONIC contract: rigor may strengthen freely; weakening needs a major version +
  rationale. A candidate that trades a hard guarantee for a soft one must say so.
· "Boring and legible" beats clever. Legibility to a NON-SPECIALIST is the product.
  A technique only its author can read is a liability, however strong on paper.
· Precision >> recall. A confident wrong answer ends a client relationship; a miss does
  not. Report false-positive behaviour on REAL documents, not just benchmark F1.
`

const FINDINGS = {
  type: 'object',
  required: ['lens', 'candidates', 'ceiling', 'sources'],
  properties: {
    lens: { type: 'string' },
    candidates: {
      type: 'array',
      items: {
        type: 'object',
        required: ['name', 'what_it_does', 'attacks_the_2m_case', 'deterministic',
                   'needs_runtime_model', 'maturity', 'precision_on_real_text', 'layer', 'cost'],
        properties: {
          name: { type: 'string' },
          what_it_does: { type: 'string', description: 'plain English, no jargon-as-proof' },
          attacks_the_2m_case: { type: 'string', description: 'would it catch the $2,000,000 refutation case? how, concretely? or "no"' },
          deterministic: { type: 'boolean' },
          needs_runtime_model: { type: 'boolean' },
          maturity: { type: 'string', enum: ['production', 'research-solid', 'research-early', 'toy'] },
          precision_on_real_text: { type: 'string', description: 'reported precision AND its false-positive mode on real prose; say "unmeasured" if so' },
          layer: { type: 'string', enum: ['layer-0', 'layer-E', 'both', 'neither'] },
          cost: { type: 'string', description: 'implementation + runtime cost, dependencies pulled in' },
        },
      },
    },
    ceiling: { type: 'string', description: 'what this lens says is PROVABLY or practically impossible — the honest limit' },
    sources: { type: 'array', items: { type: 'string' }, description: 'concrete citations: paper/author/venue/year or URL' },
  },
}

const VERDICT = {
  type: 'object',
  required: ['candidate', 'survives', 'why', 'real_failure_mode'],
  properties: {
    candidate: { type: 'string' },
    survives: { type: 'boolean' },
    why: { type: 'string' },
    real_failure_mode: { type: 'string', description: 'the concrete way this breaks on a real 10-K or patent' },
    overclaimed: { type: 'string', description: 'what the sweep claimed that the literature does not actually support' },
  },
}

// ── Phase 1 — eight lenses, deliberately non-overlapping ─────────────────────
const LENSES = [
  {
    key: 'natural-logic',
    prompt: `Research NATURAL LOGIC and MONOTONICITY CALCULUS for entailment.
Cover: MacCartney & Manning's NatLog; monotonicity/polarity marking; upward vs
downward entailing contexts; projectivity; modern revivals (e.g. NeuralLog, monotonicity
in NLI). The core question: can polarity be computed DETERMINISTICALLY from a parse, so
that "X has been claimed, but in fact this is incorrect" marks X as a NON-asserted /
downward context — mechanically, no model at decide-time? Be concrete about what a
parser must supply and how brittle that is on real financial/legal prose.`,
  },
  {
    key: 'veridicality',
    prompt: `Research VERIDICALITY, EVENT FACTUALITY, and NEGATION/HEDGE DETECTION.
Cover: Saurí & Pustejovsky (FactBank, De Facto); NegEx / ConText; BioScope hedging;
attribution & source-tagging (who asserts what — "X has been claimed" attributes to an
unnamed other, not the document); factuality profiling; speculation detection. This lens
is the closest existing match to ATTEST's failing case: text that MENTIONS a value while
ATTRIBUTING it elsewhere or REFUTING it. Report what precision these achieve on real
prose and their standard false-positive modes.`,
  },
  {
    key: 'logical-form',
    prompt: `Research SEMANTIC PARSING TO LOGICAL FORM.
Cover: AMR; Discourse Representation Theory/Structures (Boxer, DRS); FOL translation;
neuro-symbolic NLI; LLM→logic pipelines (Logic-LM, SatLM, LINC) and their measured
failure rates. Key question for ATTEST: can a claim + its cited span be compiled into
comparable logical forms so entailment becomes a DECIDABLE check? Be brutally honest
about where the compilation step itself is the weak link, and whether it can be made
deterministic.`,
  },
  {
    key: 'automated-reasoning',
    prompt: `Research AUTOMATED REASONING and PROOF-CARRYING OUTPUTS.
Cover: SMT solvers (Z3, CVC5) applied to NL-derived constraints; proof-carrying code and
its analogues for NL claims; certified/verified outputs; theorem-prover-checked
pipelines. Key question: once a claim is in logical form, what does a solver actually buy
us — a machine-checkable PROOF OBJECT that could be shipped in ATTEST's audit log
alongside the citation? What does that proof actually certify, and what does it NOT?`,
  },
  {
    key: 'statistical-guarantees',
    prompt: `Research DISTRIBUTION-FREE STATISTICAL GUARANTEES for selective prediction.
Cover: conformal prediction (incl. split/inductive conformal, and conformal for NLG);
selective prediction / the reject option / Chow's rule; PAC-Bayes; calibration
(temperature scaling, Brier/ECE); risk-controlling prediction sets (RCPS), Learn-then-Test.
Key question for ATTEST: can we put a RIGOROUS, distribution-free bound on the residual
error of a present/abstain decision — i.e. "at most X% of what we present is wrong, with
Y confidence" — and what exchangeability assumptions does that need? ATTEST already
tracks Brier + abstention; this lens should say what a real guarantee (not a metric)
would require.`,
  },
  {
    key: 'provability-logic',
    prompt: `Research PROVABILITY LOGIC proper and the THEORETICAL CEILING.
Cover: Gödel-Löb (GL) modal logic; Löb's theorem; the arithmetised provability predicate;
incompleteness; Rice's theorem; undecidability of FOL validity; and the ambiguity of
natural language as a separate, non-logical ceiling.
IMPORTANT — be honest and possibly deflationary: provability logic (GL) is the modal logic
of provability IN FORMAL ARITHMETIC. Assess plainly whether it is genuinely applicable to
document-grounded claim checking or whether the useful work lives in adjacent fields
(natural logic, veridicality, conformal prediction). Do NOT stretch it to fit. The
deliverable of this lens is chiefly: WHERE IS THE CEILING, and what is it made of —
undecidability, or irreducible linguistic ambiguity, or both?`,
  },
  {
    key: 'claim-decomposition',
    prompt: `Research CLAIM DECOMPOSITION and ATTRIBUTION VERIFICATION benchmarks.
Cover: FEVER and successors; FActScore; RARR; ALCE; AttributionBench/AttrScore; sub-claim
decomposition into atomic checkable units; citation-verification for RAG. Key questions:
how do the best systems decompose a compound claim into atomically-checkable units, how
is attribution scored, and what do the benchmarks reveal about the ceiling of automatic
attribution checking? Also: what do these benchmarks systematically MISS (e.g. exactly the
refutation-context case)?`,
  },
  {
    key: 'discourse-scope',
    prompt: `Research DISCOURSE STRUCTURE, SCOPE, and ANAPHORA as they bear on citation validity.
Cover: RST and discourse parsing; scope of negation and quantifiers; contrast/concession
relations ("but in fact this is incorrect" is a CONCESSION/CONTRAST relation); coreference
resolution; attachment ambiguity. Key question: could a deterministic discourse/scope
analysis flag that a cited span sits inside a contrast or refutation relation and is
therefore unsafe to cite as an assertion? What accuracy do discourse parsers actually hit
on financial/legal prose, and what does that imply for using them as a GATE vs a WARNING?`,
  },
]

phase('Sweep')
log(`Sweeping ${LENSES.length} literatures against ATTEST's constraints…`)

const swept = await parallel(LENSES.map(l => () =>
  agent(
    `You are researching for ATTEST, a grounded-retrieval system whose cardinal rule is
"ground or abstain — never invent". Use web search extensively; cite real papers with
authors/venues/years. Do not invent citations — a fabricated source here would be
darkly ironic and is an automatic failure.

${HOUSE_RULES}

THE CONCRETE FAILING CASE this research must speak to:
  passage: "When speaking of total assets and liabilities, the number $2,000,000 has
            been claimed, but in fact this is incorrect when accounting for the revaluation."
  question: "What are the total assets and liabilities?"   answer given: "$2,000,000"
  ATTEST today: verify ok = TRUE, coverage complete = TRUE → it would PRESENT this.
  The span mentions the metric and the figure — and refutes them. Co-presence ≠ assertion.

YOUR LENS: ${l.prompt}

Return findings per the schema. For every candidate technique, the field
'attacks_the_2m_case' must say CONCRETELY whether and how it would catch that case —
"no" is a perfectly good and useful answer. Prefer 3-6 well-understood candidates over a
long shallow list. The 'ceiling' field is not optional: say what this lens proves or
strongly suggests is IMPOSSIBLE.`,
    { label: `sweep:${l.key}`, phase: 'Sweep', schema: FINDINGS, model: 'sonnet', effort: 'high' }
  )
))

const found = swept.filter(Boolean)
const allCandidates = found.flatMap(f => (f.candidates || []).map(c => ({ ...c, lens: f.lens })))
log(`${found.length}/${LENSES.length} lenses returned · ${allCandidates.length} candidate techniques`)

// ── Phase 2 — interrogate. Default to refuted; the burden is on the candidate ──
phase('Interrogate')
const verdicts = await parallel(allCandidates.map(c => () =>
  agent(
    `You are a hostile reviewer protecting ATTEST from a plausible-but-wrong idea.
A research sweep proposes this technique for making claim-checking more rigorous:

${JSON.stringify(c, null, 2)}

${HOUSE_RULES}

Try to REFUTE it. Specifically interrogate:
1. Does the claimed capability survive contact with a REAL 300-page 10-K or a 1995
   patent scan — or is the reported performance from short, clean benchmark sentences?
2. What is its false-POSITIVE behaviour? (For ATTEST, a check that wrongly blocks good
   answers is bad; a check that wrongly passes bad ones is disqualifying.)
3. Does it secretly need a model at decide-time, breaking I6 determinism? Does the sweep
   admit this?
4. Is it legible to a non-specialist reviewer, or does it make the system unauditable?
5. Did the sweep OVERCLAIM relative to what the cited literature actually shows?

Default to survives=false if you are uncertain. A technique only survives if you cannot
find a concrete, realistic way it breaks or misleads. Be specific — name the failure.`,
    { label: `grill:${(c.name || 'candidate').slice(0, 26)}`, phase: 'Interrogate',
      schema: VERDICT, model: 'opus', effort: 'high' }
  ).then(v => (v ? { ...v, candidate_detail: c } : null))
))

const graded = verdicts.filter(Boolean)
const survivors = graded.filter(v => v.survives)
log(`interrogated ${graded.length} · ${survivors.length} survived`)

// ── Phase 3 — synthesise into something ATTEST can actually act on ───────────
phase('Synthesise')
const report = await agent(
  `Synthesise a research report for ATTEST's owner (Julian) and its ROADMAP.

${HOUSE_RULES}

SURVIVING CANDIDATES (passed hostile review):
${JSON.stringify(survivors.map(v => ({ ...v.candidate_detail, why_survived: v.why, failure_mode: v.real_failure_mode })), null, 2)}

REFUTED (say briefly why each died — the negative result is genuinely valuable, it stops
us re-litigating these later):
${JSON.stringify(graded.filter(v => !v.survives).map(v => ({ name: v.candidate, why: v.why, overclaimed: v.overclaimed })), null, 2)}

CEILINGS reported by each lens:
${JSON.stringify(found.map(f => ({ lens: f.lens, ceiling: f.ceiling })), null, 2)}

Write markdown, in the register of ATTEST's own docs: plain, concrete, no jargon-as-proof,
honest about limits. Structure:

1. **The verdict in five sentences** — can the $2,000,000 refutation case be caught at
   runtime, deterministically, yes or no? If partially, exactly which part?
2. **The ceiling** — what is provably/practically impossible here, and what is it made of.
   Julian explicitly wants to know how close to the limit we can push AND where the limit
   genuinely is. Do not be falsely encouraging; a real ceiling honestly drawn is the most
   valuable thing in this report.
3. **The staircase** — surviving candidates ordered as INCREMENTS, cheapest/most-certain
   first. For each: what it would guarantee, what it would NOT, which layer (0 or E),
   the dependencies it pulls in, and whether it needs a truth-contract version bump.
4. **Testing protocol** (Julian asked for this explicitly, throughout). For each increment:
   the Layer-0 test design (deterministic, CI-blocking) and/or the Layer-E measurement
   design; the fixtures needed; how we would know it REGRESSED; and how it interacts with
   the frozen oracle (golden sets are append-only — new checks must not silently re-label).
5. **Candidate D# rows** — for anything worth adopting, draft the ROADMAP decision row
   (decision / rationale / revisit-trigger), in the existing house style.
6. **What died and why** — the refuted list, one line each.

Rule: distinguish GUARANTEED from MEASURED everywhere. If an increment converts a
Layer-E residual into a Layer-0 guarantee, say so loudly — that is the whole point of the
exercise. If it merely moves the measurement, say that too, plainly.`,
  { label: 'synthesis', phase: 'Synthesise', model: 'opus', effort: 'high' }
)

return {
  lenses: found.length,
  candidates: allCandidates.length,
  survived: survivors.length,
  refuted: graded.length - survivors.length,
  report,
}
