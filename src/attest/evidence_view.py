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
import re
from dataclasses import dataclass, field

from .frame import QuestionFrame, check_coverage
from .retrieval import Hit
from .spans import SpanStore
from .verify import Answer, VerifyResult, equation


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
.docbody { font-size:12px; line-height:1.5; font-family:ui-monospace,Menlo,monospace; margin:0; }
.docln { white-space:pre-wrap; word-break:break-word; color:#aab2c0; }
.docln.h { color:var(--ink); font-weight:700; font-size:13px; margin-top:12px; }
.docln.sub { color:#c6ccd8; font-weight:600; margin-top:4px; }
.docln.blank { height:8px; }
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
mark { border-radius:3px; padding:0 1px; scroll-margin-top:14px; }
mark.fig { background:var(--mark); color:var(--markb); font-weight:600; }  /* figure */
mark.lbl { background:#0e3a36; color:#5fe0c4; }  /* question label term */
mark.cls { background:#23262e; color:#c6ccd8; }  /* abstention closest span */
mark.flash { outline:2px solid var(--chipb); }
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
.deriv { font-family:ui-monospace,Menlo,monospace; font-size:12px; margin:6px 0 0; color:#c6ccd8; }
.deriv .ok { color:var(--ok); } .deriv .bad { color:var(--bad); }
.chip.derived { cursor:help; }
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


def _esc(s: str) -> str:
    return html.escape(s, quote=True)


# Highlight kinds (D13 substantiation made visual): the cited figure, the
# question's label/constraint terms beside it, and abstention's closest spans.
# When ranges overlap, the higher priority wins per character.
_PRIORITY = {"figure": 3, "label": 2, "closest": 1}
_KIND_CLASS = {"figure": "fig", "label": "lbl", "closest": "cls"}
Segment = tuple[int, int, str, str]  # (start, end, kind, mark_id)


def _gather(
    interactions: list[Interaction], store: SpanStore
) -> dict[str, list[tuple[int, int, str]]]:
    raw: dict[str, list[tuple[int, int, str]]] = {}

    def add(doc_id: str, s: int, e: int, kind: str) -> None:
        raw.setdefault(doc_id, []).append((s, e, kind))

    for inter in interactions:
        if inter.kind == "answer" and inter.answer is not None:
            cons = inter.frame.constraints if inter.frame else []
            for sent in inter.answer.sentences:
                atoms = list(sent.atoms) + [o for d in sent.derived for o in d.operands]
                for a in atoms:
                    add(a.doc_id, a.char_start, a.char_end, "figure")
                    sp = store.span_containing(a.doc_id, a.char_start)
                    if sp is None:
                        continue
                    low = sp.text.lower()
                    for c in cons:  # the question's label terms, beside the figure
                        i = low.find(c.text.lower())
                        if i != -1:
                            start = sp.char_start + i
                            add(sp.doc_id, start, start + len(c.text), "label")
        for h in inter.closest:
            add(h.span.doc_id, h.span.char_start, h.span.char_end, "closest")
    return raw


def _paint(ranges: list[tuple[int, int, str]]) -> list[Segment]:
    """Resolve overlapping (start, end, kind) into non-overlapping segments; the
    highest-priority kind wins each character. Adjacent same-kind runs merge."""
    points = sorted({p for s, e, _ in ranges for p in (s, e)})
    segs: list[tuple[int, int, str]] = []
    for a, b in zip(points, points[1:], strict=False):
        covering = [k for s, e, k in ranges if s <= a and e >= b]
        if not covering:
            continue
        kind = max(covering, key=lambda k: _PRIORITY[k])
        if segs and segs[-1][1] == a and segs[-1][2] == kind:
            segs[-1] = (segs[-1][0], b, kind)
        else:
            segs.append((a, b, kind))
    return [(s, e, k, f"m{i}") for i, (s, e, k) in enumerate(segs)]


def _seg_id(painted: list[Segment], pos: int) -> str:
    for s, e, _k, mid in painted:
        if s <= pos < e:
            return mid
    return ""


_FIG = re.compile(r"\d{1,3}(?:,\d{3})+")


def _classify(line: str) -> str:
    """Light display hierarchy from a flat line (no canonical change)."""
    s = line.strip()
    if not s:
        return "blank"
    letters = [c for c in s if c.isalpha()]
    if letters and s == s.upper() and len(s) <= 90:
        return "h"  # ALL-CAPS heading (e.g. CONSOLIDATED BALANCE SHEETS, ASSETS:)
    if re.match(r"(PART |Item |ITEM )", s):
        return "h"
    if s.endswith(":") and len(s) <= 60 and not _FIG.search(s):
        return "sub"  # subsection (e.g. "Current assets:")
    return "ln"


def _doc_pane(store: SpanStore, doc_id: str, painted: list[Segment], label: str) -> str:
    """Render the document line-by-line with light hierarchy; marks spliced in situ."""
    text = store.get_document(doc_id)
    marks = sorted(painted)
    lines, offset, mi = [], 0, 0
    for raw in text.split("\n"):
        line_end = offset + len(raw)
        segs, cursor = [], offset
        while mi < len(marks) and marks[mi][0] < line_end:
            s, e, kind, mid = marks[mi]
            s, e = max(s, cursor), min(e, line_end)
            segs.append(_esc(text[cursor:s]))
            segs.append(f'<mark class="{_KIND_CLASS[kind]}" id="{mid}">{_esc(text[s:e])}</mark>')
            cursor = e
            mi += 1
        segs.append(_esc(text[cursor:line_end]))
        cls = _classify(raw)
        content = "".join(segs)
        lines.append(f'<div class="docln {cls}">{content}</div>' if cls != "blank"
                     else '<div class="docln blank"></div>')
        offset = line_end + 1  # account for the stripped "\n"
    return (
        f'<aside class="doc"><h3>{_esc(label)}</h3>'
        f'<div class="docbody">{"".join(lines)}</div></aside>'
    )


def _chip_sentence(text: str, chips: list[tuple[str, str, str, str]]) -> str:
    placeholders: dict[str, str] = {}
    for i, (literal, cls, target, title) in enumerate(chips):
        token = f"\x00{i}\x00"
        if literal in text and literal not in placeholders:
            text = text.replace(literal, token, 1)
            attr = f' data-target="{target}"' if target else ""
            tip = f' title="{_esc(title)}"' if title else ""
            placeholders[token] = f'<span class="{cls}"{attr}{tip}>{_esc(literal)}</span>'
    out = _esc(text)
    for token, chip in placeholders.items():
        out = out.replace(_esc(token), chip)
    return f"<p>{out}</p>"


def _answer_card(inter: Interaction, store: SpanStore, seg_id) -> str:
    right = []
    cited_texts = []
    derivations = []  # (equation, ok) for the decision section
    for si, s in enumerate(inter.answer.sentences):
        oks = inter.verify.sentences[si].derived_ok if inter.verify else []
        chips: list[tuple[str, str, str, str]] = []
        for a in s.atoms:
            chips.append((a.text, "chip", seg_id(a.doc_id, a.char_start), ""))
            sp = store.span_containing(a.doc_id, a.char_start)
            if sp:
                cited_texts.append(sp.text)
        for di, d in enumerate(s.derived):
            eq = equation(d)
            chips.append((d.text, "chip derived", "", eq))  # eq shows on hover
            derivations.append((eq, oks[di] if di < len(oks) else False))
            for o in d.operands:
                chips.append((o.text, "chip", seg_id(o.doc_id, o.char_start), ""))
                sp = store.span_containing(o.doc_id, o.char_start)
                if sp:
                    cited_texts.append(sp.text)
        right.append(_chip_sentence(s.text, chips))

    ok = inter.verify.ok if inter.verify else False
    vtext = "✓ verify: every figure resolves to a cited span" if ok else \
        f"✗ verify: unbound — {', '.join(inter.verify.unbound()) if inter.verify else '?'}"
    parts = [f'<div class="answer-text">{" ".join(right)}</div>',
             f'<div class="vstatus {"ok" if ok else "bad"}">{vtext}</div>']
    for eq, deq_ok in derivations:
        parts.append(f'<p class="deriv">ƒ {_esc(eq)} <span class="{"ok" if deq_ok else "bad"}">'
                     f'{"✓ recomputed" if deq_ok else "✗ mismatch"}</span></p>')
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


def _abstain_card(inter: Interaction, seg_id) -> str:
    parts = [f'<p class="reason">{_esc(inter.reason)}</p>']
    if inter.note:
        parts.append(f"<p>{_esc(inter.note)}</p>")
    for h in inter.closest:
        mid = seg_id(h.span.doc_id, h.span.char_start)
        link = f'<a data-target="{mid}">{_esc(h.span.text)}</a>' if mid else _esc(h.span.text)
        score = f'<span style="color:#8b93a3">(score {h.score:.0f})</span>'
        parts.append(f'<p class="closest">▸ {link} {score}</p>')
    return "".join(parts)


def render_evidence_view(
    interactions: list[Interaction], store: SpanStore, *, title: str = "ATTEST — evidence view"
) -> str:
    painted = {doc_id: _paint(rs) for doc_id, rs in _gather(interactions, store).items()}

    def seg_id(doc_id: str, pos: int) -> str:
        return _seg_id(painted.get(doc_id, []), pos)

    # Document pane(s): one per doc that has any citation (else the first doc in the store).
    doc_ids = list(painted) or list(store._docs)[:1]
    panes = []
    for doc_id in doc_ids:
        m = store._docs[doc_id].metadata
        label = f"{m.get('company', doc_id)} {m.get('form', '')}".strip() + " — canonical text"
        panes.append(_doc_pane(store, doc_id, painted.get(doc_id, []), label))

    cards = []
    for inter in interactions:
        body = _answer_card(inter, store, seg_id) if (
            inter.kind == "answer" and inter.answer is not None
        ) else _abstain_card(inter, seg_id)
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
