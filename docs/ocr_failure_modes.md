# OCR failure modes — research synthesis

> **Provenance.** Authored by a 72-agent research swarm run from the ATTEST repo on
> 2026-07-25 (`.claude/workflows/ocr-failure-modes.js`, all agents Opus 4.8), motivated
> by Julian's request to anticipate OCR-transcription failures rather than discover them
> one QA round at a time. 9 non-overlapping lenses swept the literature and the repo;
> each of the 62 candidate modes was then grilled by an independent hostile reviewer
> that defaulted to rejection for anything speculative, already-mitigated, or requiring
> a human to detect. 43 survived.
>
> **Status: research input. Subordinate to ROADMAP; authorizes no work.** Same standing
> as `landscape_lessons.md` and `provability_research.md`. Its claims about this repo
> were spot-checked before anything was acted on — the four acted on in D34 were each
> reproduced first. The rest await human triage; do not treat a surviving mode as a
> mandate.
>
> **Already actioned (D34):** §2.3 vocabulary (4-digit + uppercase-suffix numerals),
> §2.1 silent engine dropout, §2.2 the unverified `image_sha256`.

---

# OCR failure modes — actionable synthesis for ATTEST

**Scope.** Patent drawing sheets (US5447630A, 8 sheets, 2320×3408 1-bpp PNG @300 dpi, 145 admitted numerals, 2092 raw observations), three engines run at ingestion into a frozen hashed manifest. Everything below was checked against the repo and that manifest, not inferred from literature.

**Two words, used strictly:**
- **GUARANTEED** = enforced by code or by a standing test. If it breaks, something goes red.
- **MEASURED** = observed on the one engagement we have. n=1. It is evidence, not a property.

Almost everything reassuring in this report is MEASURED. That is the headline risk: the constants and the confidence both come from a single 1995 mechanical patent.

---

## 1. The five we already hit, and what they were instances of

Five real incidents. None was caught by a test; all five were caught by Julian looking at a sheet. That fact is the subject of §3.

### 1.1 The thumbnail / resolution class → **"the artifact you ingested is not the artifact you think"**

`fetch_patent_figures.py` picks between two same-named Google Patents URLs by byte length, and Google serves an 82×120 thumbnail under the identical `…-drawings-page-N.png` name.

The general shape: **a silent substitution upstream of the first thing you measure.** Every metric downstream is computed faithfully over the wrong input, so every metric agrees. The specific aggravation here (MEASURED, and worse than the sweep found): every coordinate in the manifest is a *normalized fraction*, so a thumbnail's manifest is structurally identical to a full-res one. Resolution is erased from the frozen record by construction. `ocr_manifest.json` records `image_sha256` but no width, height, or dpi.

**Recognise it next time by asking:** what identifies the bytes I ingested, and is that identity recorded *in the artifact I will later reason over*?

### 1.2 The label-class filter class → **"the filter's blind spot is congruent with its criterion"**

The ≥10 numeral floor (deleted real single-digit numerals from the *text* model). The ≥2-mention acronym floor (deleted CZ/CL). D30's sub-10 sighting policy (correct, but by construction unfalsifiable from the output).

The shape: **you write a rule to reject a noise class, and the rule's definition is the same property that defines a real signal class.** You cannot then measure the damage, because the measurement uses the same predicate. A ≥10 floor makes sub-10 misses invisible *to the recall metric*.

### 1.3 Over-filtering in general → **asymmetric observability**

A false positive leaves an artifact a human can point at. A deleted real label leaves *nothing* — no low-confidence row, no flag, no diff, no log line. LIBRARY L0006 now has five instances. Every one of them was a plausible precision improvement.

This is why `gate_rotated_numerals` refuses to gate upright reads, and why almost every "tighten this threshold" recommendation in the sweep should be rejected: **the pipeline's precision instincts are good and its recall instruments do not exist.**

### 1.4 Glyph hallucination → **every engine is a total function**

"C!", "J2", the phantom 98/86 pairs, the `_NOT_A_NUMERAL = {"0"}` patch. Tesseract's own maintainers put it plainly: an image with no text is still treated as an image of text. There is no engine output that means "nothing here."

The shape: **absence is not representable in the output, so absence must be established by something other than the engine.** For ATTEST that "something else" is the spec text — which is why the spec-vs-drawing reconciliation is the load-bearing instrument and not a nicety.

### 1.5 Orientation (D31 → D32) → **a presentation mismatch is invisible to redundancy**

D31's own words are the general lesson and should be quoted forward: *"all three engines fail identically on rotated text — no amount of engine redundancy would have found it. Only comparing the sheet against itself at another orientation does."*

The shape: **when the defect is in the pixels rather than the model, cross-engine agreement is not evidence.** Three engines fed the same rotated raster agree because they are looking at the same wrong thing. The only detector for that class is *self-comparison under a transformation*.

### The meta-pattern (worth its own line)

**Four of the five were mitigations that became the failure.** The ≥10 floor was a noise filter. The ≥2-mention floor was a noise filter. `detect_orientation` was the fix for a recall problem. A mitigation earns trust it has not measured, and trusted mitigations are where the next silent failure lives. This is why §3 matters more than §2.

---

## 2. What is coming that we have not hit

Ranked by **silent × likely**. "Silent" here means: produces no artifact, no error, and no count anomaly.

