# Using ATTEST in Claude Code (Desktop)

Desktop is the primary working surface for engagements. ATTEST runs there as a set
of **deterministic MCP tools** the agent calls — it makes **no model calls of its
own** (the agent is the only model). This is the day-to-day workflow.

## 1. Connect the ATTEST tools

The repo ships a project-scoped [`.mcp.json`](../.mcp.json) that registers the
ATTEST server (`python -m attest.mcp_server`). "Open the project" just means
**Claude Code Desktop's working folder is this repo** — there's no separate action.
Desktop reads `.mcp.json` **when a session starts** and **approve the `attest`
server** if prompted; so if you ever edit `.mcp.json` (or the tools don't appear),
**start a fresh session in the repo** to re-read it. A different engagement is its
own folder with its own `.mcp.json` + corpus — that's when "open the project"
(point Desktop at that folder) is a real step.

Quick check that it's live: ask *"use check_support to find Apple's total assets"* —
a `supported` result with a span id means the tools are connected.

Prerequisites (one time):

```
pip install -e ".[dev,mcp]"          # the package + the MCP server dep
python scripts/ingest_corpus.py      # builds corpus/store (content-hashed, I3)
```

Verify the tools are live — ask Desktop *"list your attest tools"*; you should see
**7**: `search_corpus`, `get_span`, `get_document`, `check_support`, `check_claim`,
`verify`, `get_audit_log`. The server logs every interaction to
`audit_log/agent.jsonl` (I5) — that log is the bridge to the review GUI below.

### Iterating on the tools — when a refresh is needed (and when it isn't)

The MCP server is a **long-lived subprocess** that loads the tool code once at
startup, so changes to the **tool code or schema** (`src/attest/tools.py`,
`mcp_server.py`, `session.py`, `verify.py`, etc.) **don't take effect until the
server is refreshed**. To refresh, cheapest first:

1. **`/mcp` panel → reconnect the `attest` server** — no app restart, no new thread.
2. **Quit and reopen Desktop** — the guaranteed reset (also required after editing
   `.mcp.json` itself, which is read only at session startup).

A **new conversation/thread alone is NOT reliable** — stdio servers persist across
conversations in one app instance. **Sub-agents don't help either**: they share the
parent's server connection (same old code) and can't invoke slash commands.

**Most edits need no refresh at all** — `CLAUDE.md`, the `/ground` command, the
`evidence_view` renderer, and anything under `scripts/` are read fresh every time.
Only the live MCP tool surface caches. (Dev tip: run `python -m attest.mcp_server`
in a terminal to watch its logs while iterating.)

## 2. Auth — no API key needed here

In Desktop you're already signed in, and the ATTEST tools are deterministic, so the
loop just works. **The `ANTHROPIC_API_KEY` / `.env.local` is only for the headless
Layer-E eval** (`scripts/run_layer_e.py --live`), which spawns its own `claude -p`
subprocesses — see [`layer_e_baseline.md`](layer_e_baseline.md). Nothing in normal
Desktop use touches that key.

## 3. The loop, one command

Ask grounded questions directly, or use the slash command:

```
/ground What were Apple's total assets as of September 28, 2024?
```

`/ground` ([.claude/commands/ground.md](../.claude/commands/ground.md)) runs the
full loop — locate → read → bind → `verify` → **present or abstain/correct (D16)** —
then rebuilds the evidence view from the session's audit log.

## 4. Review the citations

```
python scripts/build_evidence_view.py --from-audit   # → evidence_view.html
```

This reconstructs **every presented answer from this session** (each `verify`-ok
record) into the two-pane view: the canonical document on the left, your answers on
the right, each cited span highlighted in place. Click a card to light only that
answer's evidence. Reading the highlighted span — does it actually support the
claim? — is the un-gated, human step (entailment).

## 5. Per engagement

Each corpus (e.g. a patent matter) gets its **own** ingested store and a `.mcp.json`
whose `ATTEST_STORE` / `ATTEST_AUDIT` point at it. The engine, tools, loop, and
this workflow are identical — only the corpus changes (D10). For patents, the
cardinal rule tightens: **locate & evidence, never adjudicate** (no conclusions on
novelty / validity / infringement / claim construction).
