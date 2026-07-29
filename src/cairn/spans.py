"""Span store — char-offset spans into the canonical document (ROADMAP M1-T2).

A Span is an immutable `(doc_id, char_start, char_end)` window into a Document's
canonical text. `get_span` returns the exact slice and re-verifies the document's
content hash first (I3) — any drift is a hard failure. `resolve_quote` enforces
the **resolution invariant** (D7): a golden quote must resolve to exactly one
location in the canonical text, or it is a build-breaking error.

Chunking is deterministic (I6): same canonical text → same spans, same offsets.
Corpus-agnostic — knows nothing about EDGAR.
"""

from __future__ import annotations

from dataclasses import dataclass

from .ingest.document import Document, verify_document


class SpanError(Exception):
    """Invalid span request (offsets out of range, unknown doc)."""


class ResolutionError(Exception):
    """A quote did not resolve to exactly one location (resolution invariant, D7)."""


@dataclass(frozen=True)
class Span:
    span_id: str
    doc_id: str
    char_start: int
    char_end: int
    text: str


def chunk_document(doc: Document) -> list[Span]:
    """Split canonical text into line-level spans with exact char offsets.

    Deterministic. Blank / non-alphanumeric lines are skipped; each span's
    offsets are the precise bounds of the stripped line content, so
    `canonical_text[start:end] == span.text` exactly.
    """
    text = doc.canonical_text
    spans: list[Span] = []
    offset = 0
    for line in text.splitlines(keepends=True):
        stripped = line.strip()
        if stripped and any(c.isalnum() for c in stripped):
            start = offset + (len(line) - len(line.lstrip()))
            end = start + len(stripped)
            sid = f"{doc.doc_id}@{start}-{end}"
            spans.append(Span(sid, doc.doc_id, start, end, text[start:end]))
        offset += len(line)
    return spans


class SpanStore:
    """Holds documents + their spans; the read side of the evidence layer."""

    def __init__(self, docs: list[Document]):
        self._docs: dict[str, Document] = {d.doc_id: d for d in docs}
        self._spans: dict[str, list[Span]] = {d.doc_id: chunk_document(d) for d in docs}

    @classmethod
    def from_store(cls, doc_store, doc_ids: list[str] | None = None) -> SpanStore:
        ids = doc_ids if doc_ids is not None else doc_store.list_docs()
        return cls([doc_store.load(doc_id) for doc_id in ids])

    def _doc(self, doc_id: str) -> Document:
        if doc_id not in self._docs:
            raise SpanError(f"unknown doc_id: {doc_id!r}")
        return self._docs[doc_id]

    def spans(self, doc_id: str) -> list[Span]:
        self._doc(doc_id)
        return self._spans[doc_id]

    def get_document(self, doc_id: str) -> str:
        """Full canonical text, hash-verified (I3).

        The agent may read freely (D11) — grounding constrains *output* (every
        asserted claim binds to a verified span), not *input*. Broad reading is
        how the agent gets the context (section, units caption, temporal scope)
        that makes its citations correct.
        """
        doc = self._doc(doc_id)
        verify_document(doc)
        return doc.canonical_text

    def get_span(self, doc_id: str, start: int, end: int) -> str:
        """Return canonical_text[start:end], re-verifying the doc hash first (I3)."""
        doc = self._doc(doc_id)
        verify_document(doc)  # I3 — refuse to serve text from a drifted document
        n = len(doc.canonical_text)
        if not (0 <= start <= end <= n):
            raise SpanError(f"span ({start}, {end}) out of range for {doc_id} (len {n})")
        return doc.canonical_text[start:end]

    def resolve_quote(self, doc_id: str, quote: str) -> tuple[int, int]:
        """Resolve a verbatim quote to its unique (start, end). Resolution invariant (D7)."""
        doc = self._doc(doc_id)
        verify_document(doc)
        text = doc.canonical_text
        count = text.count(quote)
        if count == 0:
            raise ResolutionError(f"{doc_id}: quote not found: {quote!r}")
        if count > 1:
            raise ResolutionError(f"{doc_id}: quote resolves {count}× (need exactly 1): {quote!r}")
        start = text.find(quote)
        return start, start + len(quote)

    def span_containing(self, doc_id: str, start: int) -> Span | None:
        """The chunk span whose range contains the offset (for quote → span_id binding)."""
        for sp in self._spans[doc_id]:
            if sp.char_start <= start < sp.char_end:
                return sp
        return None
