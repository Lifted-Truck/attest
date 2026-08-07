"""Standing test for which MCP protocol era we actually speak (D57).

The 2026-07-28 revision removed the `initialize` handshake: version, identity and
capabilities now ride as per-request `_meta`, and a modern server MUST implement
`server/discover`. The spec's own compatibility matrix is blunt about the consequence —
**legacy server + modern client = fails**, and a legacy client has no fall-forward.

So the era is a compatibility fact, not a detail, and it must not change silently under a
dependency bump. This test pins what we claim and fails when the SDK moves.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.layer0

# What Cairn's MCP adapter is written against today. Changing this is an era migration
# with client-visible consequences, so it changes with a decision — never as a side
# effect of upgrading a package.
DECLARED_ERA = "legacy"
DECLARED_LATEST = "2025-11-25"


def test_the_sdk_era_matches_what_we_declare():
    """If this fails, the SDK moved era. That is not a lint failure to silence: a modern
    server must implement `server/discover` and drop the handshake, and `mcp_server.py`
    is written against the handshake API."""
    mcp_types = pytest.importorskip("mcp.types", reason="the mcp extra is optional")

    latest = getattr(mcp_types, "LATEST_PROTOCOL_VERSION", None)
    assert latest == DECLARED_LATEST, (
        f"SDK protocol version moved to {latest!r}; we declare {DECLARED_LATEST!r}. "
        f"If this is the modern era (2026-07-28+), mcp_server.py needs server/discover "
        f"and per-request _meta — see D57.")

    has_handshake = hasattr(mcp_types, "InitializeRequest")
    has_discover = any("discover" in n.lower() for n in dir(mcp_types))
    era = "modern" if (has_discover and not has_handshake) else "legacy"
    assert era == DECLARED_ERA, f"SDK era is now {era!r}, we declare {DECLARED_ERA!r}"


def test_the_engine_holds_no_session_state():
    """Why the era change costs us little: Cairn's tools are pure functions over a frozen
    corpus, so statelessness is what I6 already required. The read tools hold no
    reference to a log and accumulate nothing between calls — a second registry built on
    the same store answers identically."""
    import tempfile
    from pathlib import Path

    from cairn.ingest.document import make_document
    from cairn.ingest.store import DocumentStore
    from cairn.tools import default_registry
    d = Path(tempfile.mkdtemp())
    DocumentStore(d / "store").write(
        make_document("D1", "Total assets $ 364,980 as of September 28, 2024."))

    a = default_registry(d / "store")["search_corpus"].handler({"query": "total assets"})
    b = default_registry(d / "store")["search_corpus"].handler({"query": "total assets"})
    assert a == b, "a fresh registry must answer identically — no carried state"

    reg = default_registry(d / "store")
    first = reg["search_corpus"].handler({"query": "total assets"})
    reg["search_corpus"].handler({"query": "something else entirely"})
    assert reg["search_corpus"].handler({"query": "total assets"}) == first, (
        "an intervening call must not change a later answer")
