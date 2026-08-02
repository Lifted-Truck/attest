"""adjudicate_pane — the review queue, with judgment recorded in place (RT-7b, D50).

Closes the loop the product roadmap identified as Cairn's one structural gap: the expert
whose judgment the system exists to support could read every surface and write to none of
them. RT-7a made judgment *durable*; this makes it *reachable* — a worklist where each row
is one decision and one click, instead of hand-typing coordinates into a CLI.

Three properties the page must not lose:

  · **Confirming is not the default.** Nothing is pre-selected and there is no "accept
    all". A queue that can be cleared without reading it produces a record that says a
    human looked when none did, which is worse than no record.
  · **The reviewer is named by the server, not the page.** Provenance comes from who
    started the session, so a judgment cannot be attributed by whoever has the tab open.
  · **An empty queue is not a clean bill of health,** and it says so: these checks compare
    drawings against the specification, so anything absent from both is invisible to all
    of them.
"""

from __future__ import annotations

import html
import json


def _e(s: object) -> str:
    return html.escape(str(s), quote=True)


def render(items, *, reviewer: str | None, on: str | None) -> str:
    rows = []
    for i in items:
        loc = (f"p.{i.page}" if i.page is not None else "not located")
        target = json.dumps({k: v for k, v in
                             (("page", i.page), ("numeral", i.label),
                              ("x", i.x), ("y", i.y)) if v is not None})
        rows.append(
            f"<li class='item' data-id='{_e(i.item_id)}' data-target='{_e(target)}'>"
            f"<div class='hd'><span class='kind k-{_e(i.kind)}'>{_e(i.kind.replace('_',' '))}"
            f"</span><span class='lbl'>{_e(i.label)}</span>"
            f"<span class='loc'>{_e(loc)}</span></div>"
            f"<p class='q'>{_e(i.question)}</p>"
            f"<p class='d'>{_e(i.detail)}</p>"
            f"<div class='acts'>"
            f"<button data-kind='confirm'>It is there</button>"
            f"<button data-kind='refute'>It is not there</button>"
            f"<button data-kind='note' class='ghost'>Note only</button>"
            f"<span class='said'></span></div></li>")

    who = (f"Recording as <b>{_e(reviewer)}</b> on {_e(on)}."
           if reviewer and on else
           "<b>Read-only.</b> This server was started without a reviewer identity, so "
           "judgments cannot be recorded. Restart with --reviewer and --on.")
    empty = ("<li class='empty'><b>Nothing outstanding.</b> That is not a clean bill of "
             "health: these checks compare the drawings against the specification, so "
             "anything absent from both is invisible to all of them.</li>")
    return _PAGE.replace("{{ROWS}}", "".join(rows) or empty) \
                .replace("{{WHO}}", who) \
                .replace("{{N}}", str(len(items)))


_PAGE = r"""<meta charset="utf-8"><title>Adjudicate</title>
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
 padding:22px 26px 60px}
.wrap{max-width:880px;margin:0 auto}
h1{font:600 20px/1.3 var(--sans);margin:0 0 4px}
.sub{color:var(--mut);font-size:13px;margin:0 0 6px;max-width:70ch}
.who{font-size:12.5px;color:var(--mut);margin:0 0 20px;padding:8px 12px;
 background:var(--panel);border:1px solid var(--rule);border-radius:6px}
ul{list-style:none;padding:0;margin:0}
.item{background:var(--panel);border:1px solid var(--rule);border-radius:9px;
 padding:14px 16px;margin:0 0 11px}
.item.done{opacity:.55}
.hd{display:flex;align-items:baseline;gap:10px;flex-wrap:wrap;margin-bottom:6px}
.kind{font:600 10.5px/1.7 var(--sans);text-transform:uppercase;letter-spacing:.05em;
 padding:1px 8px;border-radius:10px;background:var(--warnbg);color:var(--warn)}
.kind.k-recited_not_drawn{background:var(--bg);color:var(--mut)}
.lbl{font:700 17px/1 var(--mono)}
.loc{font:11.5px var(--mono);color:var(--mut)}
.q{margin:0 0 4px;font-weight:600;font-size:14.5px}
.d{margin:0 0 11px;font-size:13px;color:var(--mut);max-width:72ch}
.acts{display:flex;gap:8px;align-items:center;flex-wrap:wrap}
button{padding:6px 13px;border:1px solid var(--rule);border-radius:6px;background:var(--bg);
 color:var(--ink);font:600 13px var(--sans);cursor:pointer}
button:hover{border-color:var(--accent)}
button.ghost{font-weight:400;color:var(--mut)}
button:disabled{opacity:.5;cursor:default}
.said{font-size:12.5px;color:var(--ok)}
.said.bad{color:var(--warn)}
.empty{background:var(--panel);border:1px solid var(--rule);border-radius:9px;
 padding:18px;color:var(--mut);font-size:13.5px}
.note{margin-top:26px;padding-top:14px;border-top:1px solid var(--rule);
 font-size:12.5px;color:var(--mut);max-width:72ch}
</style>
<div class="wrap">
  <h1>Needs a human — {{N}} outstanding</h1>
  <p class="sub">Ranked by what costs most to get wrong, not by count. Nothing is
  pre-selected and there is no bulk accept: a queue that can be cleared without reading it
  produces a record saying someone looked when nobody did.</p>
  <p class="who">{{WHO}}</p>
  <ul id="q">{{ROWS}}</ul>
  <p class="note">Every judgment is appended to a hash-chained record with your name and
  the date. Nothing is edited or deleted — a later change of mind is a new entry that
  supersedes the old one, and both remain readable.</p>
</div>
<script>
document.querySelectorAll('.item button').forEach(btn => {
  btn.addEventListener('click', async () => {
    const li = btn.closest('.item');
    const said = li.querySelector('.said');
    const note = (btn.dataset.kind === 'note')
      ? (prompt('Note (recorded verbatim, asserts nothing about the mark):') || '') : '';
    if (btn.dataset.kind === 'note' && !note) return;
    li.querySelectorAll('button').forEach(b => b.disabled = true);
    said.className = 'said'; said.textContent = 'recording…';
    try {
      const r = await fetch('adjudicate', {
        method: 'POST', headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
          item_id: li.dataset.id, kind: btn.dataset.kind,
          target: JSON.parse(li.dataset.target), note: note
        })
      });
      const d = await r.json();
      if (d.error) {
        said.className = 'said bad'; said.textContent = d.error;
        li.querySelectorAll('button').forEach(b => b.disabled = false);
      } else {
        said.textContent = 'recorded as ' + d.by + ' on ' + d.on;
        li.classList.add('done');
      }
    } catch (e) {
      said.className = 'said bad';
      said.textContent = 'no review server — start scripts/serve_console.py';
      li.querySelectorAll('button').forEach(b => b.disabled = false);
    }
  });
});
</script>
"""
