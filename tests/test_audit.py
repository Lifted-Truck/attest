"""Standing tests for the append-only audit log (ROADMAP M3-T1; I5).

Append-only + tamper-evident: the chain verifies after honest appends, and any
edit / reorder / deletion is detected (tampering fails the build).
"""

import json

import pytest

from attest.audit import GENESIS, AuditLog, TamperError, entry_hash


def test_append_builds_a_verifying_chain(tmp_path):
    log = AuditLog(tmp_path / "audit.jsonl")
    log.append({"query": "total assets?", "status": "answered"})
    log.append({"query": "CEO pay?", "status": "abstained"})
    log.verify_chain()  # does not raise
    entries = log.entries()
    assert [e.seq for e in entries] == [0, 1]
    assert entries[0].prev_hash == GENESIS
    assert entries[1].prev_hash == entries[0].entry_hash  # chained


def test_payload_is_preserved_and_replayable(tmp_path):
    log = AuditLog(tmp_path / "audit.jsonl")
    payload = {"query": "term debt?", "supporting": ["sp@1-2", "sp@3-4"], "confidence": 0.9}
    log.append(payload)
    assert log.entries()[0].payload == payload  # replay reconstructs the interaction


def test_tampered_payload_is_detected(tmp_path):
    path = tmp_path / "audit.jsonl"
    log = AuditLog(path)
    log.append({"answer": "$364,980M"})
    log.append({"answer": "$176,392M"})
    # Forge the first entry's payload, leaving its stored hash intact.
    rows = [json.loads(ln) for ln in path.read_text().splitlines()]
    rows[0]["payload"] = {"answer": "$999,999M"}
    path.write_text("\n".join(json.dumps(r) for r in rows) + "\n")
    with pytest.raises(TamperError):
        log.verify_chain()


def test_reordering_is_detected(tmp_path):
    path = tmp_path / "audit.jsonl"
    log = AuditLog(path)
    log.append({"n": 1})
    log.append({"n": 2})
    rows = path.read_text().splitlines()
    path.write_text("\n".join(reversed(rows)) + "\n")
    with pytest.raises(TamperError):
        log.verify_chain()


def test_deletion_is_detected(tmp_path):
    path = tmp_path / "audit.jsonl"
    log = AuditLog(path)
    log.append({"n": 1})
    log.append({"n": 2})
    log.append({"n": 3})
    rows = path.read_text().splitlines()
    path.write_text(rows[0] + "\n" + rows[2] + "\n")  # drop the middle entry
    with pytest.raises(TamperError):
        log.verify_chain()


def test_append_only_api_has_no_mutators():
    assert not hasattr(AuditLog, "update")
    assert not hasattr(AuditLog, "delete")


def test_entry_hash_is_deterministic():
    a = entry_hash(0, GENESIS, {"x": 1, "y": 2})
    b = entry_hash(0, GENESIS, {"y": 2, "x": 1})  # key order independent
    assert a == b
