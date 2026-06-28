"""Generic file → document-store ingestion (corpus-agnostic).

Loads plain-text sources into a `DocumentStore`: read → minimal,
content-preserving normalization → content-hash at ingest (I3) → write. This is
the corpus-agnostic counterpart to `edgar.py` (which stays the *only*
corpus-specific ingester). Richer formats — HTML, PDF, patent XML — need their
own adapter (e.g. the patent domain pack, PE-1), not this generic loader.

The deterministic spine is unchanged: `make_document` hashes the canonical text,
`DocumentStore.write` persists it; retrieval / spans / tools read it like any
other doc. Point `ATTEST_STORE` at the target store to use it.
"""

from __future__ import annotations

import re
from pathlib import Path

from .document import Document, make_document
from .store import DocumentStore

# Plain-text only on purpose — see module docstring for why HTML/PDF/XML are out.
TEXT_SUFFIXES = {".txt", ".md", ".markdown", ".text"}


def normalize_text(raw: str) -> str:
    """Content-preserving: strip a UTF-8 BOM and normalize newlines to ``\\n``."""
    return raw.lstrip("﻿").replace("\r\n", "\n").replace("\r", "\n")


def doc_id_for(path: Path) -> str:
    """Stable doc id from a filename stem (whitespace → ``_``; path separators out)."""
    return re.sub(r"\s+", "_", path.stem).replace("/", "-")


def ingest_file(path: Path, store: DocumentStore, *, kind: str | None = None) -> Document:
    """Ingest one plain-text file into ``store``. Raises on an unsupported type."""
    suffix = path.suffix.lower()
    if suffix not in TEXT_SUFFIXES:
        raise ValueError(
            f"{path.name}: unsupported type '{suffix}'. This loader is plain-text only "
            f"({', '.join(sorted(TEXT_SUFFIXES))}); HTML/PDF/patent-XML need a corpus "
            f"adapter (PE-1)."
        )
    text = normalize_text(path.read_text(encoding="utf-8"))
    meta = {"source": path.name}
    if kind:
        meta["kind"] = kind
    doc = make_document(doc_id_for(path), text, meta)
    store.write(doc)
    return doc


def collect_paths(inputs: list[str]) -> list[Path]:
    """Expand files + directories (non-recursive, text files only) into a sorted list."""
    out: list[Path] = []
    for raw in inputs:
        p = Path(raw)
        if p.is_dir():
            out.extend(sorted(
                c for c in p.iterdir() if c.is_file() and c.suffix.lower() in TEXT_SUFFIXES
            ))
        elif p.is_file():
            out.append(p)
        else:
            raise FileNotFoundError(raw)
    return out


def ingest_paths(inputs: list[str], store_dir: str | Path, *, kind: str | None = None
                 ) -> list[Document]:
    """Ingest every plain-text file under ``inputs`` into a store at ``store_dir``."""
    store = DocumentStore(store_dir)
    return [ingest_file(p, store, kind=kind) for p in collect_paths(inputs)]
