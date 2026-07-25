export const meta = {
  name: 'ocr-failure-modes',
  description: 'Research swarm: known failure modes in OCR-based document transcription, mapped onto ATTEST',
  whenToUse: 'Anticipate OCR transcription failures before they bite, and design the tests/corpus that would catch them.',
  phases: [
    { title: 'Sweep', detail: '9 failure-mode lenses in parallel (Opus 4.8)' },
    { title: 'Interrogate', detail: 'hostile review: would this actually bite ATTEST? (Opus 4.8)' },
    { title: 'Synthesise', detail: 'taxonomy + detection + test/corpus plan (Opus 4.8)' },
  ],
}

// ── Why this swarm exists ────────────────────────────────────────────────────
// ATTEST OCRs patent drawing sheets at ingestion (D28-D31) to locate reference
// numerals. Five failure modes were found the expensive way — by a human reviewing
// sheets and reporting misses:
//   1. thumbnail-vs-full-res URL (82x120 images silently used)            [L0003]
//   2. dimension labels D1-D6 / spaced sub-figure captions "FIGS. 3 A-C"  [L0005]
//   3. filters that delete signal (>=10 floor, >=2 mention floor, conf floor) [L0006]
//   4. single-glyph hallucination on line art; a/0 and 5/3 confusions     [L0008]
//   5. SHEET PRINTED SIDEWAYS — all engines read upright only; invisible to
//      cross-engine corroboration because every engine fails identically   [D31]
// Each was caught by a human, not by the system. The question this swarm answers:
// WHAT ELSE IS COMING, how would we DETECT it without a human, and what corpus +
// tests would catch it.

const CONTEXT = `
ATTEST's OCR context — judge every candidate failure mode against this:
· Documents: scanned patent drawing sheets (1990s USPTO scans, 2320x3408 PNG),
  sparse line art with small isolated numerals attached to leader lines. Also
  10-K/financial PDFs on the text side (no OCR there yet).
· Engines: Apple Vision (darwin), Tesseract 5 (all platforms), RapidOCR/PaddleOCR
  ONNX (all platforms). Run at INGESTION only; output frozen into a hashed manifest.
  Runtime is a pure function over that manifest (determinism invariant I6).
· Purpose: LOCATE a label on a sheet so a reviewer can confirm it. A drawing is
  "displayed evidence", never a text citation — grounding binds to the TEXT.
· Existing mitigations: text-guided targeted re-OCR (the spec predicts a numeral on
  a figure's sheet, tiled search confirms it); cross-engine corroboration as an
  acceptance rule; per-sheet orientation detection; positional same-spot conflict
  detection; a human-annotation channel with its own provenance.
· Precision >> recall for OUTPUT (never assert a wrong location) but over-filtering
  is ALSO a failure (deleting real labels is invisible to the user).
· Constraints: local engines only (client-confidential drawings never leave the
  machine); boring/legible dependencies preferred; ingestion may be slow, runtime
  must be deterministic.
`

const FINDINGS = {
  type: 'object',
  required: ['lens', 'modes', 'sources'],
  properties: {
    lens: { type: 'string' },
    modes: {
      type: 'array',
      items: {
        type: 'object',
        required: ['name', 'what_goes_wrong', 'would_it_bite_attest', 'detection',
                   'mitigation', 'silent_or_loud', 'test_design', 'corpus_need'],
        properties: {
          name: { type: 'string' },
          what_goes_wrong: { type: 'string', description: 'concrete mechanism, plain English' },
          would_it_bite_attest: { type: 'string', description: 'YES/NO/PARTIAL + why, given the context above (patent line-art sheets, three engines, ingestion-time)' },
          detection: { type: 'string', description: 'how a SYSTEM (not a human) could notice this happening — the key field' },
          mitigation: { type: 'string' },
          silent_or_loud: { type: 'string', enum: ['silent', 'loud'], description: 'silent = wrong output that looks fine (the dangerous class)' },
          test_design: { type: 'string', description: 'a concrete Layer-0-style test or fixture that would catch it' },
          corpus_need: { type: 'string', description: 'what document(s) a broader test corpus needs to exercise it' },
        },
      },
    },
    sources: { type: 'array', items: { type: 'string' } },
  },
}

const VERDICT = {
  type: 'object',
  required: ['mode', 'survives', 'why', 'priority'],
  properties: {
    mode: { type: 'string' },
    survives: { type: 'boolean' },
    why: { type: 'string' },
    priority: { type: 'string', enum: ['now', 'soon', 'watch', 'no'] },
    cheapest_detector: { type: 'string', description: 'the least-effort way to KNOW if this is happening in a given engagement' },
  },
}

