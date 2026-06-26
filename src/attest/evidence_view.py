"""render_evidence_view — parallel evidence GUI (ROADMAP M2-T7 / D8).

A self-contained HTML page: the **full canonical document** on the left with every
cited range highlighted *in place*, and the interactions on the right. Click a
figure in an answer (or a closest-span in an abstention) and the document pane
scrolls to its highlight. Read-only (I4), deterministic, no server.

It renders the *normalized canonical text* ATTEST hashes and cites (D8) — so what
you review is exactly what the system verifies. Your job is the un-gated one:
does the highlighted span actually support the claim (entailment)?
"""

from __future__ import annotations

import html
from dataclasses import dataclass, field

from .frame import QuestionFrame, check_coverage
from .retrieval import Hit
from .spans import SpanStore
from .verify import Answer, VerifyResult


@dataclass
class Interaction:
    question: str
    kind: str  # "answer" | "abstain" | "reject" | "partial"
    answer: Answer | None = None
    verify: VerifyResult | None = None
    reason: str = ""
    closest: list[Hit] = field(default_factory=list)
    note: str = ""
    trace: str = ""
    frame: QuestionFrame | None = None


_CSS = """
:root { --bg:#0f1115; --panel:#171a21; --ink:#e6e9ef; --muted:#8b93a3;
  --line:#262b36; --mark:#3b2f12; --markb:#e0a32e; --ok:#3fb950; --bad:#f85149;
  --chip:#1f6feb22; --chipb:#388bfd; }
* { box-sizing:border-box; }
body { margin:0; background:var(--bg); color:var(--ink);
  font:15px/1.55 ui-sans-serif,system-ui,-apple-system,Segoe UI,Roboto,sans-serif; }
header { padding:16px 24px; border-bottom:1px solid var(--line); }
header h1 { margin:0 0 4px; font-size:18px; }
header p { margin:0; color:var(--muted); font-size:13px; }
header a { color:var(--chipb); }
.layout { display:grid; grid-template-columns:1fr 1fr; gap:0; }
@media (max-width:860px){ .layout{ grid-template-columns:1fr; }
  .doc{ position:static!important; height:60vh!important; } }
.doc { position:sticky; top:0; height:100vh; overflow:auto; border-right:1px solid var(--line);
  padding:14px 18px; background:#0c0e12; }
.doc h3, .cards-h { font-size:11px; text-transform:uppercase; letter-spacing:.06em;
  color:var(--muted); margin:0 0 8px; }
.docbody { white-space:pre-wrap; word-break:break-word; font-size:12px; line-height:1.5;
  font-family:ui-monospace,Menlo,monospace; color:#c6ccd8; margin:0; }
.cards { overflow:auto; }
.card { border-bottom:1px solid var(--line); padding:18px 24px; }
.q { font-weight:600; margin:0 0 2px; }
.badge { display:inline-block; font-size:11px; font-weight:700; letter-spacing:.04em;
  padding:2px 8px; border-radius:999px; text-transform:uppercase; margin-bottom:10px; }
.badge.answer { background:#11331c; color:var(--ok); }
.badge.abstain, .badge.reject, .badge.partial { background:#3a1d1d; color:var(--bad); }
.answer-text { background:var(--panel); border:1px solid var(--line); border-radius:8px;
  padding:12px 14px; }
.reason { color:var(--muted); margin:0 0 8px; }
mark { background:var(--mark); color:var(--markb); border-radius:3px; padding:0 1px;
  font-weight:600; scroll-margin-top:14px; }
mark.flash { background:#1d2740; color:#cfe0ff; outline:1px solid var(--chipb); }
.chip { background:var(--chip); border:1px solid var(--chipb); color:var(--ink);
  border-radius:4px; padding:0 4px; cursor:pointer; font-weight:600; }
.chip.derived { background:#2a1f3a; border-color:#a371f7; }
.closest { font-family:ui-monospace,Menlo,monospace; font-size:12px; margin:6px 0 0; }
.closest a { color:var(--chipb); cursor:pointer; text-decoration:none; }
.vstatus { font-size:12px; margin-top:8px; }
.vstatus.ok{ color:var(--ok); } .vstatus.bad{ color:var(--bad); }
.cover { font-size:12px; margin:6px 0 0; display:flex; flex-wrap:wrap; gap:6px; }
.cover span { border-radius:4px; padding:0 6px; border:1px solid var(--line); }
.cov-ok { color:var(--ok); } .cov-bad { color:var(--bad); border-color:var(--bad)!important; }
.trace { color:var(--muted); font-size:12px; margin:10px 0 0;
  font-family:ui-monospace,Menlo,monospace; }
.trace b { color:var(--ink); font-weight:600; }
"""