| # | Mode | Silent? | Likely? | Covered today? |
|---|---|---|---|---|
| 1 | **Silent engine dropout** — a broken engine reads as "found nothing" | total | high on any new machine | no |
| 2 | **Manifest overwrite / unverified raster binding** | total | certain on re-ingest | no |
| 3 | **4-digit & uppercase-suffix numerals structurally unreadable** | total | high on any post-2000 patent | no |
| 4 | **Client PDF with lossy JBIG2 → the digit is substituted in the pixels** | total | moderate, catastrophic | no |
| 5 | **Margin crop turns `134` into `34`, a numeral that also exists** | total | low here, high on rescans | no |
| 6 | **Sub-resolution rendition frozen (thumbnail)** | total | low, unguarded | no |
| 7 | **Engine/model drift at re-ingest** (Vision revision unpinned) | partial | certain over time | partial |
| 8 | **Primed numerals `10'` collapsed to `10` on the TEXT side** | total | moderate | no |
| 9 | **Section-line designators `12—12` boxed as part 12** | partial | high on ≥10-figure patents | no |
| 10 | **Coordinate-frame error in `unrotate_observation`** | total | low, already bitten once | weakly |
| 11 | **Line-level box drawn as a numeral box** | loud-ish | present now (13 records) | no |
| 12 | **Pooled confidence decides which box is drawn** | partial | present now | no |
| 13 | **A global preprocessing step starves one engine** | total | high the next time someone "improves" recall | no |
| 14 | **DPI dropped on derived copies → Tesseract runs at an uncontrolled resolution** | total | present now | no |

### The ones worth acting on before the next engagement

**1 — Silent engine dropout.** `TESSERACT_OK = shutil.which("tesseract") is not None` is presence-on-PATH, not a working engine; `subprocess.run(..., capture_output=True)` at lines 187 and 381 never checks `returncode` and never reads `stderr`. A relocated `TESSDATA_PREFIX` yields empty stdout, zero observations, and the pipeline proceeds. Nothing distinguishes "Tesseract read this sheet and found nothing" from "Tesseract did not run."

This is not a predicted failure — **LIBRARY L0009 is this exact incident**, already written down and never installed in code ("leptonica's error went to stderr, which the harness decoded but never checked").

MEASURED blast radius: dropping Tesseract loses 15 sole-source labels plus 1 that falls under the corroboration gate = 16 of 145 (11%). Dropping Vision: 25 (17%). Dropping RapidOCR: 14 (10%).

*Cheapest detector:* per-engine raw-observation count per page must be > 0. A USPTO sheet always carries the running header, so zero is definitionally an instrument failure. Current floor: 29 observations (rapidocr, p.4).

**2 — Manifest overwrite and the decorative hash.** Three separate facts, all verified:
- The manifest's own sha256 is **printed to stdout and discarded** (`ocr_patent_figures.py:602`).
- `image_sha256` has **exactly one consumer in the whole tree: the line that writes it.** Nothing verifies it. Compare `ingest/store.py:47`, `verify_document(doc)  # I3 enforced on every read` — I3 is GUARANTEED for text and merely *declared* for drawings.
- `out.write_text(...)` overwrites in place, and `corpus/engagements/` is gitignored, so a re-run destroys the prior evidence map with no diff and no backup.

Consequence: if anyone re-fetches or re-crops a sheet without re-OCRing, every normalized box lands on a different raster and the view renders confident boxes at wrong locations, silently. That is the wrong-place class, which is the one we say we never commit.

**3 — Numerals the extractor cannot express.** All three extraction sites cap at three digits: `_DIGIT_RUN` (image), `patents._NUMERAL` (spec), `audit_sheet_labels._LABEL` (audit). `reference_numerals('the controller 1002 and the bus 1010 of FIG. 10')` returns `[]`.

The figure-keyed 1000-series (FIG. 10 → 1000/1010/1020) is the dominant convention in post-2000 software and electronics art. On such a patent the coverage report reads *clean* — `recited_not_drawn: []` and `drawn_not_recited: []` — because **both sides of the reconciliation are empty**. A perfect score over an empty map.

Worse, the uppercase-suffix half is not an omission but a **false assertion on the text side**: `reference_numerals('the housing 12A ... the housing 12')` returns `[('12','housing')]` — the suffix is eaten and a distinct part is asserted as part 12. Text is where grounding binds. That is the serious half.

**4 & 5 — the two intake-time modes.** JBIG2 lossy pattern-matching substitutes a digit *in the decoded pixels* (the 2013 Xerox WorkCentre incident; the German BSI banned it for this in 2015). Margin crop truncates `134` to `34`. Both defeat the entire mitigation stack by construction: all three engines read the same corrupted pixels, round-trip re-crop re-reads them, and the spec corroborates because the truncated/substituted string is usually *also* a real reference numeral. US5447630A has six left-truncation pairs (120/20, 112/12, 110/10, 113/13, 140/40, 280/80).

Neither bites today (MEASURED: 1-bpp lossless PNG throughout; closest numeral box to any edge is 0.084 normalized, ~195 px). Both become live the moment a client hands over PDFs — which is intake Q20, still open. **Build these as intake checks with the PDF adapter (PE-1), not before.**

