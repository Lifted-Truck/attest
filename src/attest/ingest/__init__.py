"""Ingestion & normalization (brief §1, subsystem 1).

Corpus → cleaned canonical text → content hash → document store. The only
corpus-specific module is `edgar.py`; `document.py` and `store.py` are generic.
"""

from .document import Document, HashMismatch, content_hash, make_document, verify_document
from .store import DocumentStore

__all__ = [
    "Document",
    "DocumentStore",
    "HashMismatch",
    "content_hash",
    "make_document",
    "verify_document",
]