_JS = """
function jump(id){
  const el = document.getElementById(id);
  if(!el) return;
  document.querySelectorAll('mark.flash').forEach(m=>m.classList.remove('flash'));
  el.classList.add('flash');
  el.scrollIntoView({behavior:'smooth', block:'center'});
}
document.querySelectorAll('[data-target]').forEach(c=>{
  c.addEventListener('click', ()=>jump(c.dataset.target));
});
window.addEventListener('load', ()=>{
  const first = document.querySelector('.doc mark');
  if(first){ const d=document.querySelector('.doc'); d.scrollTop = first.offsetTop - 120; }
});
"""

Range = tuple[str, int, int]  # (doc_id, char_start, char_end)


def _esc(s: str) -> str:
    return html.escape(s, quote=True)


def _gather_ranges(interactions: list[Interaction]) -> list[Range]:
    ranges: set[Range] = set()
    for inter in interactions:
        if inter.kind == "answer" and inter.answer is not None:
            for s in inter.answer.sentences:
                for a in s.atoms:
                    ranges.add((a.doc_id, a.char_start, a.char_end))
                for d in s.derived:
                    for o in d.operands:
                        ranges.add((o.doc_id, o.char_start, o.char_end))
        for h in inter.closest:
            ranges.add((h.span.doc_id, h.span.char_start, h.span.char_end))
    return sorted(ranges)


def _merge(ranges: list[Range]) -> dict[str, list[tuple[int, int, str]]]:
    """Merge overlapping ranges per doc → [(start, end, mark_id)], non-overlapping."""
    by_doc: dict[str, list[tuple[int, int]]] = {}
    for doc_id, s, e in ranges:
        by_doc.setdefault(doc_id, []).append((s, e))
    merged: dict[str, list[tuple[int, int, str]]] = {}
    for di, (doc_id, spans) in enumerate(sorted(by_doc.items())):
        out: list[tuple[int, int, str]] = []
        for s, e in sorted(spans):
            if out and s <= out[-1][1]:
                ps, pe, mid = out[-1]
                out[-1] = (ps, max(pe, e), mid)
            else:
                out.append((s, e, f"m{di}_{len(out)}"))
        merged[doc_id] = out
    return merged


def _mark_id(merged: dict[str, list[tuple[int, int, str]]], r: Range) -> str:
    doc_id, s, _e = r
    for ms, me, mid in merged.get(doc_id, []):
        if ms <= s < me:
            return mid
    return ""


def _doc_pane(store: SpanStore, doc_id: str, merged: list[tuple[int, int, str]], label: str) -> str:
    text = store.get_document(doc_id)
    out, cursor = [], 0
    for s, e, mid in merged:
        s, e = max(s, cursor), max(e, cursor)
        out.append(_esc(text[cursor:s]))
        out.append(f'<mark id="{mid}">{_esc(text[s:e])}</mark>')
        cursor = e
    out.append(_esc(text[cursor:]))
    body = "".join(out)
    return f'<aside class="doc"><h3>{_esc(label)}</h3><div class="docbody">{body}</div></aside>'


def _chip_sentence(text: str, chips: list[tuple[str, str, str]]) -> str:
    placeholders: dict[str, str] = {}
    for i, (literal, cls, target) in enumerate(chips):
        token = f"\x00{i}\x00"
        if literal in text and literal not in placeholders:
            text = text.replace(literal, token, 1)
            attr = f' data-target="{target}"' if target else ""
            placeholders[token] = f'<span class="{cls}"{attr}>{_esc(literal)}</span>'
    out = _esc(text)
    for token, chip in placeholders.items():
        out = out.replace(_esc(token), chip)
    return f"<p>{out}</p>"


