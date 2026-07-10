#!/usr/bin/env python3
"""Patent drawings review artifact (RT-4) → figures visible beside the text index.

Renders a self-contained HTML page: the patent's **drawing sheets** on the left, and
on the right the parsed **figure captions** (`parse_figures`) and the **reference-
numeral legend** (`reference_numerals`) — each numeral annotated with the figure it is
**first discussed with** (nearest preceding `FIG. N` reference in the text). Click a
figure to filter the legend to its numerals; click a numeral to see its first-mention
context. The sheets are embedded as data URIs (server-less, like the evidence view).

Prereqs (local-only): the drawing images fetched by `scripts/fetch_patent_figures.py`
into `<store>/../figures/`. The engagement store + figures are gitignored, so this is
a local reviewable artifact (the generator is generic; point it at any ingested
patent that has fetched figures).

    python scripts/patent_figures_view.py --store corpus/engagements/US5447630A/store \\
        --doc US5447630A --out figures_view.html

**Truth-contract boundary (D21):** a drawing is *displayed evidence*, not a text
citation — the numeral→figure link is "first discussed near FIG. N" in the text, a
locate-only aid (D10), never a claim about what a figure depicts or construes.
"""

from __future__ import annotations

import argparse
import base64
import html
import json
from pathlib import Path

import _bootstrap  # noqa: F401  (puts src/ on sys.path)

from attest.ingest import DocumentStore
from attest.patents import (
    figure_references,
    parse_figures,
    reference_numerals,
)
from attest.spans import SpanStore

_NEAR = 500          # a numeral is "discussed with" the nearest FIG ref within this


def numeral_figure(numeral_start: int, fig_refs) -> str | None:
    """The figure a numeral is first discussed with: the nearest FIG. N reference at
    or before the numeral's first mention, within _NEAR chars. Locate-only."""
    best = None
    for r in fig_refs:
        if r.char_start <= numeral_start and numeral_start - r.char_start <= _NEAR:
            if best is None or r.char_start > best.char_start:
                best = r
    return best.number if best else None


def snippet(text: str, start: int, end: int, pad: int = 90) -> str:
    s = max(0, start - pad)
    e = min(len(text), end + pad)
    pre, hit, post = text[s:start], text[start:end], text[end:e]
    return (("…" if s else "") + html.escape(pre) + "<b>" + html.escape(hit) + "</b>"
            + html.escape(post) + ("…" if e < len(text) else ""))


def data_uri(path: Path) -> str:
    return "data:image/png;base64," + base64.b64encode(path.read_bytes()).decode()


