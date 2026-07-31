"""adjudication — the reviewer's judgment, recorded so it cannot be lost (RT-7a, D47).

**Why this exists.** Cairn had no durable input channel for the expert whose judgment it
exists to support. The only way a human conclusion entered the system was a hand-edited
JSON array, `figures/manual_annotations.json` — a *mutable* file with no history and no
tamper evidence. It failed exactly as that design must: a reviewer's visual confirmation
of the view-marker "A" on US5447630A's FIG. 2 was later replaced by a single-engine OCR
read, and because the file simply held the current value, the confirmation is
unrecoverable. Nothing detected it; nothing could.

**The rule this module enforces:** a human adjudication is *evidence with provenance*, and
evidence is never edited. Corrections are appended and point back at what they supersede,
so the earlier judgment stays legible — including the fact that it was later revised, and
by whom. Reading the "current" view is a fold over history, never a truncation of it.

The append-only guarantee is not re-implemented here. It reuses `AuditLog`'s hash chain
(I5): one append-only mechanism in the system, not two, so tamper evidence is identical
wherever it matters and `verify_chain()` means the same thing in both places.

**Machine reads may never supersede a human mark.** `supersede_ok` refuses it at the API,
because the loss above was precisely a machine value displacing a human one. A machine can
*disagree* — that is recorded as a separate observation and surfaced as a conflict — but it
cannot overwrite.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

from .audit import AuditLog, TamperError

__all__ = [
    "CONFIRM", "CORRECT", "NOTE", "REFUTE",
    "Adjudication", "AdjudicationLog", "TamperError",
    "effective", "import_legacy_sidecar",
]

# What a reviewer can assert. Deliberately small: each is a different CLAIM about the
# evidence, and collapsing them would lose why a mark is in the record.
CONFIRM = "confirm"    # "this mark is really there" — a positive human sighting
REFUTE = "refute"      # "the tool located this, and it is not there"
CORRECT = "correct"    # "this is 14a, not 140" — a reading replaced, with the right value
NOTE = "note"          # free-text reasoning attached to a target; asserts nothing itself

KINDS = frozenset({CONFIRM, REFUTE, CORRECT, NOTE})


@dataclass(frozen=True)
class Adjudication:
    """One recorded act of human judgment.

    `target` is deliberately an opaque dict rather than a typed figure reference: the
    same log must hold judgments about drawing marks, about spans, and about findings
    that do not exist yet. `target_kind` names how to read it.
    """

    adj_id: str            # stable id, supplied by the caller (no clock, no RNG — I6)
    kind: str              # confirm | refute | correct | note
    target_kind: str       # e.g. "figure-numeral", "span", "finding"
    target: dict           # what this judgment is about
    by: str                # the human who made it — provenance is not optional
    on: str                # ISO date, supplied (cores stay clock-free)
    note: str = ""
    value: dict = field(default_factory=dict)   # the corrected reading, for CORRECT
    supersedes: str | None = None               # adj_id this revises; that one REMAINS

    def to_payload(self) -> dict:
        d = asdict(self)
        d["record"] = "adjudication"
        return d


def _valid(a: Adjudication) -> None:
    if a.kind not in KINDS:
        raise ValueError(f"unknown adjudication kind {a.kind!r} (expected one of {sorted(KINDS)})")
    if not a.adj_id or not a.by or not a.on:
        raise ValueError("an adjudication needs adj_id, by and on — provenance is not optional")
    if a.kind == CORRECT and not a.value:
        raise ValueError("a 'correct' adjudication must carry the corrected value")


class AdjudicationLog:
    """Append-only, hash-chained record of human judgments (RT-7a).

    Thin on purpose: it is `AuditLog` with a payload contract and the supersession rules.
    There is no update and no delete, and there is no way to write a payload that is not
    an adjudication.
    """

    def __init__(self, path: Path | str):
        self._log = AuditLog(path)
        self.path = self._log.path

    def append(self, adj: Adjudication, *, supersede_ok: bool = True) -> Adjudication:
        """Record a judgment. `supersede_ok=False` refuses to revise an existing one.

        Machine-originated writers must pass `supersede_ok=False`. That is the guard the
        lost "A" needed: a machine may add its own observation, but it may not displace a
        human's. A human revising their own earlier call passes the default.
        """
        _valid(adj)
        known = {a.adj_id for a in self.all()}
        if adj.adj_id in known:
            raise ValueError(
                f"adjudication {adj.adj_id!r} already recorded — this log is append-only. "
                f"To revise it, append a new entry with supersedes={adj.adj_id!r}.")
        if adj.supersedes is not None:
            if adj.supersedes not in known:
                raise ValueError(f"supersedes {adj.supersedes!r}, which is not in this log")
            if not supersede_ok:
                raise PermissionError(
                    f"refusing to supersede {adj.supersedes!r}: this writer may not "
                    f"overwrite a recorded judgment. Record a separate observation "
                    f"instead — a disagreement is evidence, a silent replacement is loss.")
        self._log.append(adj.to_payload())
        return adj

    def all(self) -> list[Adjudication]:
        """Every judgment ever recorded, in order, including superseded ones."""
        out = []
        for e in self._log.entries():
            p = e.payload
            if p.get("record") != "adjudication":
                continue
            out.append(Adjudication(**{k: v for k, v in p.items() if k != "record"}))
        return out

    def verify_chain(self) -> None:
        self._log.verify_chain()

    def effective(self) -> list[Adjudication]:
        return effective(self.all())


def effective(entries: list[Adjudication]) -> list[Adjudication]:
    """The judgments currently in force — a FOLD over history, not a truncation of it.

    An entry is superseded if a later entry names it. Superseded entries stay in `all()`
    forever; this view only decides which ones speak for the present. `note` entries are
    never superseded away by design: a note is reasoning attached to a target, not a
    competing claim about it, so keeping both is correct.
    """
    replaced = {a.supersedes for a in entries if a.supersedes}
    return [a for a in entries if a.adj_id not in replaced]


def import_legacy_sidecar(path: Path | str, *, by: str, on: str) -> list[Adjudication]:
    """Read the old mutable `manual_annotations.json` into adjudication records.

    Migration is one-way and lossy in one direction only: the legacy file holds no
    history, so whatever it currently contains is all that can be recovered. That is the
    defect, preserved honestly rather than papered over — the entries are attributed to
    the supplied reviewer with a note saying the provenance was reconstructed.
    """
    p = Path(path)
    if not p.exists():
        return []
    raw = json.loads(p.read_text(encoding="utf-8"))
    out = []
    for i, a in enumerate(raw):
        out.append(Adjudication(
            adj_id=f"legacy-{i:03d}", kind=CONFIRM, target_kind="figure-numeral",
            # w/h included: a migration that silently narrows a recorded box is the same
            # class of loss this module exists to prevent, just smaller.
            target={k: a[k] for k in ("page", "numeral", "x", "y", "w", "h") if k in a},
            by=by, on=on,
            note=(a.get("note", "") + " [migrated from manual_annotations.json; the "
                  "original file kept no history, so this provenance is reconstructed]"
                  ).strip()))
    return out