def _answer_card(inter: Interaction, store: SpanStore, mid_of) -> str:
    right = []
    cited_texts = []
    for s in inter.answer.sentences:
        chips: list[tuple[str, str, str]] = []
        for a in s.atoms:
            chips.append((a.text, "chip", mid_of((a.doc_id, a.char_start, a.char_end))))
            sp = store.span_containing(a.doc_id, a.char_start)
            if sp:
                cited_texts.append(sp.text)
        for d in s.derived:
            chips.append((d.text, "chip derived", ""))
            for o in d.operands:
                chips.append((o.text, "chip", mid_of((o.doc_id, o.char_start, o.char_end))))
                sp = store.span_containing(o.doc_id, o.char_start)
                if sp:
                    cited_texts.append(sp.text)
        right.append(_chip_sentence(s.text, chips))

    ok = inter.verify.ok if inter.verify else False
    vtext = "✓ verify: every figure resolves to a cited span" if ok else \
        f"✗ verify: unbound — {', '.join(inter.verify.unbound()) if inter.verify else '?'}"
    parts = [f'<div class="answer-text">{" ".join(right)}</div>',
             f'<div class="vstatus {"ok" if ok else "bad"}">{vtext}</div>']
    if inter.frame is not None:
        cov = check_coverage(inter.frame, cited_texts)
        bits = [f'<span class="cov-ok">{_esc(c.role)} ✓ {_esc(c.text)}</span>' for c in cov.covered]
        bits += [
            f'<span class="cov-bad">{_esc(c.role)} ✗ {_esc(c.text)}</span>' for c in cov.missing
        ]
        head = "✓ question coverage" if cov.complete else "✗ question coverage — incomplete"
        parts.append(f'<div class="vstatus {"ok" if cov.complete else "bad"}">{head}</div>')
        parts.append(f'<p class="cover">{" · ".join(bits)}</p>')
    return "".join(parts)


def _abstain_card(inter: Interaction, mid_of) -> str:
    parts = [f'<p class="reason">{_esc(inter.reason)}</p>']
    if inter.note:
        parts.append(f"<p>{_esc(inter.note)}</p>")
    for h in inter.closest:
        mid = mid_of((h.span.doc_id, h.span.char_start, h.span.char_end))
        link = f'<a data-target="{mid}">{_esc(h.span.text)}</a>' if mid else _esc(h.span.text)
        score = f'<span style="color:#8b93a3">(score {h.score:.0f})</span>'
        parts.append(f'<p class="closest">▸ {link} {score}</p>')
    return "".join(parts)


def render_evidence_view(
    interactions: list[Interaction], store: SpanStore, *, title: str = "ATTEST — evidence view"
) -> str:
    merged = _merge(_gather_ranges(interactions))

    def mid_of(r: Range) -> str:
        return _mark_id(merged, r)

    # Document pane(s): one per doc that has any citation (else the first doc in the store).
    doc_ids = list(merged) or list(store._docs)[:1]
    panes = []
    for doc_id in doc_ids:
        m = store._docs[doc_id].metadata
        label = f"{m.get('company', doc_id)} {m.get('form', '')}".strip() + " — canonical text"
        panes.append(_doc_pane(store, doc_id, merged.get(doc_id, []), label))

    cards = []
    for inter in interactions:
        body = _answer_card(inter, store, mid_of) if (
            inter.kind == "answer" and inter.answer is not None
        ) else _abstain_card(inter, mid_of)
        trace = f'<p class="trace"><b>decision</b> · {_esc(inter.trace)}</p>' if inter.trace else ""
        cards.append(
            f'<section class="card"><p class="q">{_esc(inter.question)}</p>'
            f'<span class="badge {inter.kind}">{inter.kind}</span>{body}{trace}</section>'
        )

    return (
        "<!doctype html><html lang=en><head><meta charset=utf-8>"
        '<meta name=viewport content="width=device-width,initial-scale=1">'
        f"<title>{_esc(title)}</title><style>{_CSS}</style></head><body>"
        f"<header><h1>{_esc(title)}</h1><p>{_source_links(store)}</p>"
        "<p>Click a highlighted figure (or a closest span) to jump to it in the document. "
        "Your review: does the highlighted span actually support the claim? "
        "(entailment — not gated in v1)</p></header>"
        f'<div class="layout">{"".join(panes)}'
        f'<main class="cards">{"".join(cards)}</main></div>'
        f"<script>{_JS}</script></body></html>"
    )


def _source_links(store: SpanStore) -> str:
    parts = []
    for doc_id, doc in store._docs.items():
        m = doc.metadata
        label = f"{m.get('company', doc_id)} {m.get('form', '')}".strip()
        bits = [f"<b>{_esc(label)}</b>"]
        if m.get("primary_url"):
            url = _esc(m["primary_url"])
            bits.append(f'<a href="{url}" target="_blank" rel="noopener">SEC filing ↗</a>')
        parts.append(" · ".join(bits))
    return "Source: " + " &nbsp;|&nbsp; ".join(parts)