**11, 12 — the two present-tense cosmetic-but-real defects.** MEASURED: 13 of 145 records have a box wider than 2× the page median, every one sourced from a dirty `source_text` (`"14 140"`, `"→70"`, `"=93"`, `"+54"`, `"--12a"`, `">120"`). Page 3's `140` box spans x 0.565→0.644: it fully encloses the real `14` and *clips* the real `140`. A reviewer confirming "140" is looking at a box dominated by a different numeral, in exactly the 14/140/14a confusion family.

And the pooled `confidence` field: MEASURED across 2092 raw observations, **Vision emits exactly 3 distinct values {0.3, 0.5, 1.0} over 547 reads**; Tesseract 597 distinct over 1134; RapidOCR 218 over 411. `merge_same_spot_numerals` sorts by `-confidence`, so which box gets drawn is decided by a 3-level quantizer. Cross-engine box-centre disagreement is small (~5 px median) so the harm is minor today — but the field is *displayed verbatim to the reviewer* as `OCR conf 1.0`, and 3 of the records at 1.0 are single-engine while 49 are three-engine. The display shows the least trustworthy number and hides the most trustworthy one (`engines`, which is right there in the record and never reaches the view — `patent_figures_view.py:253` carries only `(numeral, bbox, confidence)`).

**13, 14 — the two latent traps.** No preprocessing step exists today, and that is load-bearing: I reproduced that `convert("L")` + `GaussianBlur(0.8)` takes Tesseract on drawings-page-3 from 18 numeric tokens to **zero** (Tesseract short-circuits thresholding on 1-bpp input; re-graying destroys 2.7-px strokes). The "obvious improvement" after the next QA round — blur/denoise/upscale globally because it demonstrably helps Vision — guts Tesseract, and the aggregate label count barely moves. Separately, `_rotated_copy` and `marker_band_rescue` write PNGs with no pHYs chunk (verified: source `info == {'dpi': (299.9994, 299.9994)}`, reloaded derived copy `info == {}`), so Tesseract estimates resolution from content and reports values from 378 to 2269 across sheets of the *same* scan. Angle 0 reads the tagged original; angles 90/180/270 read untagged copies. Two different engine configurations are unioned.

---

## 3. The detection gap — the checks to actually write

**The fact to sit with:** every OCR failure this project has found was found by a human looking at a sheet. Not one was found by a test. That is not a discipline problem; it is that the manifest is measured for *what it contains* and never for *what it is missing or what it silently decided*.

Three tiers, in order of value per line.

### Tier A — pure functions over the frozen manifest (no engine, no image, no ground truth, no human)

These are all Layer-0-legal: the manifest is frozen and hashed, so a function over it is deterministic and calls no model. Put them in one `scripts/audit_manifest.py` with committed baselines. **Every number below is MEASURED on US5447630A today.**

| Check | What fires | Today |
|---|---|---|
| **A1 Engine liveness** — per (page, engine) count of raw observations | any zero | min 29, clean |
| **A2 Conservation** — replay the gate chain over `observations`, count drops per gate | any gate's drop count moves | header 410 · prose 160 · sub-10 151 · not-a-numeral 10 · **rotated gate 24** |
| **A3 Raster binding** — re-hash each PNG, compare to `image_sha256` | any mismatch | 8/8 match |
| **A4 Frame integrity** — median centre displacement per angle vs the upright read; per engine-pair; count of `y → 1−y` mirror pairs | any median off rounding, or mirror count > 0 | dx ≤ +0.0011, dy ≤ +0.0002; mirror 0/1499 |
| **A5 Engine contribution** — per-engine total and sole-source count | any engine's total drops | vision 20 sole / tesseract 15 / rapidocr 8; 43 of 145 single-engine |
| **A6 Confidence scale shape** — distinct-value count per engine over raw obs | any engine < ~5 distinct | **vision 3 / 547 — fires today** |
| **A7 Line-level boxes** — `w > 2×` page median, or `source_text` ≠ the token | any new one | **13 records — fires today** |
| **A8 Ambiguous confirmation targets** — boxes containing a foreign sighting's centre | count rises | 53/145 (41 not already flagged by same-spot conflicts) |
| **A9 Strobogram twins** — rotated-only labels whose 180° alias sits at the mirrored spot on the same sheet | any hit | 0; also **0 admissions on 180 alone** |
| **A10 Split records** — same numeral, same page, boxes overlapping or centres < 0.02, kept separate | count rises | 13 rows; min genuine same-token separation 0.0202 vs merge radius 0.02 — **0.7 px of headroom** |
| **A11 Weak-evidence slice** — single-engine AND has an in-lexicon confusion twin | report as a review queue, never a filter | 28/145 (19%) |
| **A12 Prior-admitted count** — `method == text-guided` OR `corroboration == spec`, with < 2 engines | report | 14/145 (10%) |
| **A13 Adjudication coverage** — count of `method: human` | report | **0 of 145** |

A6, A7, A10 and A13 fire today. A10 is the sharpest: the merge radius is pinned to the top of its safe window by accident and has never been measured.

### Tier B — pure over the sheets, no engine (PIL/numpy at intake)