const LENSES = [
  { key: 'geometry', prompt: `GEOMETRY & PRESENTATION: page rotation (90/180/270), arbitrary SKEW (1-5°), mixed orientations on ONE page (an upright header over a sideways figure), mirrored/transposed scans, non-square pixel aspect, cropping that cuts labels at the margin, multi-page fold-outs. ATTEST just found the 270° case the hard way — what else in this family, and crucially: how does a system DETECT that it is mis-oriented without a human? Cover deskew algorithms (Hough/projection profile), orientation classifiers (Tesseract OSD), and their failure rates on SPARSE LINE ART (very few text pixels — most published numbers are for dense prose).` },
  { key: 'resolution', prompt: `RESOLUTION, SCALE & PREPROCESSING: DPI too low for small glyphs, downsampling inside the engine, JPEG/CCITT compression artifacts on old scans, binarization/thresholding choices (Otsu/Sauvola/adaptive) and how they destroy thin strokes, dilation/erosion, upscaling (bicubic vs super-resolution) and whether it actually helps OCR or just hallucinates. What is the measurable relationship between glyph height in pixels and OCR reliability, and what is the practical floor?` },
  { key: 'lineart', prompt: `TEXT-IN-LINE-ART / GRAPHICS INTERFERENCE: leader lines and arrows fusing with digits, hatching/shading behind text, text touching or crossing rules, glyphs inside boxes and circles, dashed lines read as characters, engineering-drawing conventions. Also the inverse: line art hallucinated AS text (ATTEST saw a curly leader read as "C!"). How do document-analysis systems separate text from graphics (connected-component analysis, text/graphics separation literature — Fletcher-Kasturi and successors), and how reliable is it?` },
  { key: 'confusion', prompt: `CHARACTER CONFUSION & LEXICON EFFECTS: the classic confusion sets (0/O/o/Q, 1/l/I/|, 5/S, 8/B, 2/Z, 6/b, 9/g/q, rn/m), how they change WITHOUT a language model (digits in isolation have no context to correct against), why language correction HURTS on label text, engine-specific confusion tendencies, and the a/0 suffix case ATTEST hit ("14a" read "140"). How can a system detect a confusion without knowing the right answer — what redundancy is available (cross-engine disagreement, checksum-like structure, sequence expectations)?` },
  { key: 'layout', prompt: `LAYOUT & READING ORDER: multi-column, tables and cell association, captions vs body, headers/footers/furniture, reading-order errors, text fragmented across OCR "lines", coordinate systems and origin conventions (top-left vs bottom-left, normalized vs pixel — ATTEST hit a y-flip bug), bounding-box semantics across engines (word vs line vs block). What goes wrong when composing boxes from tiles or crops back into a page frame?` },
  { key: 'evaluation', prompt: `EVALUATION & GROUND TRUTH for OCR: CER/WER and why they mislead for LABEL extraction, IoU/localization metrics, how to build ground truth cheaply, inter-annotator agreement, benchmark datasets for engineering drawings / patents / forms (e.g. USPTO datasets, DocBank, PubLayNet, FUNSD, DeepPatent, drawings datasets), and what a REGRESSION suite for an OCR-dependent pipeline should look like when the engine itself is a moving target across OS/library versions.` },
  { key: 'drift', prompt: `NON-DETERMINISM & VERSION DRIFT: are OCR engines deterministic run-to-run (same input, same version, same machine)? What about across engine versions, OS updates, GPU/CPU/Neural-Engine paths, thread counts, ONNX runtime providers? What is known about Apple Vision revision changes, Tesseract 4->5 LSTM changes, PaddleOCR model updates? ATTEST freezes OCR output at ingestion into a hashed manifest to get determinism DOWNSTREAM — critique that design: what does it actually guarantee, what does it not, and what should be recorded to make drift detectable later?` },
  { key: 'domain', prompt: `PATENT/ENGINEERING DRAWING SPECIFICS: USPTO drawing conventions (reference numerals, leader lines, section markers A-A, view arrows, hatching standards, dimension callouts, sub-figure labelling), what patent-OCR/patent-figure-analysis literature and tools exist (e.g. work on patent figure segmentation, numeral extraction, PatentNet/DeepPatent, USPTO full-text/image APIs), and known accuracy figures. What do practitioners in patent analytics do about figure-numeral extraction — is there prior art we should be reusing rather than re-deriving?` },
  { key: 'humanloop', prompt: `HUMAN-IN-THE-LOOP & UNCERTAINTY COMMUNICATION for transcription systems: how mature systems surface OCR uncertainty to reviewers, confidence calibration of OCR scores (are engine confidences meaningful/comparable?), review-queue design, annotation provenance, "verification burden" research, and how to present a transcription that may be wrong WITHOUT either hiding the risk or drowning the user in caveats. Cover disclosure/labelling practice in regulated or evidentiary settings.` },
]

phase('Sweep')
log(`Sweeping ${LENSES.length} OCR failure-mode literatures against ATTEST's actual setup…`)

