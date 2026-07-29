# Corpus fit record — US8046721B2

**The second corpus.** First end-to-end run of the RT-6 protocol
([`corpus_fitting.md`](corpus_fitting.md)), which existed as an untested hypothesis until
this run. Date: 2026-07-28.

| | |
|---|---|
| Document | **US8046721B2** — "Unlocking a device by performing gestures on an unlock image" (Apple, granted 2011) |
| Why chosen | Post-2000 software art, to stress exactly what corpus 1 could not: the figure-keyed **1000-series**, **6-wide sub-figure ranges** (FIGS. 11A-11F), and numbering that starts at 100 rather than 1 |
| Ingested | 74,286 chars, `sha256=3227d8d5d9d5…`, via `scripts/ingest_files.py` |
| Store | `corpus/engagements/US8046721B2/store` (gitignored; re-fetch from Google Patents to reproduce) |
| Corpus 1 regression | **None.** US5447630A still parses 8 figures, unchanged, throughout. |

**Headline: 2 constants did not transfer, 1 transferred only after a root-cause bug was
fixed, 1 was validated, 1 is inert.** RT-6's acceptance criterion asked for at least one
non-transferring constant. The protocol found three problems, and the falsifiers written
into the registry predicted two of them in advance.

---

## 1. `_FIG_CAPTION` — a real bug, found by the falsifier for a *different* constant

The registry's falsifier for `_CAPTION_GAP = 400` read: *"A patent with a long prose aside
between two figure captions."* It fired. But the diagnosis pointed somewhere else, which is
the most useful thing that happened in this run.

`parse_figures` returned 22 figures and **silently dropped FIG. 6, 9 and 10** — each
recited three times, each with a caption in the Brief Description. The pattern in the
misses was the clue: every figure found was either ≤5 or letter-suffixed.

Root cause: `_FIG_CAPTION` required `FIG. N <verb>`, so a **range caption** could not match
— in "FIGS. 4A-4B illustrate the GUI display", `-4B` sits between the number and the verb.
That cost twice. The caption was lost, *and* the now-unmatched text inflated the gap to the
next caption:

```
FIG 1    gap    0        FIG 6    gap  450   <-- BLOCK BREAKS (limit 400)
FIG 2    gap  110        FIG 9    gap  497
FIG 3    gap  150
```

Fixed by giving the caption pattern an optional range tail (**D43**). Result: **25 figures**
— the complete set (1, 2, 3, 4A-4B, 5A-5D, 6, 7A-7D, 8A-8C, 9, 10, 11A-11F) — and the
largest in-run gap fell to **160**, comfortably inside 400.

So `_CAPTION_GAP = 400` **did transfer**; the apparent threshold failure was a regex
failure. Worth recording as a general lesson: *a threshold that appears too tight is
sometimes measuring a parse failure upstream of it.* Loosening it would have masked the
bug and left FIG 6/9/10 attributed to the wrong captions.

## 2. `support.THRESHOLD = 15.0` — did not transfer, and fails toward false abstention

| Query | Top BM25 | Verdict |
|---|---|---|
| "how is the device unlocked" | **4.56** | **below** floor — Cairn would abstain |
| "what is the optical intensity of a user-interface object" | 22.72 | above floor |
| "what colour is the moon" | 0.00 | below floor (correct) |

The first row is the finding. That question is the patent's entire subject, answered
throughout, and the floor calibrated on EDGAR rejects it. Cairn would return `insufficient`
on an answerable question — a **false abstention**, which is the failure mode that looks
responsible and is therefore easy to ship.

The registry predicted this precisely (*"Any new corpus. A BM25 score is not comparable
across corpora"*), and this is why: BM25 scores scale with document length and term
distribution, so the number is meaningless off its calibration corpus.

**Not "fixed" by retuning the constant.** `scripts/calibrate_threshold.py` exists; what does
not exist is any mechanism *requiring* a per-corpus calibration before a store is used, or
even recording which corpus a threshold was calibrated against. That gap is the real
finding and it is an architectural one — filed as **RT-9**, not patched here.

## 3. `_NOT_A_LABEL` — did not transfer, worse than predicted

`acronym_labels` returned **34** acronym "labels" on this corpus, including:

```
BRIEF  FIELD                          <- section headings
CDMA  GSM  CMOS  CPU  GPS  IEEE  AAC  CODEC  EDGE   <- technology acronyms
```

None is a reference label. Corpus 1 needed only `CFM RPM PSI GPM` excluded; an electronics
patent breaks that list completely, and the prediction (*"a domain with different unit
acronyms"*) understated it — **section headings leak in too**.

**Deliberately not fixed by extending the blocklist.** That is the whack-a-mole the protocol
warns against (L0006, five instances), and each new corpus would need its own list. The
structural point: `acronym_labels` has no frequency floor *because drawings adjudicate* —
an acronym is a real label if OCR locates it on a sheet. On a corpus with no OCR'd drawings
that adjudicator is absent, so the function over-generates by design. It should not be
consumed without drawing evidence, and nothing currently enforces that. Also **RT-9**.

## 4. `NUMERAL_DIGITS = 4` — validated on independent evidence

13 four-digit numerals extracted (`1000`–`1108`), every one of which the pre-D34 three-digit
cap made invisible. Independent confirmation that D34/D42 was necessary rather than
speculative, on a corpus chosen before the numerals were inspected.

No 5+-digit label shapes exist in this document, so 4 remains the right cap for this domain.

## 5. `MIN_LOCATABLE_NUMERAL = 10` — inert, therefore still untested

The lowest numeral this patent recites is **36**; numbering runs 100-1108. The floor
suppresses **nothing** here.

This is not a pass. The registry flags it as the constant most likely to be wrong on a new
corpus *and* one that fails silently, and this run produced **no evidence either way**. A
third corpus with single-digit numerals on clean modern drawings is still needed. Recording
"inert" rather than "transferred" is the point — a constant no test exercised has not been
validated, and calling it validated is how a fitted value quietly becomes a law.

---

## What this run says about the protocol itself

- **The falsifiers earned their place.** Two of three failures were predicted in advance by
  the `falsifier` field, and the third (§1) was found by chasing a falsifier to a different
  constant. Writing "what would prove this wrong" turned out to be the reusable artifact.
- **Step 1 was correctly ordered.** Probing expressible vocabulary first is what made the
  4-digit result trustworthy; had the extractor been unable to express the 1000-series, the
  coverage report would have read clean over an empty map.
- **The protocol has no drawings step yet.** This run was text-only — no sheets were fetched
  or OCR'd — so every OCR-side constant (the 0.02 merge radius with 0.7 px of headroom, the
  0.88 header band, the strobogrammatic map) remains untested on corpus 2. That is the
  largest gap in this record and the honest next step.
- **Two of three failures were not fixable by changing a number.** Both needed a mechanism
  (per-corpus calibration; refusing to consume an unadjudicated label set). A protocol that
  only re-tunes constants would have declared success and shipped a false abstention.