- **B1 Sheet geometry.** Print width/height/dpi/bytes per sheet; hard-fail on *cross-sheet dimension disagreement* (self-calibrating, no magic number — this is the thumbnail-substitution signature) and on a short edge under ~1000 px (derived from 37 CFR 1.84(p)(3): a 1/8-inch reference character cannot physically exist below that at any scan resolution). Do **not** gate on an absolute dpi or a pHYs chunk — a legitimate CDN re-encode drops pHYs. Today: 8 × (2320, 3408), no flags.
- **B2 Ink margins.** Per-column/row ink counts with a **noise floor of >5 px** — the floor is load-bearing; raw, it flags 4 of 8 sheets on 2-pixel scanner specks. Thresholded: L 220–243, R 171–184 across all sheets. Compare across sheets of one grant; an outlier is a detected crop.
- **B3 Glyph-bitmap repeats** (JBIG2 signature). Hash each glyph-sized connected component; flag any bitmap occurring ≥3 times. MEASURED baseline: 741 components across 8 sheets, max duplicate = 1, distinct/instances = 1.000. Synthetic symbol-reuse gives 12 instances / 1 distinct, so the threshold has ~3× margin and a proven known-negative.

### Tier C — text-only, before any OCR runs (milliseconds, spec alone)

- **C1 Vocabulary coverage.** Probe the spec for 4+-digit runs in element-noun position and for `\d{1,3}[A-Z]` labels; diff against `reference_numerals()`. Non-empty = the extractor cannot express labels this patent recites → fail ingestion loudly. This is the *only* honest detector for §2.3, because the obvious one (compare the spec inventory to the image regex) passes vacuously — the inventory is already empty.
- **C2 Prime scan.** `(?<![.\d])(\d{1,3})\s*['′’](?!\s*[\d.])` over the pre-claims text. Zero hits ⇒ the primed-numeral mode does not apply to this engagement, close it. Non-empty ⇒ every bare-base read of those numerals is a suspect binding, and `label_pattern` needs a `(?!['′’])` guard immediately (today it matches *inside* `10'`).
- **C3 Section-designator scan.** Match the sectional-view idiom (`taken along line N—N ... of FIG. M`) and report (a) which designators are also reference numerals, (b) which numerals got their element phrase from the section sentence. On US5447630A: empty, correctly — no "taken along", all figures < 10.

### Tier D — ingestion-time asserts (engines available; **not** CI)

`pytest -m layer0` must never call an engine. These belong in `ocr_patent_figures.py` itself:

