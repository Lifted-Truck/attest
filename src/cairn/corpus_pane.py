"""corpus_pane — what are we searching, and is it fit for this? (RT-2, D52).

The pane answers its own tab title, and it answers the second half honestly: a corpus is
not merely a list of documents, it is a list of documents **plus everything that was
fitted to them**. So this shows the documents, their hashes, the calibration record and
whether it still holds, the corpus-scoped constants nothing has yet tested here, and what
state the drawings are in.

**Why there is no "add document" button, and why that is a narrowing of RT-2.**
Ingestion is the one operation that invalidates everything downstream at once:

  · the support floor was fitted to *these* documents, and a BM25 score does not survive
    the corpus changing (D44 — the same reasoning as `STALE CALIBRATION`, one level up);
  · every citation already in the audit log resolves against offsets in a *specific*
    document version, and replay (I6) is a claim about that corpus, not a later one;
  · the corpus is read-only to the agent by construction (I4), and putting a corpus-write
    endpoint on a listener is a different security posture than the one D49 argued for.

None of that makes ingestion wrong — it makes it **deliberate**. It stays a CLI act with
the same weight as calibration, and this pane's job is to show the consequences of the
corpus changing rather than to make changing it a click. That is a real scope reduction
against RT-2 as written, stated here rather than quietly delivered.
"""

from __future__ import annotations

import html


def _e(s: object) -> str:
    return html.escape(str(s), quote=True)


def render(*, doc_ids, hashes, sizes, calibration, calibrated, stale,
           fitted_untested, sheets, adjudications, chain_ok) -> str:
    docs = "".join(
        f"<tr><td class='mono'>{_e(d)}</td>"
        f"<td class='mono num'>{sizes.get(d, 0):,}</td>"
        f"<td class='mono hash'>{_e(hashes.get(d, ''))}</td></tr>" for d in doc_ids)

    cal_cls = "warn" if (not calibrated or stale) else "ok"
    untested = "".join(f"<li><code>{_e(n)}</code> — {_e(why)}</li>"
                       for n, why in fitted_untested)
    sheets_line = (f"{sheets} drawing sheet(s) with a frozen OCR manifest."
                   if sheets else "No drawing sheets ingested for this corpus.")
    chain = ("verified" if chain_ok else "NOT VERIFIED")
    chain_cls = "ok" if chain_ok else "warn"

    return _PAGE.replace("{{DOCS}}", docs or
                         "<tr><td colspan='3'><i>No documents.</i></td></tr>") \
                .replace("{{N}}", str(len(doc_ids))) \
                .replace("{{CAL}}", _e(calibration)) \
                .replace("{{CAL_CLS}}", cal_cls) \
                .replace("{{UNTESTED}}", untested or
                         "<li>Every corpus-scoped constant has been exercised here.</li>") \
                .replace("{{SHEETS}}", _e(sheets_line)) \
                .replace("{{ADJ}}", str(adjudications)) \
                .replace("{{CHAIN}}", chain).replace("{{CHAIN_CLS}}", chain_cls)


_PAGE = r"""<meta charset="utf-8"><title>Corpus</title>
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
.wrap{max-width:900px;margin:0 auto}
h1{font:600 20px/1.3 var(--sans);margin:0 0 4px}
h2{font:600 15px/1.3 var(--sans);margin:28px 0 8px}
.sub{color:var(--mut);font-size:13px;margin:0 0 16px;max-width:72ch}
table{border-collapse:collapse;width:100%;font-size:13.5px}
th,td{text-align:left;padding:7px 12px 7px 0;border-bottom:1px solid var(--rule);
 vertical-align:top}
th{font-size:11px;text-transform:uppercase;letter-spacing:.06em;color:var(--mut)}
.mono{font-family:var(--mono)} .num{text-align:right;font-variant-numeric:tabular-nums}
.hash{font-size:11px;color:var(--mut);word-break:break-all}
.state{padding:10px 14px;border-radius:7px;font-size:13.5px;margin:0 0 8px}
.state.ok{background:var(--okbg);color:var(--ok)}
.state.warn{background:var(--warnbg);color:var(--warn)}
ul{margin:6px 0 0;padding-left:20px} li{margin:5px 0;font-size:13.5px}
code{font:.87em var(--mono);background:var(--bg);padding:1px 5px;border-radius:3px}
.why{margin-top:26px;padding:14px 18px;border-left:3px solid var(--accent);
 background:var(--panel);border-radius:0 7px 7px 0;font-size:13px;color:var(--mut);
 max-width:74ch}
.why b{color:var(--ink)}
.why code{background:var(--bg)}
</style>
<div class="wrap">
  <h1>Corpus — {{N}} document(s)</h1>
  <p class="sub">A corpus is not only its documents; it is its documents plus everything
  fitted to them. Both are shown, because the second is what decides whether findings here
  can be trusted.</p>

  <h2>Documents</h2>
  <p class="sub">Re-hashing a file and comparing it here verifies, without this tool, that
  the text examined is the text you hold.</p>
  <table><thead><tr><th>Document</th><th class="num">Characters</th>
   <th>SHA-256 at ingest</th></tr></thead><tbody>{{DOCS}}</tbody></table>

  <h2>Support floor</h2>
  <p class="state {{CAL_CLS}}">{{CAL}}</p>

  <h2>Constants not yet exercised on this corpus</h2>
  <p class="sub">Corpus-scoped values that this corpus has not tested either way. Inert is
  not validated — a constant no observation exercised has not been shown to transfer.</p>
  <ul>{{UNTESTED}}</ul>

  <h2>Drawings and judgments</h2>
  <p class="sub">{{SHEETS}}</p>
  <p class="state {{CHAIN_CLS}}">{{ADJ}} reviewer judgment(s) in force · hash chain {{CHAIN}}</p>

  <div class="why">
    <p><b>There is no “add document” button here, on purpose.</b> Ingesting or removing a
    document invalidates three things at once: the support floor was fitted to <i>these</i>
    documents and a relevance score does not survive the corpus changing; every citation
    already in the audit log resolves against offsets in a specific document version, and
    replay is a claim about <i>that</i> corpus; and the corpus is read-only to the agent by
    construction, so a corpus-write endpoint on a listener is a different security posture
    than this server was argued for.</p>
    <p>None of that makes ingestion wrong — it makes it deliberate. It stays a considered
    act: <code>scripts/ingest_files.py</code>, then re-calibrate, then rebuild.</p>
  </div>
</div>
"""
