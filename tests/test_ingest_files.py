"""Standing tests for the generic plain-text ingester (RT-2 CLI half).

Corpus-agnostic loader: read → content-preserving normalize → hash (I3) → write.
No EDGAR, no network; everything runs against tmp files.
"""

import pytest

from attest.ingest import DocumentStore
from attest.ingest.files import (
    doc_id_for,
    ingest_file,
    ingest_paths,
    normalize_text,
)


def test_normalize_is_content_preserving():
    assert normalize_text("a\r\nb\rc") == "a\nb\nc"      # newlines unified
    assert normalize_text("﻿hi") == "hi"             # BOM stripped
    assert normalize_text("plain text") == "plain text"   # nothing else touched


def test_doc_id_from_filename(tmp_path):
    from pathlib import Path
    assert doc_id_for(Path("US 1234567 B2.txt")) == "US_1234567_B2"


def test_ingest_round_trips_and_hashes(tmp_path):
    (tmp_path / "a.txt").write_text("Claim 1. A widget comprising a sprocket.\n", encoding="utf-8")
    (tmp_path / "b.md").write_text("# Notes\n\nThe sprocket is red.\n", encoding="utf-8")
    store_dir = tmp_path / "store"

    docs = ingest_paths([str(tmp_path)], store_dir, kind="patent")
    assert {d.doc_id for d in docs} == {"a", "b"}

    store = DocumentStore(store_dir)
    assert set(store.list_docs()) == {"a", "b"}
    a = store.load("a")
    assert "sprocket" in a.canonical_text and a.metadata["kind"] == "patent"
    assert a.content_hash  # hashed at ingest (I3)


def test_ingest_is_deterministic(tmp_path):
    f = tmp_path / "p.txt"
    f.write_text("same bytes in → same hash out", encoding="utf-8")
    h1 = ingest_file(f, DocumentStore(tmp_path / "s1"))
    h2 = ingest_file(f, DocumentStore(tmp_path / "s2"))
    assert h1.content_hash == h2.content_hash


def test_unsupported_type_is_rejected(tmp_path):
    pdf = tmp_path / "spec.pdf"
    pdf.write_bytes(b"%PDF-1.7 ...")
    with pytest.raises(ValueError, match="adapter"):
        ingest_file(pdf, DocumentStore(tmp_path / "store"))


def test_missing_path_errors(tmp_path):
    with pytest.raises(FileNotFoundError):
        ingest_paths([str(tmp_path / "nope.txt")], tmp_path / "store")
