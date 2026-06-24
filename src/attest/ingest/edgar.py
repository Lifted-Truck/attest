"""EDGAR corpus adapter — THE ONLY corpus-specific module (brief §8).

Everything that knows the corpus is "SEC EDGAR filings" lives here: the filing
registry, the fetch, and the HTML→canonical-text normalization. Swapping to a
different corpus (clinical guidelines, municipal code, …) means writing a sibling
adapter and changing nothing else. `document.py` / `store.py` stay untouched.

Normalization is deterministic (I6): same raw HTML → same canonical text → same
hash. The conversion is intentionally simple and content-preserving — it strips
markup and normalizes whitespace/Unicode spaces, but never alters the visible
words or figures that spans and golden quotes resolve against.
"""

from __future__ import annotations

import html as html_mod
import os
import re
import urllib.request
from html.parser import HTMLParser
from pathlib import Path

from .document import Document, make_document

SEC_USER_AGENT = os.environ.get("SEC_USER_AGENT", "ATTEST research contact@example.com")

# Filing registry. Each entry is fully self-describing provenance for one document.
FILINGS: dict[str, dict] = {
    "AAPL-10K-FY2024": {
        "doc_id": "AAPL-10K-FY2024",
        "company": "Apple Inc.",
        "ticker": "AAPL",
        "cik": "0000320193",
        "form": "10-K",
        "period_of_report": "2024-09-28",
        "accession": "0000320193-24-000123",
        "primary_document": "aapl-20240928.htm",
        "index_url": "https://www.sec.gov/Archives/edgar/data/320193/000032019324000123/0000320193-24-000123-index.htm",
        "primary_url": "https://www.sec.gov/Archives/edgar/data/320193/000032019324000123/aapl-20240928.htm",
    },
}


class _TextExtractor(HTMLParser):
    """Minimal, dependency-free HTML → text. Preserves visible words verbatim."""

    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self._skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self._skip += 1
        if tag in ("p", "div", "tr", "br", "table", "h1", "h2", "h3", "li"):
            self.parts.append("\n")
        if tag == "td":
            self.parts.append(" ")

    def handle_endtag(self, tag):
        if tag in ("script", "style") and self._skip:
            self._skip -= 1
        if tag in ("p", "div", "tr", "table"):
            self.parts.append("\n")

    def handle_data(self, data):
        if not self._skip:
            self.parts.append(data)


def normalize(raw_html: str) -> str:
    """Deterministic HTML → canonical text (I6). Content-preserving."""
    p = _TextExtractor()
    p.feed(raw_html)
    txt = html_mod.unescape("".join(p.parts))
    # Normalize Unicode spaces (NBSP, thin, narrow-NBSP) to ASCII — content-preserving.
    txt = txt.translate({0xA0: " ", 0x2009: " ", 0x202F: " ", 0x2007: " "})
    txt = re.sub(r"[ \t]+", " ", txt)
    txt = re.sub(r"\n[ \t]+", "\n", txt)
    txt = re.sub(r"\n{3,}", "\n\n", txt)
    return txt


def fetch_html(doc_id: str, cache_dir: Path | str) -> str:
    """Fetch the filing's primary document, caching the raw HTML for offline re-runs."""
    filing = FILINGS[doc_id]
    cache_dir = Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache = cache_dir / filing["primary_document"]
    if cache.exists():
        return cache.read_text(encoding="utf-8")
    req = urllib.request.Request(filing["primary_url"], headers={"User-Agent": SEC_USER_AGENT})
    with urllib.request.urlopen(req, timeout=60) as resp:  # noqa: S310 (trusted SEC host)
        raw = resp.read().decode("utf-8")
    cache.write_text(raw, encoding="utf-8")
    return raw


def ingest(doc_id: str, cache_dir: Path | str) -> Document:
    """Fetch → normalize → content-hash a filing into a Document (I3)."""
    raw = fetch_html(doc_id, cache_dir)
    canonical = normalize(raw)
    metadata = {k: v for k, v in FILINGS[doc_id].items() if k != "doc_id"}
    return make_document(doc_id, canonical, metadata)