PAGE = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>{title}</title>
<style>
:root{{--bg:#0d1117;--panel:#161b22;--panel2:#1c2230;--bd:#30363d;--tx:#c9d1d9;
--mut:#8b949e;--acc:#58a6ff;--fig:#f0883e;--num:#3fb950}}
*{{box-sizing:border-box}}
body{{margin:0;background:var(--bg);color:var(--tx);
font:15px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,Arial,sans-serif}}
.sr-only{{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0,0,0,0)}}
header{{padding:20px 24px;border-bottom:1px solid var(--bd)}}
h1{{margin:0 0 3px;font-size:20px;letter-spacing:-.3px}}
.sub{{color:var(--mut);font-size:13px}}
.cols{{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);
gap:0;height:calc(100vh - 70px)}}
.pane{{overflow:auto;padding:18px 22px}}
.pane.left{{border-right:1px solid var(--bd);background:#0b0f16}}
h2{{font-size:13px;text-transform:uppercase;letter-spacing:.6px;color:var(--mut);
margin:0 0 12px;font-weight:700}}
.sheet{{margin:0 0 16px}}
.sheet .cap{{font-size:11px;color:var(--mut);font-family:ui-monospace,monospace;margin-bottom:5px}}
.sheet img{{width:100%;border:1px solid var(--bd);border-radius:8px;background:#fff;display:block}}
.fig{{background:var(--panel);border:1px solid var(--bd);border-left:3px solid var(--fig);
border-radius:8px;padding:11px 13px;margin:0 0 9px;cursor:pointer;transition:.12s}}
.fig:hover{{border-color:var(--fig)}}
.fig.sel{{background:#2a1c12;border-left-width:5px}}
.fig .fl{{font-weight:700;color:var(--fig);font-family:ui-monospace,monospace}}
.fig .fd{{color:var(--tx);font-size:13px;margin-top:2px}}
.legend{{display:flex;flex-wrap:wrap;gap:6px;margin:0 0 14px}}
.num{{background:var(--panel);border:1px solid var(--bd);border-radius:6px;
padding:4px 9px;font-size:12.5px;cursor:pointer;transition:.12s;white-space:nowrap}}
.num:hover{{border-color:var(--num)}}
.num.dim{{opacity:.28}}
.num b{{color:var(--num);font-family:ui-monospace,monospace}}
.num .fg{{color:var(--fig);font-family:ui-monospace,monospace;font-size:11px;margin-left:4px}}
#ctx{{position:sticky;bottom:0;background:#0b0f16f2;border:1px solid var(--bd);
border-radius:8px;padding:11px 13px;font-size:12.5px;min-height:20px;color:var(--mut)}}
#ctx b{{color:var(--tx);background:#243; padding:0 2px;border-radius:3px}}
.note{{color:var(--mut);font-size:11.5px;margin:14px 0 0;line-height:1.5}}
</style></head><body>
<h2 class="sr-only">{title}: drawing sheets beside parsed figure captions and numerals.</h2>
<header><h1>{h1}</h1><div class="sub">{sub}</div></header>
<div class="cols">
  <div class="pane left"><h2>Drawing sheets ({nsheets})</h2>{sheets}</div>
  <div class="pane right">
    <h2>Figures ({nfigs})</h2>{figs}
    <h2 style="margin-top:20px">Reference numerals ({nnums})</h2>
    <div class="legend" id="legend">{nums}</div>
    <div id="ctx">Click a numeral to see where it is first named; click a figure to filter.</div>
    <p class="note">{note}</p>
  </div>
</div>
<script>
const CTX = {ctx_json};
const legend = document.getElementById('legend');
const ctx = document.getElementById('ctx');
let selFig = null;
function filter(fig){{
  selFig = (selFig===fig)?null:fig;
  document.querySelectorAll('.fig').forEach(f=>f.classList.toggle('sel', f.dataset.fig===selFig));
  document.querySelectorAll('.num').forEach(n=>{{
    const show = !selFig || n.dataset.fig===selFig;
    n.classList.toggle('dim', !show);
  }});
  ctx.innerHTML = selFig ? `Showing numerals first discussed with <b>FIG. ${{selFig}}</b>.`
    : 'Click a numeral to see where it is first named; click a figure to filter.';
}}
document.querySelectorAll('.fig').forEach(f=>f.addEventListener('click',()=>filter(f.dataset.fig)));
document.querySelectorAll('.num').forEach(n=>n.addEventListener('click',()=>{{
  ctx.innerHTML = CTX[n.dataset.n] || '(no context)';
}}));
</script>
</body></html>"""


def main() -> int:
    ap = argparse.ArgumentParser(description="Render a patent's drawings + figure index (RT-4)")
    ap.add_argument("--store", required=True)
    ap.add_argument("--doc", required=True)
    ap.add_argument("--out", default="figures_view.html")
    ns = ap.parse_args()

    store = SpanStore.from_store(DocumentStore(ns.store))
    text = store.get_document(ns.doc)
    figs = parse_figures(text)
    refs = figure_references(text)
    nums = reference_numerals(text)

    fig_dir = Path(ns.store).parent / "figures"
    manifest_path = fig_dir / "figures_manifest.json"
    if not manifest_path.exists():
        print(f"no figures manifest at {manifest_path} — run scripts/fetch_patent_figures.py first")
        return 1
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    sheets_html = "".join(
        f'<div class="sheet"><div class="cap">sheet · page {s["page"]} '
        f'· sha256 {s["sha256"][:12]}…</div>'
        f'<img loading="lazy" alt="drawing sheet page {s["page"]}" '
        f'src="{data_uri(fig_dir / s["file"])}"></div>'
        for s in manifest["sheets"]
    )
    def _cap_body(f):                                   # caption text minus the "FIG. N is" lead
        return html.escape(f.description.split(" ", 3)[-1] if f.description else "")
    figs_html = "".join(
        f'<div class="fig" data-fig="{f.number}"><span class="fl">{f.label}</span>'
        f'<div class="fd">{_cap_body(f)}</div></div>'
        for f in figs
    )
    ctx_json, nums_html = {}, []
    for n in nums:
        fig = numeral_figure(n.char_start, refs)
        ctx_json[str(n.number)] = snippet(text, n.char_start, n.char_end)
        fg = f'<span class="fg">FIG. {fig}</span>' if fig else ""
        nums_html.append(
            f'<span class="num" data-n="{n.number}" data-fig="{fig or ""}">'
            f'<b>{n.number}</b> {html.escape(n.element)}{fg}</span>'
        )
    note = (
        "Drawings are <i>displayed evidence</i>, not text citations (truth-contract D21): "
        "grounding binds a claim to the text that recites a numeral; the sheet rides alongside. "
        "The FIG. N tag on a numeral is where it is <i>first discussed</i> in the text (nearest "
        "reference), a locate-only aid (D10) — not a claim about what the figure depicts. "
        "Element phrases and sub-figure captions are heuristic; refinable."
    )
    page = PAGE.format(
        title=f"{ns.doc} — drawings", h1=f"{ns.doc} · drawings",
        sub=f"{len(manifest['sheets'])} sheets · {len(figs)} figures · "
            f"{len(nums)} reference numerals",
        nsheets=len(manifest["sheets"]), nfigs=len(figs), nnums=len(nums),
        sheets=sheets_html, figs=figs_html, nums="".join(nums_html),
        ctx_json=json.dumps(ctx_json), note=note,
    )
    Path(ns.out).write_text(page, encoding="utf-8")
    print(f"OK — wrote {ns.out} ({len(manifest['sheets'])} sheets, {len(figs)} figures, "
          f"{len(nums)} numerals) from {ns.doc}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
