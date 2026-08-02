"""locate_pane — ask the corpus what it has, live (RT-10b, D49).

**What this pane is not.** It does not answer questions. Cairn makes no model calls, so
there is nothing here that could compose prose — and that is the design, not a gap. The
reasoner is the agent in a Claude Code session; this pane runs the *locate* step it would
run, and shows the reviewer the same evidence, with the same support decision, recorded to
the same audit log.

So the honest framing on the page is: **"what does this corpus have?"** — supporting spans
above the floor, or `insufficient` plus the closest passages found, which is how the system
shows it looked and where (D12). A reviewer reads spans and decides; the page never decides
for them.

The support decision is only as good as its floor, so the calibration state is repeated
here rather than left to the console header alone — a reviewer who lands on this pane and
reads `insufficient` is exactly the person who needs to know the floor came from a
different corpus.
"""

from __future__ import annotations


def render(*, calibrated: bool, calibration: str) -> str:
    cls = "ok" if calibrated else "warn"
    return _PAGE.replace("{{CAL_CLASS}}", cls).replace("{{CAL}}", calibration)


_PAGE = r"""<meta charset="utf-8"><title>Locate</title>
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
.wrap{max-width:860px;margin:0 auto}
h1{font:600 20px/1.3 var(--sans);margin:0 0 4px}
.sub{color:var(--mut);font-size:13px;margin:0 0 16px;max-width:68ch}
.cal{font-size:12.5px;padding:8px 12px;border-radius:6px;margin:0 0 18px}
.cal.ok{background:var(--okbg);color:var(--ok)}
.cal.warn{background:var(--warnbg);color:var(--warn);font-weight:500}
form{display:flex;gap:8px;margin:0 0 6px}
input[type=text]{flex:1;padding:10px 13px;border:1px solid var(--rule);border-radius:7px;
 background:var(--panel);color:var(--ink);font:15px var(--sans)}
button{padding:10px 18px;border:0;border-radius:7px;background:var(--accent);color:#fff;
 font:600 14px var(--sans);cursor:pointer}
button:disabled{opacity:.55;cursor:default}
.hint{font-size:12px;color:var(--mut);margin:0 0 22px}
.verdict{border-radius:8px;padding:13px 16px;margin:0 0 14px;font-size:14px}
.verdict.supported{background:var(--okbg);color:var(--ok)}
.verdict.insufficient{background:var(--warnbg);color:var(--warn)}
.verdict b{display:block;font-size:15px;margin-bottom:3px}
.span{background:var(--panel);border:1px solid var(--rule);border-left:3px solid var(--accent);
 border-radius:0 7px 7px 0;padding:11px 14px;margin:0 0 9px}
.span .loc{font:11.5px var(--mono);color:var(--mut);margin-bottom:5px}
.span .txt{font:14px/1.6 Georgia,serif}
.span.near{border-left-color:var(--mut);opacity:.9}
.err{background:var(--warnbg);color:var(--warn);padding:11px 14px;border-radius:7px;
 font-size:13.5px}
.note{margin-top:26px;padding-top:14px;border-top:1px solid var(--rule);
 font-size:12.5px;color:var(--mut);max-width:70ch}
</style>
<div class="wrap">
  <h1>What does this corpus have?</h1>
  <p class="sub">This runs the <b>locate</b> step and shows you the evidence. It does not
  compose an answer — Cairn makes no model calls, so reading the spans and deciding what
  they support is yours to do.</p>
  <p class="cal {{CAL_CLASS}}">{{CAL}}</p>

  <form id="f">
    <input type="text" id="q" placeholder="e.g. what were total assets at year end?"
           autocomplete="off" aria-label="Question">
    <button id="go">Locate</button>
  </form>
  <p class="hint">Recorded to the audit log, exactly as an agent's call would be.</p>

  <div id="out"></div>

  <p class="note">Below the support floor the system returns <b>insufficient</b> and shows
  the closest passages it found — proof that it looked, and where. That is a content
  judgment about this corpus, not a claim that the answer does not exist anywhere.</p>
</div>
<script>
const out = document.getElementById('out');
const esc = s => String(s).replace(/[&<>"]/g, c =>
  ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));

// A hit is {span_id, score}; span_id is "doc@start-end". The TEXT is fetched through
// get_span, which re-verifies the document hash (I3) — so what the reviewer reads is
// exactly what verification would confirm, not a cached copy that could have drifted.
async function spanText(spanId) {
  const m = /^(.*)@(\d+)-(\d+)$/.exec(spanId);
  if (!m) return {loc: spanId, text: ''};
  const [, doc, start, end] = m;
  try {
    const r = await fetch('tool/get_span', {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({doc_id: doc, start: Number(start), end: Number(end)})
    });
    const d = await r.json();
    return {loc: doc + '  ' + start + '–' + end, text: d.text || d.error || ''};
  } catch (e) {
    return {loc: doc + '  ' + start + '–' + end, text: ''};
  }
}

async function spanCard(h, near) {
  const s = await spanText(h.span_id);
  const score = (h.score != null) ? '  ·  score ' + h.score.toFixed(2) : '';
  return '<div class="span' + (near ? ' near' : '') + '">' +
         '<div class="loc">' + esc(s.loc) + esc(score) + '</div>' +
         '<div class="txt">' + esc(s.text) + '</div></div>';
}

document.getElementById('f').addEventListener('submit', async ev => {
  ev.preventDefault();
  const q = document.getElementById('q').value.trim();
  if (!q) return;
  const btn = document.getElementById('go');
  btn.disabled = true;
  out.innerHTML = '<p class="hint">locating…</p>';
  try {
    const r = await fetch('tool/check_support', {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({query: q})
    });
    const d = await r.json();
    if (d.error) { out.innerHTML = '<div class="err">' + esc(d.error) + '</div>'; return; }
    const ok = d.status === 'supported';
    let html = '<div class="verdict ' + esc(d.status) + '"><b>' +
      (ok ? 'Supported — ' + d.supporting.length + ' span(s) clear the floor'
          : 'Insufficient — nothing clears the floor') + '</b>' +
      (ok ? 'Read them and decide what they support.'
          : 'The closest passages found are shown, so you can see where it looked.') +
      '</div>';
    if (d.calibration_warning) {
      html += '<div class="err">' + esc(d.calibration_warning) + '</div>';
    }
    const hits = ok ? d.supporting : d.closest;
    html += (await Promise.all(hits.map(h => spanCard(h, !ok)))).join('');
    out.innerHTML = html;
  } catch (e) {
    out.innerHTML = '<div class="err">Could not reach the review server. Start it with ' +
      'python scripts/serve_console.py — this pane needs the real tools, because a ' +
      'second retrieval implementation in the browser could drift from the real one.' +
      '</div>';
  } finally { btn.disabled = false; }
});
</script>
"""
