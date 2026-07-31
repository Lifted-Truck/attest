"""Standing tests for the append-only adjudication record (RT-7a, D47).

The motivating incident is concrete and must stay uncatchable-again: a reviewer's visual
confirmation of the view-marker "A" on US5447630A's FIG. 2 was replaced by a
single-engine OCR read in a mutable JSON array, and is unrecoverable.
"""

from __future__ import annotations

import json

import pytest

from cairn.adjudication import (
    CONFIRM,
    CORRECT,
    NOTE,
    REFUTE,
    Adjudication,
    AdjudicationLog,
    TamperError,
    effective,
    import_legacy_sidecar,
)

pytestmark = pytest.mark.layer0


def _adj(adj_id="a1", kind=CONFIRM, **kw):
    base = dict(adj_id=adj_id, kind=kind, target_kind="figure-numeral",
                target={"page": 3, "numeral": "A", "x": 0.84, "y": 0.19},
                by="J. Smith", on="2026-07-28")
    base.update(kw)
    return Adjudication(**base)


def test_a_recorded_judgment_cannot_be_rewritten(tmp_path):
    """The core guarantee. Re-recording the same id is refused outright — there is no
    update and no delete, only a new entry that names what it revises."""
    log = AdjudicationLog(tmp_path / "adj.jsonl")
    log.append(_adj())
    with pytest.raises(ValueError, match="append-only"):
        log.append(_adj(note="second thoughts"))


def test_a_machine_writer_may_not_supersede_a_human_judgment(tmp_path):
    """THE incident, made impossible. A machine may disagree — that is an observation and
    is evidence — but it may not displace a recorded human call."""
    log = AdjudicationLog(tmp_path / "adj.jsonl")
    log.append(_adj("human-1", note="I can see the A on FIG 2"))

    machine = _adj("ocr-1", kind=CORRECT, supersedes="human-1",
                   by="tesseract-5.5.2", value={"numeral": "4", "x": 0.84, "y": 0.19})
    with pytest.raises(PermissionError, match="refusing to supersede"):
        log.append(machine, supersede_ok=False)

    # The human's judgment is untouched and still in force.
    assert [a.adj_id for a in log.effective()] == ["human-1"]


def test_superseding_keeps_the_earlier_judgment_in_history(tmp_path):
    """A revision is a fold over history, never a truncation of it: the earlier call
    stays legible, including the fact that it was later revised and by whom."""
    log = AdjudicationLog(tmp_path / "adj.jsonl")
    log.append(_adj("v1", note="reads as 140"))
    log.append(_adj("v2", kind=CORRECT, supersedes="v1",
                    value={"numeral": "14a", "x": 0.84, "y": 0.19},
                    note="on closer look it is 14a"))

    assert [a.adj_id for a in log.effective()] == ["v2"]
    assert [a.adj_id for a in log.all()] == ["v1", "v2"], "history must be complete"
    assert log.all()[0].note == "reads as 140"


def test_tampering_with_the_record_is_detected(tmp_path):
    """Append-only is worth little without tamper evidence: a doctored file must fail
    loudly rather than read clean. Reuses the audit chain (I5) rather than a second one."""
    path = tmp_path / "adj.jsonl"
    log = AdjudicationLog(path)
    log.append(_adj("a1"))
    log.append(_adj("a2", target={"page": 4, "numeral": "B", "x": 0.1, "y": 0.2}))
    log.verify_chain()

    lines = path.read_text().splitlines()
    rec = json.loads(lines[0])
    rec["payload"]["by"] = "somebody else"
    lines[0] = json.dumps(rec)
    path.write_text("\n".join(lines) + "\n")

    with pytest.raises(TamperError):
        log.verify_chain()


def test_deleting_an_entry_is_detected(tmp_path):
    path = tmp_path / "adj.jsonl"
    log = AdjudicationLog(path)
    for i in range(3):
        log.append(_adj(f"a{i}"))
    lines = path.read_text().splitlines()
    path.write_text("\n".join([lines[0], lines[2]]) + "\n")   # excise the middle
    with pytest.raises(TamperError):
        log.verify_chain()


def test_provenance_is_not_optional():
    with pytest.raises(ValueError, match="provenance is not optional"):
        Adjudication(adj_id="x", kind=CONFIRM, target_kind="figure-numeral",
                     target={}, by="", on="2026-07-28")
        AdjudicationLog("/dev/null").append(
            Adjudication("x", CONFIRM, "figure-numeral", {}, "", "2026-07-28"))


def test_a_correction_must_carry_the_corrected_value(tmp_path):
    log = AdjudicationLog(tmp_path / "adj.jsonl")
    with pytest.raises(ValueError, match="corrected value"):
        log.append(_adj("c1", kind=CORRECT))


def test_notes_are_never_superseded_away():
    """A note is reasoning attached to a target, not a competing claim about it, so a
    later judgment does not silence it."""
    notes = [_adj("n1", kind=NOTE, note="the leader line is ambiguous here"),
             _adj("c1", kind=CONFIRM)]
    assert {a.adj_id for a in effective(notes)} == {"n1", "c1"}


def test_legacy_migration_preserves_the_box_and_admits_its_own_limits(tmp_path):
    """The legacy file kept no history, so migration recovers only what it currently
    holds. That limit is recorded in the note rather than papered over — and the box
    dimensions come across, since a migration that silently narrows a recorded mark is
    the same class of loss, just smaller."""
    p = tmp_path / "manual_annotations.json"
    p.write_text(json.dumps([{"page": 3, "numeral": "A", "x": 0.84, "y": 0.19,
                              "w": 0.03, "h": 0.02, "note": "seen on the sheet"}]))
    got = import_legacy_sidecar(p, by="J. Smith", on="2026-07-28")
    assert len(got) == 1
    assert got[0].target["w"] == 0.03 and got[0].target["h"] == 0.02
    assert "provenance is reconstructed" in got[0].note
    assert got[0].kind == CONFIRM


def test_a_refutation_withdraws_a_located_mark(tmp_path):
    """The only way anything leaves the manifest view — and it takes a named human
    saying so on a dated record."""
    from cairn.figures_map import apply_adjudications
    log = AdjudicationLog(tmp_path / "adjudications.jsonl")
    log.append(_adj("r1", kind=REFUTE,
                    target={"page": 2, "numeral": "99", "x": 0.5, "y": 0.5},
                    note="nothing is drawn here"))
    manifest = {"pages": [{"page": 2, "numerals": [
        {"numeral": "99", "x": 0.5, "y": 0.5, "method": "first-pass"},
        {"numeral": "12", "x": 0.1, "y": 0.1, "method": "first-pass"}]}]}
    apply_adjudications(manifest, tmp_path)
    assert [n["numeral"] for n in manifest["pages"][0]["numerals"]] == ["12"]


def test_a_confirmation_carries_who_and_when_into_the_manifest(tmp_path):
    from cairn.figures_map import apply_adjudications
    log = AdjudicationLog(tmp_path / "adjudications.jsonl")
    log.append(_adj("h1", target={"page": 3, "numeral": "A", "x": 0.84, "y": 0.19},
                    note="visually confirmed"))
    manifest = {"pages": [{"page": 3, "numerals": []}]}
    apply_adjudications(manifest, tmp_path)
    n = manifest["pages"][0]["numerals"][0]
    assert (n["numeral"], n["method"], n["by"], n["on"]) == (
        "A", "human", "J. Smith", "2026-07-28")
    assert n["adjudication"] == "h1", "the mark must point back at the record that made it"
