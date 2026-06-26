"""Append-only audit log (ROADMAP M3-T1; invariants I4, I5).

The audit log is the **only writable surface** in the system (I4): every
interaction — query, retrieval set, answer + citations, verify/support result,
abstention, confidence — is appended immutably and replayably (I5).

Immutability is made *tamper-evident* with a hash chain: each entry carries the
hash of the previous one, and `entry_hash` covers `(seq, prev_hash, payload)`.
Editing, reordering, or deleting any entry breaks the chain, which
`verify_chain()` detects — so a doctored log fails the build, it doesn't lie
quietly. The API only appends; there is no update or delete.

The payload is opaque JSON (the M4 tool layer defines its schema); this module
owns only the append-only + tamper-evidence guarantees. Deterministic: the chain
is a pure function of the payloads (timestamps, when supplied, live inside the
payload — this module reads no clock).
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

GENESIS = "0" * 64


class TamperError(Exception):
    """The audit log's hash chain does not verify — it has been altered (I5)."""


def _canonical(seq: int, prev_hash: str, payload: dict) -> str:
    return json.dumps(
        {"seq": seq, "prev_hash": prev_hash, "payload": payload},
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )


def entry_hash(seq: int, prev_hash: str, payload: dict) -> str:
    return hashlib.sha256(_canonical(seq, prev_hash, payload).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class AuditEntry:
    seq: int
    prev_hash: str
    payload: dict
    entry_hash: str


class AuditLog:
    """A tamper-evident, append-only JSONL log. The only writable surface (I4)."""

    def __init__(self, path: Path | str):
        self.path = Path(path)

    def _raw(self) -> list[dict]:
        if not self.path.exists():
            return []
        lines = self.path.read_text(encoding="utf-8").splitlines()
        return [json.loads(ln) for ln in lines if ln.strip()]

    def append(self, payload: dict) -> AuditEntry:
        raw = self._raw()
        seq = len(raw)
        prev = raw[-1]["entry_hash"] if raw else GENESIS
        h = entry_hash(seq, prev, payload)
        rec = {"seq": seq, "prev_hash": prev, "payload": payload, "entry_hash": h}
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        return AuditEntry(seq, prev, payload, h)

    def entries(self) -> list[AuditEntry]:
        return [
            AuditEntry(r["seq"], r["prev_hash"], r["payload"], r["entry_hash"]) for r in self._raw()
        ]

    def verify_chain(self) -> None:
        """Recompute the whole chain; raise TamperError on any drift (I5)."""
        prev = GENESIS
        for i, r in enumerate(self._raw()):
            if r["seq"] != i:
                raise TamperError(f"entry {i}: seq is {r['seq']} (reordered or deleted)")
            if r["prev_hash"] != prev:
                raise TamperError(f"entry {i}: prev_hash broken (chain spliced)")
            recomputed = entry_hash(r["seq"], r["prev_hash"], r["payload"])
            if recomputed != r["entry_hash"]:
                raise TamperError(f"entry {i}: payload altered (hash mismatch)")
            prev = r["entry_hash"]
