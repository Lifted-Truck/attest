"""CLI mirror of the ATTEST tools (ROADMAP M4-T1).

`python -m attest list` enumerates the tools; `python -m attest call <tool> <json>`
invokes one. Same registry as the MCP server, so the two interfaces can't drift.

    python -m attest list
    python -m attest call get_span '{"doc_id":"AAPL-10K-FY2024","start":139998,"end":140030}'
    python -m attest call check_support '{"query":"How much term debt does Apple carry?"}'
"""

from __future__ import annotations

import argparse
import json
import sys

from .tools import default_registry


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="attest", description="ATTEST grounded-retrieval tools")
    p.add_argument("--store", default="corpus/store", help="document store dir")
    p.add_argument("--audit", default=None, help="audit log path (enables get_audit_log)")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list", help="enumerate the tools")
    call = sub.add_parser("call", help="invoke a tool")
    call.add_argument("tool")
    call.add_argument("args", nargs="?", default="{}", help="JSON args object")
    ns = p.parse_args(argv)

    registry = default_registry(ns.store, ns.audit)

    if ns.cmd == "list":
        for tool in registry.values():
            flag = "" if tool.read_only else " (writes log)"
            print(f"{tool.name}{flag}\t{tool.description}")
        return 0

    if ns.tool not in registry:
        print(f"unknown tool: {ns.tool!r}; try `attest list`", file=sys.stderr)
        return 2
    result = registry[ns.tool].handler(json.loads(ns.args))
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
