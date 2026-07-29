# Corpus-fitting protocol

**What this is.** The procedure for pointing Cairn at a corpus it has never seen. It
exists because of one admission (Julian, 2026-07-26): *the deterministic architecture
will not catch every case, and pretending otherwise is the failure mode.* This is the
guidance layer that sits between the engine and a particular corpus.

**Status:** ROADMAP **RT-6**. Binding on any new-corpus work. The mechanizable half is
enforced by `tests/test_corpus_fit.py`; the rest is procedure a human or agent follows.

---

## The situation this protocol addresses

Every extraction constant in Cairn was fitted to **one 1995 mechanical patent**
(US5447630A) or **one Apple 10-K**. `src/cairn/corpus_fit.py` inventories them: at the
time of writing, **8 of 12 are corpus-specific**, meaning "expect this to be wrong until
re-measured" — not "probably fine."

And every single one was discovered the same way: **a human noticed a miss.** Not one was
found by a test. That is not a discipline failure; it is that the system is measured for
what it *contains* and never for what it silently *decided*.

So the protocol's steps are not best practices in general. They are the specific moves
that historically caught these failures, written down so the next corpus costs less than
the first.

---

## Step 0 — Read the inventory before touching anything

```bash
python scripts/corpus_fit_report.py
```

Read the `falsifier` field on every `corpus`-scoped entry. Each one names the observation
that would show the value does not transfer. That list *is* your test plan — you are not
inventing checks, you are executing ones already written down.

The two entries to look at first, because they fail **silently**:

- **`MIN_LOCATABLE_NUMERAL = 10`** — suppresses locations rather than producing wrong
  ones. Fitted because on a 1990s raster scan every sub-10 read was noise. On a clean
  modern vector PDF this is probably wrong, and nothing will tell you.
- **`merge_same_spot_numerals(radius=0.02)`** — the closest genuine same-token pair on
  US5447630A sits at 0.0202, about **0.7 px of headroom**, which was never measured when
  the value was chosen. On a denser sheet two real marks merge into one and the survivor
  keeps only the higher confidence. The miss leaves no trace.

## Step 1 — Probe for vocabulary the extractor cannot express, *before* trusting coverage

This step comes early because skipping it makes every later measurement meaningless.

The failure it prevents (D34): the numeral pattern capped at three digits, so the
figure-keyed 1000-series (`FIG. 10` → 1000/1010/1020) that dominates post-2000 software
patents was unreadable. On such a patent **both sides** of the drawing/spec reconciliation
come back empty — and a coverage report reads **perfectly clean over an empty map**.

A clean report is therefore not evidence of anything until you have confirmed the
extractor can express what the corpus recites. Probe the raw text directly for label
shapes, and diff against what `reference_numerals()` returns. Non-empty difference means
stop and widen the vocabulary; do not proceed to measure recall.

## Step 2 — Inspect what the extractor DISCARDS, not only what it keeps

`L0006`, five instances. Over-filtering is the repeated failure of this project, and it is
**asymmetrically invisible**: a false positive leaves an artifact a human can point at; a
deleted real label leaves nothing — no low-confidence row, no flag, no diff, no log line.

Instances so far: a `≥10` numeral floor deleted real single-digit numerals; a `≥2`-mention
floor deleted CZ and CL; an OCR confidence floor would have deleted the *real* numerals,
because leader lines fuse with digits and drive confidence down — the low-confidence reads
were the true ones.

So: for every filter on the path, print the rejected set and read it. If you cannot
enumerate what a filter discarded, you cannot claim it is safe.

## Step 3 — Test each instrument on a known-positive before recording a negative

`L0009`, and the corollary that stayed prose for four milestones until a swarm found it
uninstalled (`L0010`).

An "unreadable by everything" conclusion is load-bearing and earns a positive control
first. A dead Tesseract — its error on stderr, never checked — was once mistaken for a
Tesseract *blind to this corpus*, and that false conclusion nearly shipped as a finding
about the corpus. **A broken instrument reads exactly like a clean sheet.**

This applies to the checks you add during fitting, not only to engines. When you write a
new gate, break something on purpose and confirm it fires. Every instrument in this repo
that was trusted without that step was later found inert or wrong.

## Step 4 — Blind-annotate one document before looking at any overlay

Do this **before** opening the review GUI for the new corpus. Once you have seen the
overlay you cannot un-see it, and an uncontaminated recall stratum for that document can
never be recreated.

One hour buys the only honest recall denominator available. The specification gives a free
denominator for *recited* numerals, but says nothing about marks the spec never recites —
view letters, dimension callouts, unlabelled parts. Only a human annotating blind gives
that.

Write it to the annotation sidecar with `method: "human"` provenance. **Note the standing
defect:** the sidecar is not yet append-only, and a human confirmation of FIG-2's "A" was
already overwritten by a single-engine OCR read and is unrecoverable. Fixing that is
RT-7's prerequisite; until it lands, keep a copy outside the sidecar.

## Step 5 — Record the fit, with evidence and a falsifier

Every value you change or add gets a `FittedConstant` in `src/cairn/corpus_fit.py`:

| Field | What it must contain |
|---|---|
| `value` | The scalar, pinned. `None` only for open-ended lexical sets that legitimately grow. |
| `scope` | `corpus` / `domain` / `universal` — a claim about generality, read first on the next corpus. |
| `fitted_on` | The evidence that set it. Never "seemed right". |
| `falsifier` | **The operative field.** What observation would show this does not transfer? |

`pytest -m layer0` then enforces two things: a scalar retuned without updating its
provenance fails, and a new tunable added to a fitted module without being registered or
explicitly exempted fails. Both were proved on known-positives before being trusted.

Provenance without a falsifier is a story. A constant with no recorded provenance is
indistinguishable from a law.

---

## What this protocol does not do

Stated plainly, because a protocol that implies completeness is worse than none:

- **It does not make fitting safe.** It makes fitting *visible*. The constants will still
  be wrong on a new corpus; the difference is that you know which ones to doubt and what
  would prove it.
- **It cannot measure true recall.** Only a blind human annotation does, and only for the
  document annotated.
- **It cannot catch a corroborated-but-wrong reading.** Three engines fed the same
  corrupted pixels agree with each other. Cross-engine agreement is corroboration, not
  proof — a defect living in the pixels rather than the models is invisible to redundancy
  (the D31/D32/D36 lesson, three instances).
- **It has never been run end-to-end.** RT-6's acceptance criterion requires a second
  patent producing a written fit record and at least one constant that did not transfer.
  Until that happens, this document is a hypothesis about what will help.
