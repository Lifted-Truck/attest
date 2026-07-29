"""The ingested document and its content hash — the I3 anchor.

Corpus-agnostic on purpose: a `Document` is canonical text plus the sha256 of
that text. Spans (M1-T2) reference immutable char offsets into `canonical_text`;
any drift between the stored text and its hash is a hard failure (I3). Nothing
here knows about EDGAR — the corpus-specific code lives only in `edgar.py`.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field


class HashMismatch(Exception):
    """Raised when a document's canonical text no longer matches its stored hash (I3)."""


def content_hash(text: str) -> str:
    """The single hashing convention for the whole system: sha256 of UTF-8 text."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class Document:
    doc_id: str
    canonical_text: str
    content_hash: str  # sha256 of canonical_text at ingest (I3)
    metadata: dict = field(default_factory=dict)

    def __len__(self) -> int:
        return len(self.canonical_text)


def make_document(doc_id: str, canonical_text: str, metadata: dict | None = None) -> Document:
    """Build a Document, hashing the canonical text at ingest (I3)."""
    return Document(doc_id, canonical_text, content_hash(canonical_text), metadata or {})


def verify_document(doc: Document) -> None:
    """Re-hash the canonical text and confirm it matches the stored hash (I3).

    Raises HashMismatch on any drift. This is the standing check every read path
    runs so a tampered or corrupted corpus fails loudly instead of being trusted.
    """
    recomputed = content_hash(doc.canonical_text)
    if recomputed != doc.content_hash:
        raise HashMismatch(
            f"{doc.doc_id}: stored {doc.content_hash[:12]}… != recomputed {recomputed[:12]}…"
        )