const swept = await parallel(LENSES.map(l => () =>
  agent(
    `You are researching for ATTEST, a grounded-retrieval system whose cardinal rule is
"ground or abstain — never invent". Use web search extensively; cite real papers,
tools and docs with authors/venues/years. Do NOT invent citations.

${CONTEXT}

YOUR LENS: ${l.prompt}

Return findings per the schema. The MOST IMPORTANT field is 'detection': ATTEST's
recurring problem is that failures are found by a HUMAN reviewing sheets, not by the
system. A mode nobody can detect automatically is far more dangerous than a common
one that announces itself — mark those 'silent'. Prefer 4-7 well-evidenced modes over
a long shallow list. Be concrete about whether each would actually bite THIS setup
(sparse patent line art, three local engines, ingestion-time, locate-only purpose).`,
    { label: `sweep:${l.key}`, phase: 'Sweep', schema: FINDINGS, model: 'opus', effort: 'high' }
  )
))

const found = swept.filter(Boolean)
const allModes = found.flatMap(f => (f.modes || []).map(m => ({ ...m, lens: f.lens })))
log(`${found.length}/${LENSES.length} lenses returned · ${allModes.length} candidate failure modes`)

phase('Interrogate')
const verdicts = await parallel(allModes.map(m => () =>
  agent(
    `You are a hostile reviewer protecting ATTEST from busywork and from false comfort.
A sweep proposes this OCR failure mode as something ATTEST should worry about:

${JSON.stringify(m, null, 2)}

${CONTEXT}

Interrogate it:
1. Would it ACTUALLY bite this setup? (Patent line art, not dense prose. Locate-only:
   a wrong TRANSCRIPTION that still lands the right box may be harmless; a right
   transcription in the wrong PLACE is not.)
2. Is the proposed detection real, or does it secretly need the right answer / a human?
3. Is the proposed test genuinely Layer-0-able (deterministic, no engine call), or does
   it require running an engine in CI (which ATTEST forbids — engines are
   ingestion-time only)?
4. Has ATTEST already mitigated it (see the existing mitigations in the context)?
5. Is the mitigation worse than the disease (over-filtering deletes real labels — a
   repeated ATTEST failure)?

Default to survives=false for anything speculative, already-handled, or undetectable.
Set 'priority': now / soon / watch / no. 'cheapest_detector' must be something a
script could run over an engagement's sheets TODAY.`,
    { label: `grill:${(m.name || 'mode').slice(0, 26)}`, phase: 'Interrogate',
      schema: VERDICT, model: 'opus', effort: 'high' }
  ).then(v => (v ? { ...v, detail: m } : null))
))

const graded = verdicts.filter(Boolean)
const live = graded.filter(v => v.survives)
log(`interrogated ${graded.length} · ${live.length} survived`)

phase('Synthesise')
const report = await agent(
  `Synthesise an actionable report for ATTEST's owner (Julian) and its ROADMAP.

${CONTEXT}

SURVIVING FAILURE MODES (passed hostile review):
${JSON.stringify(live.map(v => ({ ...v.detail, priority: v.priority, why: v.why, cheapest_detector: v.cheapest_detector })), null, 2)}

REJECTED (say briefly why each — the negative result stops us re-litigating):
${JSON.stringify(graded.filter(v => !v.survives).map(v => ({ name: v.mode, why: v.why })), null, 2)}

Write markdown in ATTEST's house register: plain, concrete, honest about limits.
Structure:

1. **The five ATTEST already hit, and what they were instances OF** — generalise the
   pattern (thumbnail/res, label-class filtering, over-filtering, glyph hallucination,
   orientation) so the shape is recognisable next time.
2. **What is coming that we have NOT hit** — ranked by (silent × likely). For each:
   the mechanism, the cheapest detector, and whether ATTEST is already covered.
3. **The detection gap** — every ATTEST failure so far was found by a HUMAN reviewing
   sheets. Which of these modes could be caught by a SELF-CHECK, and what would that
   check be? This is the most valuable section: name concrete, runnable checks.
4. **Test + corpus plan** — a broader corpus (name real, obtainable documents: other
   patents with known-awkward drawings, rotated/skewed scans, dense-numeral figures,
   different eras/scanners) and the Layer-0 fixtures that make each failure mode a
   standing test WITHOUT calling an engine in CI (frozen manifests as fixtures is the
   available trick).
5. **Orientation specifically** — Julian asks whether 0/90/270 is enough, and whether
   sheets with text at MULTIPLE orientations need multi-angle OCR unioned rather than
   a single best angle. Answer directly with evidence.
6. **Uncertainty communication** — how the report/GUI should surface OCR discrepancies
   prominently and early, and what the disclaimer should say to be accurate rather than
   merely defensive (note: ATTEST's OCR is frozen at ingestion, so DOWNSTREAM is
   deterministic; the OCR reading itself is model-derived and version-sensitive — say
   this precisely, do not overclaim in either direction).
7. **Candidate D# rows** for anything worth adopting, in the house style
   (decision / rationale / revisit-trigger).

Distinguish GUARANTEED from MEASURED throughout. Prefer 'do this cheap check now' over
'build this elaborate system'.`,
  { label: 'synthesis', phase: 'Synthesise', model: 'opus', effort: 'high' }
)

return { lenses: found.length, modes: allModes.length, survived: live.length,
         rejected: graded.length - live.length, report }
