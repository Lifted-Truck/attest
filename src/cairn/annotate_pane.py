"""annotate_pane — draw a box over a sheet to assert a mark OCR missed (RT-7c, D51).

The last leg of the loop. The review queue can only act on marks the tool already
*located*; a miss has no coordinates, so there is nothing to click. This is where the
reviewer supplies them.

The page deliberately does not convert anything. It reports the drag in pixels and the
displayed size, and the server turns that into manifest coordinates — see `annotate.py`
for why that split is load-bearing rather than tidy.

**A box is a sighting, not a search.** Recording one asserts "I can see this here", with
the reviewer's name and the date. It does not re-run OCR over the region: OCR is an
ingestion-time step whose output is frozen and hashed (D28), and calling an engine at
review time would put a model call on the runtime path (I6). The page says so, because a
reviewer who believes they triggered a re-scan would draw different conclusions from an
empty result than the truth warrants.
"""

from __future__ import annotations

import html
import json


def _e(s: object) -> str:
    return html.escape(str(s), quote=True)


def render(sheets: list[dict], *, reviewer: str | None, on: str | None) -> str:
    """`sheets` = [{page, file, figures}] — already copied beside the console."""
    opts = "".join(
        f"<option value='{_e(s['page'])}' data-file='{_e(s['file'])}'>"
        f"p.{_e(s['page'])}{(' — FIG ' + _e(s['figures'])) if s.get('figures') else ''}"
        f"</option>" for s in sheets)
    who = (f"Recording as <b>{_e(reviewer)}</b> on {_e(on)}."
           if reviewer and on else
           "<b>Read-only.</b> Started without a reviewer identity, so a box cannot be "
           "recorded. Restart the server with --reviewer and --on.")
    return (_PAGE.replace("{{OPTS}}", opts or "<option>no sheets</option>")
                 .replace("{{WHO}}", who)
                 .replace("{{SHEETS}}", json.dumps(sheets)))


