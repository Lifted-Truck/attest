"""calibration — the record that says which corpus a support floor was fitted to (RT-9).

`support.THRESHOLD` is a **BM25 score**, and a BM25 score is not comparable across
corpora: it scales with document length and term distribution. Applying one corpus's
floor to another is not approximately right, it is meaningless — and it fails toward
**false abstention**, which is the dangerous direction for a system whose entire claim is
that it abstains honestly. A refusal on an answerable question looks like diligence.

Measured on 2026-07-28 (D43): the query *"how is the device unlocked"* — the whole subject
of US8046721B2 — scores **4.56** against the EDGAR-calibrated floor of **15.0**. Cairn
would have returned `insufficient` on a question the corpus answers throughout, and
nothing anywhere would have said why.

`scripts/calibrate_threshold.py` already existed. What did not exist was any way to tell a
calibrated store from an uncalibrated one. So this module does one thing: it makes the
provenance of a threshold a **fact carried by the store**, and makes its absence visible in
the tool output and the audit log rather than silent.

The design deliberately WARNS rather than refuses. Refusing would be defensible, but it
would make an uncalibrated store unusable for exploration — and the honest failure here is
not "you may not ask", it is "this abstention decision is not trustworthy and you must be
told so". A warning that reaches the agent, the audit record and the reviewer is stronger
than a hard stop the operator learns to route around.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

CALIBRATION_FILE = "calibration.json"


@dataclass(frozen=True)
class CalibrationRecord:
    """Which corpus a support floor was fitted to, and how."""

    threshold: float
    corpus_id: str            # the store this was fitted against
    doc_ids: list[str]        # documents present at calibration time
    corpus_hash: str          # content hash over those documents (drift detection)
    calibrated_on: str        # ISO date, supplied by the caller (cores stay clock-free)
    method: str               # e.g. "golden-gap" (support.calibrate_threshold)
    n_present: int
    n_absent: int
    # Whether the fit actually SEPARATES answerable from content-absent items. A floor
    # fitted on overlapping scores is a number, not a separator: some unanswerable
    # questions outscore some answerable ones, so no single threshold can divide them.
    # Recorded because "calibrated" must not be able to mean "we ran the fitter".
    separable: bool = True
    gap: float = 0.0          # min(answerable) - max(content-absent); negative = overlap

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2, sort_keys=True) + "\n"


def corpus_hash(doc_ids: list[str], hashes: list[str]) -> str:
    """A stable hash over the corpus's identity — ids paired with content hashes.

    Sorted, so it does not depend on directory order. If a document is added, removed or
    edited after calibration, this changes and the record is stale by construction (I3's
    pattern applied to a fitted value rather than to text).
    """
    import hashlib
    blob = "\n".join(f"{d}:{h}" for d, h in sorted(zip(doc_ids, hashes, strict=True)))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def write(store_dir: str | Path, record: CalibrationRecord) -> Path:
    p = Path(store_dir) / CALIBRATION_FILE
    p.write_text(record.to_json(), encoding="utf-8")
    return p


def load(store_dir: str | Path) -> CalibrationRecord | None:
    """The store's calibration record, or None if it has never been calibrated."""
    p = Path(store_dir) / CALIBRATION_FILE
    if not p.exists():
        return None
    d = json.loads(p.read_text(encoding="utf-8"))
    return CalibrationRecord(**d)


@dataclass(frozen=True)
class ThresholdChoice:
    """A support floor plus an honest account of where it came from."""

    threshold: float
    calibrated: bool
    warning: str | None       # non-None whenever the floor is not this corpus's own

    def to_json(self) -> dict:
        d = {"threshold": self.threshold, "calibrated": self.calibrated}
        if self.warning:
            d["warning"] = self.warning
        return d


def describe(store_dir: str | Path, doc_ids=None, hashes=None) -> tuple[str, bool]:
    """The calibration verdict as a sentence, plus whether it counts as calibrated.

    Every surface that shows calibration state uses this: the console header, the
    client-facing report, and anything added later. Three copies of the same branch is
    how a store comes to read "calibrated" on one surface and "non-separable" on
    another — which happened, and is exactly the class of drift this project keeps
    designing against.
    """
    choice = resolve(store_dir, 0.0, doc_ids, hashes)
    rec = load(store_dir)
    if rec is None:
        return ("This corpus has NO calibration record — the support floor was fitted "
                "elsewhere. A relevance score does not transfer between corpora, so "
                "abstentions here are unreliable and skew toward refusing questions the "
                "documents can in fact answer. Run scripts/calibrate_threshold.py --write.",
                False)
    if not rec.separable:
        return (f"Fitted {rec.calibrated_on}, but answerable and content-absent scores "
                f"DO NOT SEPARATE (overlap {abs(rec.gap):.1f}). No single floor divides "
                f"them, so the content-absence check is close to inert here and "
                f"abstentions rest on the agent's reasoning rather than on the score.",
                False)
    if choice.warning:                      # stale — the corpus moved under the fit
        return (choice.warning, False)
    return (f"Support floor {rec.threshold}, calibrated {rec.calibrated_on} against this "
            f"corpus ({rec.method}, {rec.n_present} answerable / {rec.n_absent} "
            f"content-absent). Abstentions here are fitted to these documents.", True)


def resolve(store_dir: str | Path, default: float,
            live_doc_ids: list[str] | None = None,
            live_hashes: list[str] | None = None) -> ThresholdChoice:
    """Pick the support floor for this store and say plainly where it came from.

    Three outcomes, all of them explicit:
      · calibrated and current  → the store's own floor, no warning;
      · calibrated but STALE    → the store's floor, with the drift named (the corpus
        changed since the fit, so the separation it was fitted to no longer holds);
      · never calibrated        → the default, with a warning naming it as foreign.
    """
    rec = load(store_dir)
    if rec is None:
        return ThresholdChoice(
            default, False,
            f"UNCALIBRATED STORE: applying a support floor of {default} that was fitted "
            f"to a different corpus. A BM25 score does not transfer between corpora, so "
            f"abstention decisions here are unreliable and skew toward FALSE ABSTENTION "
            f"(refusing answerable questions). Run scripts/calibrate_threshold.py.")

    if live_doc_ids is not None and live_hashes is not None:
        now = corpus_hash(live_doc_ids, live_hashes)
        if now != rec.corpus_hash:
            return ThresholdChoice(
                rec.threshold, False,
                f"STALE CALIBRATION: the floor {rec.threshold} was fitted on "
                f"{rec.calibrated_on} against corpus {rec.corpus_hash[:12]}…, but this "
                f"store now hashes to {now[:12]}… — documents were added, removed or "
                f"edited since. Re-calibrate.")
    if not rec.separable:
        return ThresholdChoice(
            rec.threshold, False,
            f"NON-SEPARABLE CALIBRATION: the floor {rec.threshold} was fitted on "
            f"{rec.calibrated_on}, but answerable and content-absent scores OVERLAP by "
            f"{abs(rec.gap):.1f}. No single threshold divides them, so this floor cannot "
            f"be doing the work it appears to do — abstention here rests on the agent's "
            f"reasoning, not on the score.")
    return ThresholdChoice(rec.threshold, True, None)
