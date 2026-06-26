"""render_evidence_view — server-less two-pane evidence GUI (ROADMAP M2-T7, D8).

Turns verified interactions into a single self-contained HTML page: the answer on
the right, its source spans on the left, click-to-source highlights between them.
Abstentions show the refusal plus the closest spans found. Read-only (I4) and
deterministic — given the same interactions + store, the same bytes out.

This is the static precursor to the M5 React app. It renders the *normalized
canonical text* (the hashed, cited text), not the original filing HTML — the thing
ATTEST actually verifies (D8). The hyperlinks are generated from verified bindings,
never hand-authored: a claim links to a span only if `verify` resolved it.

The human reviewer's job here is the one thing v1 doesn't gate: click a claim,
read its span, and judge whether it actually *supports* the claim (entailment).
"""

from __future__ import annotations

import html
from dataclasses import dataclass, field

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


_CSS = """
:root { --bg:#0f1115; --panel:#171a21; --ink:#e6e9ef; --muted:#8b93a3;
  --line:#262b36; --mark:#3b2f12; --markb:#e0a32e; --ok:#3fb950; --bad:#f85149;
  --chip:#1f6feb22; --chipb:#388bfd; }
* { box-sizing:border-box; }
body { margin:0; background:var(--bg); color:var(--ink);
  font:15px/1.55 ui-sans-serif,system-ui,-apple-system,Segoe UI,Roboto,sans-serif; }
header { padding:20px 28px; border-bottom:1px solid var(--line); }
header h1 { margin:0 0 4px; font-size:18px; }
header p { margin:0; color:var(--muted); font-size:13px; }
.card { border-bottom:1px solid var(--line); padding:22px 28px; }
.q { font-weight:600; margin:0 0 2px; }
.badge { display:inline-block; font-size:11px; font-weight:700; letter-spacing:.04em;
  padding:2px 8px; border-radius:999px; text-transform:uppercase; margin-bottom:12px; }
.badge.answer { background:#11331c; color:var(--ok); }
.badge.abstain, .badge.reject, .badge.partial { background:#3a1d1d; color:var(--bad); }
.cols { display:grid; grid-template-columns:1fr 1fr; gap:18px; }
@media (max-width:760px){ .cols{ grid-template-columns:1fr; } }
.pane h3 { font-size:11px; text-transform:uppercase; letter-spacing:.06em;
  color:var(--muted); margin:0 0 8px; }
.answer-text { background:var(--panel); border:1px solid var(--line); border-radius:8px;
  padding:14px 16px; }
.src { background:var(--panel); border:1px solid var(--line); border-radius:8px;
  padding:10px 12px; margin-bottom:8px; font-family:ui-monospace,SFMono-Regular,Menlo,monospace;
  font-size:13px; white-space:pre-wrap; transition:background .15s,border-color .15s; }
.src .prov { display:block; font-family:inherit; color:var(--muted); font-size:11px;
  margin-bottom:4px; }
.src.flash { background:#1d2740; border-color:var(--chipb); }
mark { background:var(--mark); color:var(--markb); border-radius:3px; padding:0 2px;
  font-weight:600; }
.chip { background:var(--chip); border:1px solid var(--chipb); color:var(--ink);
  border-radius:4px; padding:0 4px; cursor:pointer; font-weight:600; }
.chip.derived { background:#2a1f3a; border-color:#a371f7; }
.chip.bad { background:#3a1d1d; border-color:var(--bad); }
.reason { color:var(--muted); margin:0 0 10px; }
.foot { padding:14px 28px; color:var(--muted); font-size:12px; }
.vstatus { font-size:12px; margin-top:8px; }
.vstatus.ok { color:var(--ok); } .vstatus.bad { color:var(--bad); }
"""

_JS = """
document.querySelectorAll('.chip[data-target]').forEach(c => {
  c.addEventListener('click', () => {
    const el = document.getElementById(c.dataset.target);
    if (!el) return;
    document.querySelectorAll('.src.flash').forEach(s => s.classList.remove('flash'));
    el.classList.add('flash');
    el.scrollIntoView({behavior:'smooth', block:'center'});
  });
});
"""


def _esc(s: str) -> str:
    return html.escape(s, quote=True)


def _highlight(span_text: str, span_start: int, marks: list[tuple[int, int]]) -> str:
    """Wrap atom ranges (absolute offsets) inside a span's text with <mark>."""
    rel = sorted((s - span_start, e - span_start) for s, e in marks)
    out, cursor = [], 0
    for s, e in rel:
        s, e = max(s, cursor), max(e, cursor)
        out.append(_esc(span_text[cursor:s]))
        out.append(f"<mark>{_esc(span_text[s:e])}</mark>")
        cursor = e
    out.append(_esc(span_text[cursor:]))
    return "".join(out)