_PAGE = r"""<meta charset="utf-8"><title>Mark a sheet</title>
<style>
:root{--bg:#f7f5f0;--panel:#fff;--ink:#161c26;--mut:#5d6779;--rule:#dcd6ca;
 --ok:#3f6b52;--okbg:#e9f1ec;--warn:#a2402f;--warnbg:#fbeeeb;--accent:#2f4f8f;
 --sans:ui-sans-serif,system-ui,"Segoe UI",Helvetica,sans-serif;
 --mono:ui-monospace,"SF Mono",Menlo,monospace}
@media (prefers-color-scheme:dark){:root{--bg:#0f131a;--panel:#151b24;--ink:#e7e3d9;
 --mut:#98a2b3;--rule:#2a323f;--ok:#7fc39c;--okbg:#16241d;--warn:#e8837a;
 --warnbg:#271619;--accent:#8fb3dd}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font:14.5px/1.6 var(--sans);
 padding:20px 24px 60px}
.wrap{max-width:1000px;margin:0 auto}
h1{font:600 20px/1.3 var(--sans);margin:0 0 4px}
.sub{color:var(--mut);font-size:13px;margin:0 0 12px;max-width:74ch}
.who{font-size:12.5px;color:var(--mut);margin:0 0 14px;padding:8px 12px;
 background:var(--panel);border:1px solid var(--rule);border-radius:6px}
.bar{display:flex;gap:10px;align-items:center;flex-wrap:wrap;margin:0 0 12px}
select,input[type=text]{padding:8px 11px;border:1px solid var(--rule);border-radius:6px;
 background:var(--panel);color:var(--ink);font:14px var(--sans)}
button{padding:8px 15px;border:0;border-radius:6px;background:var(--accent);color:#fff;
 font:600 13.5px var(--sans);cursor:pointer}
button:disabled{opacity:.5;cursor:default}
button.ghost{background:var(--bg);color:var(--mut);border:1px solid var(--rule)}
#stage{position:relative;display:inline-block;max-width:100%;background:var(--panel);
 border:1px solid var(--rule);border-radius:8px;overflow:hidden;cursor:crosshair}
#sheet{display:block;max-width:100%;height:auto;user-select:none;-webkit-user-drag:none}
#rect{position:absolute;border:2px solid var(--accent);background:rgba(47,80,143,.14);
 pointer-events:none;display:none}
.said{font-size:13px;margin:12px 0 0}
.said.ok{color:var(--ok)} .said.bad{color:var(--warn)}
.note{margin-top:22px;padding-top:14px;border-top:1px solid var(--rule);
 font-size:12.5px;color:var(--mut);max-width:74ch}
.note b{color:var(--ink)}
</style>
<div class="wrap">
  <h1>Mark something OCR missed</h1>
  <p class="sub">Drag a box around a reference numeral you can see on the sheet, then name
  it. The queue can only offer marks the tool already located — a miss has no coordinates,
  so this is where you supply them.</p>
  <p class="who">{{WHO}}</p>

  <div class="bar">
    <select id="page">{{OPTS}}</select>
    <input type="text" id="label" placeholder="what is it? e.g. 14a, A, D3" size="14">
    <button id="save" disabled>Record this mark</button>
    <button id="clear" class="ghost">Clear box</button>
  </div>

  <div id="stage"><img id="sheet" alt="drawing sheet"><div id="rect"></div></div>
  <p class="said" id="said"></p>

  <p class="note">A recorded box is a <b>sighting</b>: your name, the date, and where you
  saw it. It does <b>not</b> re-run OCR over the region — OCR is an ingestion-time step
  whose output is frozen and hashed, and running an engine at review time would put a
  model call on the path this system's determinism depends on. Your mark can inform a
  later ingestion pass; it does not silently become one.</p>
</div>
<script>
const SHEETS = {{SHEETS}};
const img = document.getElementById('sheet'), stage = document.getElementById('stage'),
      rect = document.getElementById('rect'), sel = document.getElementById('page'),
      said = document.getElementById('said'), save = document.getElementById('save');
let box = null, drag = null;

function loadSheet() {
  const o = sel.selectedOptions[0];
  if (o && o.dataset.file) img.src = 'sheets/' + o.dataset.file;
  clearBox();
}
function clearBox() { box = null; rect.style.display = 'none'; save.disabled = true; }
sel.addEventListener('change', loadSheet);
document.getElementById('clear').addEventListener('click', clearBox);

function at(ev) {
  const r = img.getBoundingClientRect();
  return {x: Math.max(0, Math.min(ev.clientX - r.left, r.width)),
          y: Math.max(0, Math.min(ev.clientY - r.top, r.height))};
}
stage.addEventListener('pointerdown', ev => {
  ev.preventDefault(); drag = at(ev); stage.setPointerCapture(ev.pointerId);
});
stage.addEventListener('pointermove', ev => {
  if (!drag) return;
  const p = at(ev);
  Object.assign(rect.style, {display: 'block',
    left: Math.min(drag.x, p.x) + 'px', top: Math.min(drag.y, p.y) + 'px',
    width: Math.abs(p.x - drag.x) + 'px', height: Math.abs(p.y - drag.y) + 'px'});
});
stage.addEventListener('pointerup', ev => {
  if (!drag) return;
  const p = at(ev), r = img.getBoundingClientRect();
  // Pixels and the displayed size only. The page never computes a normalized
  // coordinate: that conversion lives in Python where a test can reach it.
  box = {x0: drag.x, y0: drag.y, x1: p.x, y1: p.y, width: r.width, height: r.height};
  drag = null;
  save.disabled = !(Math.abs(box.x1 - box.x0) > 3 && Math.abs(box.y1 - box.y0) > 3);
  said.textContent = save.disabled ? 'That is a click, not a box — drag across the mark.' : '';
  said.className = 'said' + (save.disabled ? ' bad' : '');
});

save.addEventListener('click', async () => {
  const label = document.getElementById('label').value.trim();
  if (!label) { said.className = 'said bad'; said.textContent = 'Name the mark first.'; return; }
  if (!box) return;
  save.disabled = true; said.className = 'said'; said.textContent = 'recording…';
  try {
    const r = await fetch('adjudicate', {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({
        item_id: 'drawn:p' + sel.value + ':' + label, kind: 'confirm',
        target: {page: Number(sel.value), numeral: label}, box_px: box,
        note: 'drawn on the sheet by the reviewer'
      })
    });
    const d = await r.json();
    if (d.error) { said.className = 'said bad'; said.textContent = d.error; save.disabled = false; }
    else {
      said.className = 'said ok';
      said.textContent = 'recorded “' + label + '” as ' + d.by + ' on ' + d.on +
        ' — rebuild the console to see it on the sheet.';
      clearBox(); document.getElementById('label').value = '';
    }
  } catch (e) {
    said.className = 'said bad';
    said.textContent = 'no review server — start scripts/serve_console.py';
    save.disabled = false;
  }
});
loadSheet();
</script>
"""