- Check `returncode` and surface `stderr` whenever stdout is empty (L0009's own corollary, still uninstalled).
- Assert per-engine non-zero yield per full sheet — **not** per tile; tiles legitimately return nothing.
- Round-trip report: crop each emitted box out of the *original* PNG and re-OCR it. This catches every frame/flip/scale error at once. It **must be a report that flags for human review, never an emission gate** — a numeral legible only at 270° fails an upright crop by construction, and that is 19 marks today.
- Refuse to clobber an existing manifest without `--force`; archive the old one; store the manifest's own sha256 and a `generator_commit`.

### What cannot be self-checked, honestly

- **True recall.** The spec gives a denominator for recited numerals (near-exhaustive under 37 CFR 1.84(p)(5)) — that is a real, free, engine-free recall *floor*. It says nothing about marks the spec never recites: view letters, dimension callouts, unlabelled parts. Only a human annotating a sheet blind gives that.
- **Whether a corroborated reading is correct.** Three engines on the same corrupted pixels agree. §1.5's lesson stands.
- **Calibration of anything.** No adjudicated outcomes exist. Do not build a calibration map; there is nothing to fit.

**One thing to do this week, before anything else:** annotate **one sheet blind** — overlay off, list every mark you can see — and write it to `manual_annotations.json` with human provenance. `manual_annotations.json` is currently `[]`, and ROADMAP:269 records a human confirmation (the FIG-2 "A") that was subsequently **replaced by a 0.668-confidence single-engine tesseract read** and is now unrecoverable, because the sidecar was never append-only and the ROADMAP entry carries no coordinates. Once you have looked at the overlay, an uncontaminated blind stratum can never be recreated for that sheet.

---

## 4. Test and corpus plan

### The available trick: frozen manifests as fixtures

Engines are ingestion-time only and `corpus/engagements/` is gitignored (client-confidential, permanently). So:

1. **Commit synthetic manifests, not sheets.** A manifest is a JSON dict of observation records. Hand-build them. Every Tier-A check above is then a pure function under test with no engine, no image, and no confidential content. `tests/test_figures_map.py:434` already builds synthetic sighting lists — that is the template, and it scales to all of Tier A.
2. **For behaviour that needs a real run, freeze the run.** Want a known-negative proving the preprocessing check has teeth? Run the sigma-0.8 blur once at ingestion, commit the *resulting manifest* as a static fixture, and assert against it. No engine in CI, and the instrument is proven to fire (L0009's discipline, applied to fixtures).
3. **Anything needing a real sheet uses a public-domain sheet**, committed to the repo. Client drawings never enter the test corpus. This is not a limitation to work around — it is the only version that is portable to a second machine.

### Layer-0 fixtures, one per mode

| Mode | Fixture | Assertion |
|---|---|---|
| Engine dropout | manifest with one engine at 0 observations on a page | raises, naming engine + page |
| Conservation | manifest + gate replay | `admitted + rejected == candidates`, every rejection names its gate |
| Coordinate frame | **pure-math** dihedral test of `unrotate_observation` with a deliberately asymmetric box (w≠h, x≠y, nothing summing to 1) | 4-fold composition is identity; `unrotate(k)` and `unrotate(360−k)` are mutual inverses; one *named corner* maps to its known destination |
| Frame integrity | committed manifest | per-angle/per-engine median displacement < 0.005; mirror count 0 |
| Vocabulary | spec strings `['12','12a','12A','102','1000','1002',"10'"]` | each is expressible; failure names the unrepresentable ones |
| Prime binding | text `"the connector 10' is shown near 10"` | `label_pattern("10")` does **not** match inside `10'` |
| Section designator | synthetic spec + fabricated observations of `12` at both ends of FIG 11 | element phrase for 12 is not `"taken along line"`; the sheet carries an advisory; **no sighting is deleted** |
| Line-level box | manifest with `source_text="14 140"` and one wide box | flagged `localization: line-level`; a clean sibling is merged by containment |
| Same-spot conflict | sightings `('12a', …)` and `('120', …)` 0.001 apart | one conflict reported; **fails today** (the `isdigit()` conjunct at figures_map.py:519 exempts suffixed labels) |
| Radius invariant | constants | conflict radius == merge radius (today 0.01 vs 0.02, with 0.7 px of headroom above the closest genuine same-token pair) |
| Preprocessing | frozen blurred-run manifest as a **negative** fixture | per-engine total recall drops → assertion fires. Gate on per-engine **total**, never on the unique set (a label going from Tesseract-only to Tesseract+Vision leaves Tesseract's unique set while becoming *more* admissible) |
| DPI round-trip | pure Pillow | `rotate(90).save(p)` preserves `info['dpi']` — **fails today** |
| Human provenance | sidecar entry colliding with an OCR sighting | rendered provenance is `human`; and permuting `page['numerals']` changes nothing — **fails today** |
| Adjudication | manifest | prints coverage; **reports, never gates** (gating on it fails 100% of strata and becomes a warning within a week) |

### Corpus

I am deliberately **not** inventing patent numbers. Here are selection *queries* that resolve deterministically on Google Patents / USPTO full-text search, plus the pre-annotated sets. Verify each on download before committing.

**Must-have (each unblocks a mode that is currently untestable):**

| Need | Selection query | Unblocks |
|---|---|---|
| 1000-series numbering | any post-2005 grant, ≥10 figures, software/electronics art unit; check the detailed description for `1002`/`1010` | §2.3 vocabulary |
| Sectional views | brief description contains `"taken along line"` with a designator ≥ 10 | §2.9 |
| Primed numerals | 1980s–90s mechanical; description contains `10'` / `12'` | §2.8 |
| Dense figure | ≥25 numerals on one sheet — exploded assembly or circuit schematic | merge radius, occupancy, box collision |
| Genuinely landscape sheets, not page 2 | flowchart/long-assembly patents | orientation (§5) |
| Both a suffixed label and its 0-form (`14a` **and** `140` recited) | disables the a↔0 rule | conflict detection |

**Public annotated sets** (cited from the sweep, unverified by me):
- **USPTO/NASA TopCoder "Problem PAT"** — 306 manually annotated drawing pages with part-label bounding boxes *and* text, on 1990s-era 300-dpi scans, archived at UCI ML Repository. This is the closest thing to ATTEST's exact annotation schema that exists.
- **DeepPatent2** (Sci Data 10, 2023, 2.7M drawings) and **LANL/ODU** (figshare 13416311, 100 annotated design-patent figures) for scale and for the figure-label half.

**Deliberately out of scope for now:** a 20-sheet double-keyed ground-truth set. It is the honest way to measure recall, and it is weeks of human time. One blind sheet (§3) buys most of the epistemic value for one hour.

---

## 5. Orientation: is 0/90/270 enough?

**Direct answers, both MEASURED on US5447630A.**

### Q1: Can one sheet carry text at multiple orientations, requiring a union rather than a best angle?

**Yes, decisively, and it is already happening on page 2:**

| p.2, 31 admitted labels | count |
|---|---|
| legible upright (0 in angle set) | 13 |
| legible **only** at 90° | 3 (`32`, `29`, `92`) |
| legible **only** at 270° | 2 (`36`, `56`) |
| legible at several rotations but never upright | 11 |

There is no single angle that recovers page 2. Pick 270° and you lose 3 labels *and* all 13 upright ones. Pick 90° and you lose 2 *and* the 13. Pick 0° and you lose 18. D32's union is not a hedge — it is the only correct answer, and D31's token-count vote picked 90° where 270° is human-confirmed truth.

The underlying reason (D32's, and it generalises): **the running header `Sheet 1 of 8` parses at all four angles** because a long line carries enough context to be found however it lies, while an isolated `33` on a leader line reads only when upright in the raster. So rotation is a per-*glyph* property. Any per-*page* orientation scalar is wrong on a mixed sheet by construction. Do not reintroduce one.

### Q2: Is 0/90/270 enough — i.e. is 180° pulling its weight?

**MEASURED: 180° has contributed zero unique admitted labels across all 8 sheets.** Admissions on 180 alone: **0**. Every label whose angle set contains 180 also contains 0, 90, or 270. Dropping the 180° pass would have lost nothing on this corpus.

But keep it, for two reasons that are not "it might help":
1. Its cost is *ingestion time only*, not precision — D32 already holds 180°-only finds to the cross-engine bar, and every 180° phantom (98, 86, 95, 90, 10, 89, 96, 901) was correctly rejected.
2. Removing it is a recall change that would need re-validating on the next corpus anyway.

**However — one honest correction to D32's rationale.** D32 justifies the 180° cross-engine bar with "engines have complementary blind spots, so agreement is real evidence." For 180° specifically that is exactly backwards, and D31 already said so: all three engines are handed the *same* losslessly-flipped raster, so an upside-down `86` genuinely *is* `98` to every decoder. Cross-engine agreement is structurally blind to the very artifact class the bar names. The gate is currently safe only because its population is empty. Add the strobogram-twin check (A9) as a standing assertion — pure manifest, zero cost, currently 0 — so that if a future engagement admits a 180°-only label, someone looks.

### What the quarter-turn set does *not* cover

**Skew.** Non-quarter-turn rotation (0.5–3° is routine on 1990s feed scanners) is untouched by any rotation set, and D32's own further-work column names it. It is not currently a problem — no deskew step exists, so nothing can get the sign wrong — and I would leave it that way. If deskew is ever added:
- Pin the transform math in **one function with one direction of travel**;
- Convert mode `"1"` → `"L"` before any non-90° geometry (Pillow silently forces NEAREST resampling on 1-bpp, which shatters 2.7-px strokes with no warning — harmless today *only* because ROTATIONS are multiples of 90, a load-bearing coincidence that should be a code comment);
- Store coordinates in original-PNG pixel space only, with the transform recorded separately **as data**.

### The real residual on the rotation path

**19 of 145 labels (13%) have no upright read at all.** Their position rests entirely on `unrotate_observation` — hand-written affine math with three branches whose own docstring records that this repo *already shipped a bug in exactly this class* (`x - w` instead of `1 - y - h`, displacing every rotated box by ~0.02, one glyph width). It was caught by Julian marking sheets by eye. The two guarding tests check one box and an axis round-trip; neither is chirally asymmetric, so a transpose or reflection error would pass both.

Fix: the pure-math dihedral test in §4 (asymmetric box, named-corner assertion) plus the A4 frame-integrity assertion over the committed manifest. Both are Layer-0, both engine-free, and together they convert "a human noticed" into "CI is red."

---

## 6. Uncertainty communication

D33 already sets the standing rule and gets the hard part right: discrepancies lead, the caveat leads them, and the wording separates frozen-manifest determinism from the reading's own version-sensitivity. Three specific gaps remain.

### 6.1 The reviewer sees the least trustworthy number and not the most trustworthy one

`patent_figures_view.py:272` renders `<title>{num} (OCR conf {c})</title>` and `:290` renders `OCR conf {a.confidence}`. The record's `engines` and `corroboration` fields — the actual acceptance evidence, and the only signal comparable across engines — never reach the view. So a 1-engine Vision read at its top quantizer bucket and a 3-engine agreement render **identically as "conf 1.0"**.

**Change:** replace the float with the corroboration set and the method — `3 engines · first-pass`, `2 engines · rotated`, `1 engine — unconfirmed`, `↻ text-guided`, `👁 human` — with the single-engine state visually distinct. Keep the float only if it is relabelled *"best single-engine score — not comparable across engines."* This is display-only: nothing is filtered, no label is deleted.

One caution: do not let "3 engines" become the new over-trusted number. The engines share blind spots by construction (same raster, same upright-glyph assumption, same leader-line fusion). The chip belongs *under* the existing "agreement is corroboration, not proof" sentence, and must never gate what is shown.

### 6.2 Some boxes are not confirmable and should not look like confirmations

MEASURED: 13 records are line-level regions rather than numerals (page 3's `140` box encloses `14` and clips `140`); 53 of 145 boxes contain another sighting's centre, 41 of which are not already surfaced by the same-spot conflict alarm. And in the shipped two-column layout the median mark renders at **16.9 CSS px**, p10 at 13.4, minimum 6.0 — 49 of 145 below 16 px, with no zoom anywhere in the 487-line view.

A box a reviewer cannot resolve is a box whose green tick means nothing. Two changes, both additive:
- Render line-level and ambiguous-target boxes in a distinct style — *"region, not numeral"* — so the reviewer knows what they are being asked to confirm.
- Add a magnified crop on click (deterministic PIL over the hash-pinned PNG; assert on the image hash). This filters nothing and touches no manifest.

### 6.3 The disclaimer, worded precisely

D33's wording is already close. The precise version, stated in both directions:

> **What is guaranteed.** The OCR reading of every sheet was performed once, at ingestion, and frozen into a content-hashed manifest. Everything downstream of that file — retrieval, reconciliation, every box on this page — is a pure function of it, byte-identical on every run. No sheet is ever re-read at answer time.
>
> **What is not guaranteed.** The reading itself is model-derived. Three OCR engines were run at four rotations and cross-checked, because each is fallible in ways the others are not — but they share blind spots, and agreement is corroboration, not proof. A different engine version, operating system, or machine could produce a different reading; that would be a new ingestion producing a new manifest with a new hash, not a silent change to this one.
>
> **What the checks can and cannot see.** These checks compare the drawings against the specification. A numeral that OCR missed *and* the specification never recites is invisible to all of them. Absence of a flag is not evidence of correctness: the counts below are a floor on the discrepancies, not a ceiling.
>
> **What a box means.** A drawing is displayed evidence, not a citation. A box marks where the system believes a label sits, for you to confirm by eye. Grounded claims bind to the specification text, never to a drawing.

Add, once §3's checks exist: *"N of M marks on this sheet rest on a single engine"* and *"K marks were confirmed by a named reviewer."* Today those are 43/145 and **0**.

---

## 7. Candidate D# rows

House style: decision / rationale / revisit-trigger. Highest existing row is D33; D24–D27 are candidates awaiting triage. These start at **D34**. All are candidates pending Julian's ratification.

**D34 — Instrument liveness is asserted at ingestion; a silent engine is a hard failure.**
*Decision:* Check `returncode` and surface `stderr` on every subprocess OCR call whenever stdout is empty; assert every declared engine returns > 0 raw observations on every full sheet (whole-sheet only — tiles legitimately return nothing); record the **observed** engine set and per-page `engine_counts` in the manifest rather than the requested list; treat a reduced engine set as a different manifest identity.
*Rationale:* `TESSERACT_OK` tests for a binary on PATH, not a working engine, and `capture_output=True` discards stderr — which is LIBRARY **L0009**, an incident already diagnosed and never installed in code. A dropout does not merely lose one witness: corroboration silently degrades from 2-of-3 to 2-of-2 and the rotated-gate quorum changes. MEASURED: losing Tesseract costs 16 of 145 labels, Vision 25, RapidOCR 14 — with no error, no flag, and a slightly shorter clean-looking list. The fix fails the *ingest* loudly and deletes no labels, so it is on the safe side of the over-filtering asymmetry.
*Revisit:* If a legitimate engine ever reads a genuinely blank sheet — then the assertion needs a documented exemption, not a lowered bar.

**D35 — The frozen manifest gets an identity, and the raster binding is enforced on read.**
*Decision:* Store the manifest's own sha256 (currently printed and discarded), plus `schema_version`, `generator_commit`, and `generated_at`. Verify `image_sha256` in `figures_map.load_manifest()` as a hard failure, mirroring `store.verify_document`'s "I3 enforced on every read". Refuse to overwrite an existing manifest without `--force`; archive the previous one. Commit a hash-only sidecar (manifest sha + per-page image sha + generator commit) — no client content — so drift becomes a reviewable git diff.
*Rationale:* `image_sha256` has exactly one consumer in the tree: the line that writes it. So I3 is GUARANTEED for text and merely declared for drawings — a re-fetch or re-crop without re-OCR puts every normalized box on a different raster and renders confident boxes at wrong locations, silently. And `out.write_text(...)` over a gitignored file means a re-run destroys the prior evidence map with no diff. Pure recording; nothing is filtered.
*Revisit:* If engagement artifacts ever become committable (they should not — client-confidential), the sidecar collapses into the artifact itself.

**D36 — The label alphabet is validated against the specification before any OCR runs.**
*Decision:* At ingestion, probe the spec for 4+-digit reference numerals in element-noun position and for `\d{1,3}[A-Z]` labels; fail loudly if the extractor cannot express a label the patent recites. Widen `_NUMERAL` / `_DIGIT_RUN` / `_LABEL` to `\d{1,4}` with an optional case-insensitive suffix and an optional prime — spec side **first**, image side second, and generalise the furniture guard before either.
*Rationale:* All three extraction sites cap at three digits, so the figure-keyed 1000-series (dominant in post-2000 art) yields *zero* labels — and the coverage report then reads perfectly clean, because both sides of the reconciliation are empty. The uppercase half is worse than an omission: `12A` is silently truncated to `12` on the TEXT side, which is where grounding binds. The obvious check (compare spec inventory to image regex) passes vacuously; the probe must come from outside the parser.
*Revisit:* If a corpus arrives with 5-digit numerals or a suffix convention outside `[A-Za-z]`.

**D37 — Rotation-transform correctness is a standing assertion, not a human's eye.**
*Decision:* Add (a) a pure-math dihedral test of `unrotate_observation` using a deliberately asymmetric box, asserting four-fold composition is identity, that `unrotate(k)`/`unrotate(360−k)` are mutual inverses, and that one *named corner* maps to its known destination; and (b) a manifest-invariant assertion that per-angle and per-engine median centre displacements stay below 0.005 and the `y → 1−y` mirror-pair count stays at 0.
*Rationale:* 19 of 145 labels have no upright read, so their position rests entirely on this function — which has already shipped one bug of exactly this class (`x - w` for `1 - y - h`, one glyph width, caught by Julian marking sheets). The two existing tests check one box and an axis round-trip; neither is chirally asymmetric, so a transpose or reflection error passes both. MEASURED today: cross-angle medians ≤ 0.0011, cross-engine ≤ 0.0013, mirror pairs 0 of 1499 — ~10× headroom on the proposed threshold. Engine-free and CI-blocking.
*Revisit:* If a deskew step is ever added — then the transform is no longer a quarter-turn and the algebra needs re-deriving, not re-thresholding.

**D38 — Preprocessing is per-engine, and any change is judged per-engine, never in aggregate.**
*Decision:* Record each engine's preprocessing chain per sheet in the manifest. No global image transform may be introduced without a per-engine total-recall report over the frozen corpus; ship a frozen blurred-run manifest as a **negative** fixture proving the check fires. Gate on per-engine **total** recall and the accepted union — never on the per-engine *unique* set.
*Rationale:* MEASURED: `convert("L")` + GaussianBlur(σ=0.8) takes Tesseract on drawings-page-3 from 18 numeric tokens to **zero** — its thresholder short-circuits on 1-bpp input, and re-graying re-Otsus 2.7-px strokes. The aggregate label count barely moves, so the obvious next "improvement" (blur because it helps Vision) is invisible in the only number anyone would check. The per-engine dispatch is already ~90% the architecture; this pins it. The unique-set criterion is wrong because a label moving from Tesseract-only to Tesseract+Vision *leaves* the unique set while becoming strictly more admissible.
*Revisit:* A sheet with heavy stipple or hatching where blur genuinely helps every engine — then per-engine chains are the answer, still not a global one.

**D39 — Tesseract's operating resolution is pinned explicitly, and the change is validated against the human roster before re-freezing.**
*Decision:* Pass an explicit `--dpi` (and `-l eng --oem 1 --tessdata-dir <resolved>`) on every Tesseract invocation — original and derived alike — so angle 0 and angle 90 are read under the same configuration. Then re-run `audit_sheet_labels.py` against the human-confirmed roster and choose the pinned value **on evidence**.
*Rationale:* MEASURED: source PNGs carry `dpi=(299.9994, 299.9994)`; `.rotate(...).save(...)` writes no pHYs chunk, so derived copies are untagged and Tesseract estimates resolution from content — 378 to 2269 across sheets of the *same* scan. The D32 union therefore mixes two engine configurations. **Do not blind-apply the obvious fix:** passing `dpi=src.info['dpi']` measurably *deletes* sheet 3's real view-marker `A`, the exact finding `marker_band_rescue`'s docstring cites as its reason to exist. Pin the parameter, then measure.
*Revisit:* A Tesseract version whose estimator is documented and stable, or a corpus where the pinned value measurably underperforms.

**D40 — Conflict detection covers every label class, and the two radii are one constant.**
*Decision:* Delete the `isdigit()` conjunct in `_same_spot_conflicts` so suffixed and letter labels (`12a`, `J2`, `D1`) can be reported as disagreements, comparing normalized strings. Make the conflict radius and the merge radius a single module constant so they cannot drift. Keep the existing unresolved-report path — surface both readings, never pick a winner.
*Rationale:* Both are gate *removals* that delete nothing. MEASURED: the type gate exempts 7 co-located different-label pairs (6 are a↔0, already caught elsewhere; 1 — `J2` vs `52` on page 3, Δ 0.002, tesseract-only, confidence 0.0 — is a genuine phantom element invisible to every check). MEASURED on the radii: the closest genuine same-token pair separation is 0.0202 against a merge radius of 0.02 — **0.7 px of headroom** — and 13 records are one physical mark stored twice because merge compares *left edges* while RapidOCR returns boxes 2–3× wider than Tesseract for the same glyph. Compare centres or require overlap; widen x only, never y.
*Revisit:* A denser patent where the safe window closes — then the radius must be derived per sheet from measured glyph geometry, with the split-record and over-merge counts reported in the same commit.

**D41 — The reviewer surface shows corroboration, not a pooled score; the human channel is append-only.**
*Decision:* Carry `engines`, `angles`, `method` and `corroboration` into the rendered box and chip; relabel or retire the displayed float. Render line-level and ambiguous-target boxes in a distinct "region, not numeral" style, and add a deterministic magnified crop on click. Make `manual_annotations.json` append-only with I5's shape — a human confirmation is never deleted or overwritten, only superseded with a reason — and flag when an OCR sighting lands where a superseded human record sat. Print adjudication coverage; report it, never gate on it.
*Decision (negative, equally binding):* Do **not** gate on any of these. Every filter proposed in this review has been rejected for the same reason.
*Rationale:* MEASURED: Vision emits 3 distinct confidence values over 547 raw reads, so `merge_same_spot_numerals`' `-confidence` sort means the drawn box is chosen by a quantizer; 3 records at "conf 1.0" are single-engine while 49 are three-engine and they render identically. The median mark renders at 16.9 CSS px with no zoom, and 49 of 145 fall below 16 px — a mark too small to read is a confirmation that cannot mean anything. On the sidecar: ROADMAP:269 records the one human adjudication this project has ever produced (the FIG-2 `A`, proven invisible to Vision at every scale), and today the file is `[]` while page 3 carries an `A` from a 0.668-confidence single-engine tesseract read. The human record was consumed by a machine read and the substitution is now unfalsifiable. MEASURED adjudication coverage: **0 of 145**.
*Revisit:* When enough adjudicated outcomes exist to draw a reliability curve — at which point a calibrated number may be displayed, and not before.

---

## What I would do first, in order

1. **One blind sheet** (one hour, human). Before looking at the overlay again. It is the only stratum that cannot be recreated later, and it anchors everything else.
2. **`scripts/audit_manifest.py`** — Tier A, ~150 lines total, no engine, no ground truth. Four of its thirteen checks fire on the current corpus. Commit the baselines.
3. **D34 + D35** — instrument liveness and manifest identity. ~40 lines between them, both pure recording, both closing a gap where the artifact can be destroyed or the guarantee is declared rather than enforced.
4. **C1/C2/C3 at intake** — three text-only probes, milliseconds, run before any OCR on the next patent. They decide whether §2.3, §2.8 and §2.9 apply at all, and on US5447630A they correctly return nothing.

Everything else waits for the second patent. That is not caution — it is that most of the constants in this pipeline were fitted to one document, and the honest next measurement is a second document, not a cleverer detector.