def _render_answer(inter: Interaction, store: SpanStore, idx: int) -> tuple[str, str]:
    """Return (right-pane answer HTML, left-pane source HTML) for an answered interaction."""
    # Collect every bound atom (direct + derived operands) → its enclosing span.
    bindings = []
    for s in inter.answer.sentences:
        bindings += [(a, False) for a in s.atoms]
        bindings += [(o, True) for d in s.derived for o in d.operands]

    span_dom: dict[str, str] = {}      # enclosing span_id → dom id
    span_marks: dict[str, tuple] = {}  # span_id → (Span, [ranges])
    chip_target: dict[tuple, str] = {} # (literal, char_start) → dom id
    for atom, _is_op in bindings:
        sp = store.span_containing(atom.doc_id, atom.char_start)
        if not sp:
            continue
        dom = span_dom.setdefault(sp.span_id, f"src-{idx}-{len(span_dom)}")
        span, ranges = span_marks.setdefault(sp.span_id, (sp, []))
        ranges.append((atom.char_start, atom.char_end))
        chip_target[(atom.text, atom.char_start)] = dom

    # Left pane: each enclosing span, atoms highlighted, with provenance.
    left = []
    for span_id, (sp, ranges) in span_marks.items():
        text = store.get_span(sp.doc_id, sp.char_start, sp.char_end)
        body = _highlight(text, sp.char_start, ranges)
        prov = f"{sp.doc_id} · chars {sp.char_start}–{sp.char_end}"
        left.append(
            f'<div class="src" id="{span_dom[span_id]}">'
            f'<span class="prov">{prov}</span>{body}</div>'
        )

    # Right pane: answer text with each atom literal turned into a click-to-source chip.
    ok = inter.verify.ok if inter.verify else False
    right = []
    for s in inter.answer.sentences:
        text = s.text
        chips: list[tuple[str, str, str]] = []  # (literal, cls, target)
        for a in s.atoms:
            tgt = chip_target.get((a.text, a.char_start), "")
            chips.append((a.text, "chip", tgt))
        for d in s.derived:
            chips.append((d.text, "chip derived", ""))
            for o in d.operands:
                chips.append((o.text, "chip", chip_target.get((o.text, o.char_start), "")))
        right.append(_chip_sentence(text, chips))
    vclass = "ok" if ok else "bad"
    vtext = "✓ verify: every figure resolves to a cited span" if ok else \
        f"✗ verify: unbound — {', '.join(inter.verify.unbound()) if inter.verify else '?'}"
    answer_html = (
        f'<div class="answer-text">{" ".join(right)}</div>'
        f'<div class="vstatus {vclass}">{vtext}</div>'
    )
    return answer_html, "".join(left)


def _chip_sentence(text: str, chips: list[tuple[str, str, str]]) -> str:
    """Escape sentence text, then swap each literal for a chip (first occurrence)."""
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


def _render_abstain(inter: Interaction) -> tuple[str, str]:
    right = f'<p class="reason">{_esc(inter.reason)}</p>'
    if inter.kind in ("reject", "partial") and inter.note:
        right += f"<p>{_esc(inter.note)}</p>"
    left = []
    for h in inter.closest:
        sp = h.span
        prov = f"{sp.doc_id} · chars {sp.char_start}–{sp.char_end} · score {h.score:.1f}"
        left.append(
            f'<div class="src"><span class="prov">{prov}</span>{_esc(sp.text)}</div>'
        )
    label = "Closest spans it did find (shown to prove it looked):" if left else ""
    left_html = (f'<p class="reason">{label}</p>' + "".join(left)) if left else \
        '<p class="reason">No span cleared the relevance floor.</p>'
    return right, left_html


def render_evidence_view(
    interactions: list[Interaction], store: SpanStore, *, title: str = "ATTEST — evidence view"
) -> str:
    cards = []
    for idx, inter in enumerate(interactions):
        if inter.kind == "answer" and inter.answer is not None:
            right, left = _render_answer(inter, store, idx)
        else:
            right, left = _render_abstain(inter)
        show_note = inter.note and inter.kind == "answer"
        note = f'<p class="reason">{_esc(inter.note)}</p>' if show_note else ""
        cards.append(
            f'<section class="card"><p class="q">{_esc(inter.question)}</p>'
            f'<span class="badge {inter.kind}">{inter.kind}</span>{note}'
            f'<div class="cols">'
            f'<div class="pane"><h3>Answer</h3>{right}</div>'
            f'<div class="pane"><h3>Source (canonical text)</h3>{left}</div>'
            f'</div></section>'
        )
    return (
        "<!doctype html><html lang=en><head><meta charset=utf-8>"
        '<meta name=viewport content="width=device-width,initial-scale=1">'
        f"<title>{_esc(title)}</title><style>{_CSS}</style></head><body>"
        f"<header><h1>{_esc(title)}</h1>"
        "<p>Click a highlighted figure to jump to its verbatim source span. "
        "Your review job: does the cited span actually support the claim? "
        "(entailment — not gated in v1)</p>"
        "</header>"
        + "".join(cards)
        + '<p class="foot">Deterministic, server-less render of verified interactions '
        "(ROADMAP M2-T7 / D8). Source is the normalized canonical text ATTEST hashes and cites.</p>"
        f"<script>{_JS}</script></body></html>"
    )
