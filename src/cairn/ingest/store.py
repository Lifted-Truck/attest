"""On-disk document store — the persisted corpus.

Each document is a directory holding `canonical.txt` (the exact hashed text) and
`meta.json` (hash + provenance). Loading re-verifies the hash (I3), so a drifted
or tampered file fails loudly rather than being served. Corpus-agnostic.

The store is read-only to the agent in v1 (I4, enforced at the tool boundary in
M3/M4); ingestion is the only writer, and it runs offline.
"""

from __future__ import annotations

import json
from pathlib import Path

from .document import Document, verify_document

CANONICAL = "canonical.txt"
META = "meta.json"


class DocIdError(ValueError):
    """A doc_id that does not name a document inside this store's root."""


class DocumentStore:
    def __init__(self, root: Path | str):
        self.root = Path(root)

    def doc_dir(self, doc_id: str) -> Path:
        """Resolve a doc_id to its directory, refusing anything outside the root (D35).

        `self.root / doc_id` is not safe on its own, and the failure is not the obvious
        one: pathlib DISCARDS the left operand entirely when the right is absolute, so
        `Path("corpus/store") / "/etc/passwd"` is `/etc/passwd` — traversal without a
        single `..`. Canonicalize and containment-check instead of pattern-matching for
        `..`, which URL- and unicode-encoding both defeat.

        The MCP surface does not currently reach here — `SpanStore` is dict-backed and
        refuses an unknown doc_id — but that guard is INCIDENTAL, a property of one
        class's storage choice, not a boundary anyone designed. The RAG extension under
        discussion contemplates corpora too large to preload, and lazy loading is
        exactly the refactor that would quietly make this reachable from a caller-
        supplied argument. Safety by construction, not by vigilance: put the boundary
        where the path is built, so it survives the refactor that removes the accident.
        """
        if not doc_id or doc_id in (".", "..") or "\x00" in doc_id:
            raise DocIdError(f"invalid doc_id: {doc_id!r}")
        root = self.root.resolve()
        target = (root / doc_id).resolve()
        if target != root and root not in target.parents:
            raise DocIdError(
                f"doc_id {doc_id!r} resolves outside the corpus root ({target}). "
                f"The corpus is a closed set; a document is named, never addressed.")
        return target

    def write(self, doc: Document) -> Path:
        d = self.doc_dir(doc.doc_id)
        d.mkdir(parents=True, exist_ok=True)
        (d / CANONICAL).write_text(doc.canonical_text, encoding="utf-8")
        meta = {
            "doc_id": doc.doc_id,
            "content_hash": doc.content_hash,
            "char_len": len(doc.canonical_text),
            "metadata": doc.metadata,
        }
        (d / META).write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
        return d

    def load(self, doc_id: str) -> Document:
        d = self.doc_dir(doc_id)
        text = (d / CANONICAL).read_text(encoding="utf-8")
        meta = json.loads((d / META).read_text(encoding="utf-8"))
        doc = Document(doc_id, text, meta["content_hash"], meta.get("metadata", {}))
        verify_document(doc)  # I3 enforced on every read
        return doc

    def list_docs(self) -> list[str]:
        if not self.root.exists():
            return []
        return sorted(p.name for p in self.root.iterdir() if (p / META).exists())
