"""ATTEST — grounded-retrieval tools.

Cardinal rule: ground or abstain, never invent. Every assertion is bound to a
verbatim, hash-matched source span, or it is not made.

v1 ships as deterministic tools (an MCP server + CLI) that Claude Code invokes;
ATTEST makes no model calls of its own at runtime. See ATTEST_build_brief.md.
"""

__version__ = "0.1.0"
