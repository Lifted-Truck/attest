"""Standing tests for the loopback-only review server (RT-10b, D49).

The listener exists under protest: the MCP hardening brief says a local server's ABSENCE
of a listener is the win. The cause that justified it is determinism — a JavaScript
retrieval implementation would be a second oracle that can drift from the Python one — so
the guards that pay for it are tested, not assumed.
"""

from __future__ import annotations

import pytest

from cairn.serve import NotLoopback, origin_allowed, require_loopback

pytestmark = pytest.mark.layer0


def test_non_loopback_binds_are_refused_not_warned():
    """A review server reachable from the network is a different product with a different
    threat model. Refusing beats warning: a warning gets scrolled past."""
    for host in ("0.0.0.0", "192.168.1.10", "10.0.0.1", "example.com", "::"):
        with pytest.raises(NotLoopback):
            require_loopback(host)


def test_loopback_binds_are_allowed():
    for host in ("127.0.0.1", "::1", "localhost", "127.0.0.53"):
        require_loopback(host)


def test_cross_origin_requests_are_refused():
    """A browser will happily let any page POST to 127.0.0.1, and DNS rebinding makes
    that reachable from a hostile site — the MCP Inspector RCE class. Origin is the only
    signal distinguishing our own console from someone else's page."""
    assert not origin_allowed("http://evil.example", 8765)
    assert not origin_allowed("https://127.0.0.1.nip.io", 8765)
    assert not origin_allowed("file://", 8765)
    # a different port is a different origin
    assert not origin_allowed("http://127.0.0.1:9999", 8765)


def test_same_origin_and_non_browser_clients_are_allowed():
    assert origin_allowed("http://127.0.0.1:8765", 8765)
    assert origin_allowed("http://localhost:8765", 8765)
    assert origin_allowed(None, 8765), "curl and tests send no Origin"


def test_the_server_exposes_no_tool_the_mcp_surface_lacks():
    """The handlers come from the same registry, so schema validation, path containment
    (D35) and bounded inputs (D41) apply unchanged — there is no second code path to keep
    in step, and no endpoint that exists only here."""
    import inspect

    from cairn import serve as serve_mod
    src = inspect.getsource(serve_mod)
    assert "tools.get(name)" in src, "handlers must come from the passed registry"
    assert "default_registry" not in src, "the module must not build its own tool set"
