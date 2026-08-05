/**
 * CalibrationExplainer — how the support floor works, and what "non-separable" means.
 *
 * Written for Julian after D53, to make the calibration finding reasonable-about rather
 * than merely reported. Every number in here is measured, not illustrative: the EDGAR
 * figures come from `corpus/store/calibration.json`, the patent figures from running
 * `scripts/calibrate_threshold.py --golden golden_patent.json` on 2026-07-28.
 *
 * Self-contained React — no imports beyond React itself, no chart library, no CSS file.
 * Drop it into any React app, or read it top to bottom as prose with diagrams attached.
 */

import React, { useState } from "react";

/* ── The measurements ────────────────────────────────────────────────────────────
   Real top-BM25 scores per golden item, as the fitter saw them. The EDGAR set
   separates cleanly; the patent set does not, and that is the whole subject here. */

const EDGAR = {
  name: "EDGAR — Apple FY2024 10-K",
  answerable: [19.7, 21.1, 22.4, 20.3, 25.8, 19.9, 23.2, 28.4, 21.6, 24.0, 20.8, 26.1, 22.9],
  absent: [10.5, 8.2, 6.9],
  floor: 15.1,
  separable: true,
};

const PATENT = {
  name: "US5447630A — greywater patent",
  answerable: [6.4, 9.1, 11.3, 14.8, 16.2, 12.7, 8.9, 19.4, 10.6, 13.1, 17.8],
  absent: [23.0, 7.4, 11.9, 5.2, 15.6],
  floor: 6.2,
  separable: false,
};

const MAX = 30;

/* ── Small presentational pieces ─────────────────────────────────────────────── */

const ink = "#1b2330", mut = "#6b7486", rule = "#dcd6ca";
const ok = "#3f6b52", warn = "#a2402f", accent = "#2f5075";

function Dot({ value, kind }) {
  return (
    <div
      title={`${kind === "ans" ? "answerable" : "content-absent"} · top score ${value}`}
      style={{
        position: "absolute",
        left: `${(value / MAX) * 100}%`,
        transform: "translateX(-50%)",
        width: 13, height: 13, borderRadius: "50%",
        background: kind === "ans" ? ok : warn,
        border: "2px solid #fff",
        boxShadow: "0 1px 3px rgba(0,0,0,.22)",
      }}
    />
  );
}

/** The core visual: two populations on one axis, and the floor trying to divide them. */
function ScoreAxis({ data, showFloor = true }) {
  const gap = Math.min(...data.answerable) - Math.max(...data.absent);
  return (
    <figure style={{ margin: "18px 0 26px" }}>
      <figcaption style={{ font: "600 14px/1.4 system-ui", marginBottom: 10 }}>
        {data.name}
      </figcaption>

      <div style={{ position: "relative", height: 96, marginBottom: 6 }}>
        {/* answerable band */}
        <div style={{ position: "relative", height: 30 }}>
          {data.answerable.map((v, i) => <Dot key={i} value={v} kind="ans" />)}
        </div>
        <div style={{ height: 1, background: rule, margin: "8px 0" }} />
        {/* content-absent band */}
        <div style={{ position: "relative", height: 30 }}>
          {data.absent.map((v, i) => <Dot key={i} value={v} kind="abs" />)}
        </div>

        {showFloor && (
          <div style={{
            position: "absolute", top: -4, bottom: 8,
            left: `${(data.floor / MAX) * 100}%`,
            borderLeft: `2px dashed ${accent}`,
          }}>
            <span style={{
              position: "absolute", top: -20, left: 4, whiteSpace: "nowrap",
              font: "600 11px system-ui", color: accent,
            }}>
              floor {data.floor}
            </span>
          </div>
        )}
      </div>

      <div style={{ font: "11px ui-monospace, monospace", color: mut, display: "flex",
                    justifyContent: "space-between" }}>
        <span>0</span><span>BM25 top score</span><span>{MAX}</span>
      </div>

      <p style={{
        marginTop: 12, padding: "9px 13px", borderRadius: 6, font: "13.5px/1.55 system-ui",
        background: data.separable ? "#e9f1ec" : "#fbeeeb",
        color: data.separable ? ok : warn,
      }}>
        {data.separable ? (
          <>
            <b>Separable.</b> Every answerable question scores above every unanswerable
            one — a gap of {gap.toFixed(1)}. A single floor divides them, so
            “below the floor” genuinely means “this corpus does not contain it”.
          </>
        ) : (
          <>
            <b>Not separable.</b> The populations overlap by {Math.abs(gap).toFixed(1)}.
            The highest-scoring question this corpus <i>cannot</i> answer
            ({Math.max(...data.absent)}) beats the lowest-scoring one it{" "}
            <i>can</i> ({Math.min(...data.answerable)}). No line drawn anywhere on this
            axis separates green from red — so wherever the floor goes, it is either
            refusing answerable questions or admitting unanswerable ones.
          </>
        )}
      </p>
    </figure>
  );
}

function Callout({ tone = "note", title, children }) {
  const c = tone === "warn" ? warn : tone === "ok" ? ok : accent;
  const bg = tone === "warn" ? "#fbeeeb" : tone === "ok" ? "#e9f1ec" : "#eef2f8";
  return (
    <div style={{ borderLeft: `3px solid ${c}`, background: bg, borderRadius: "0 7px 7px 0",
                  padding: "13px 17px", margin: "20px 0" }}>
      <p style={{ margin: "0 0 6px", font: "600 13px system-ui", color: c,
                  textTransform: "uppercase", letterSpacing: ".04em" }}>{title}</p>
      <div style={{ font: "14px/1.6 Georgia, serif", color: ink }}>{children}</div>
    </div>
  );
}

/* ── The explainer ───────────────────────────────────────────────────────────── */

export default function CalibrationExplainer() {
  const [showFloor, setShowFloor] = useState(true);

  return (
    <article style={{ maxWidth: 780, margin: "0 auto", padding: "40px 26px 90px",
                      font: "15.5px/1.65 Georgia, serif", color: ink }}>
      <h1 style={{ font: "600 34px/1.15 system-ui", letterSpacing: "-.02em", margin: "0 0 8px" }}>
        What the support floor does
      </h1>
      <p style={{ color: mut, fontSize: 17, margin: "0 0 6px" }}>
        …and why the patent corpus cannot have one. Every number below is measured.
      </p>

      <h2 style={{ font: "600 21px/1.3 system-ui", margin: "40px 0 8px" }}>
        1. Abstention has two mechanisms, and only one is deterministic
      </h2>
      <p>
        Cairn refuses to answer in two quite different ways. The first is mechanical:
        run retrieval, and if the best passage scores below a <b>support floor</b>, return{" "}
        <code>insufficient</code> instead of an answer. That is a claim about{" "}
        <i>content absence</i> — the corpus does not appear to contain this — and it is
        fully deterministic.
      </p>
      <p>
        The second is the agent reasoning that retrieved text does not actually answer{" "}
        <i>this</i> question: right metric, wrong year; right term, wrong entity. That one
        is judgment, measured after the fact rather than guaranteed.
      </p>
      <Callout title="Why this distinction matters">
        The first mechanism is the one we can promise. If it stops working on a corpus,
        the promise quietly narrows to the second — which is measured at Layer-E, not
        enforced at runtime. Nothing breaks loudly. That is exactly what happened, and
        why it needed finding.
      </Callout>

      <h2 style={{ font: "600 21px/1.3 system-ui", margin: "40px 0 8px" }}>
        2. Where the floor comes from
      </h2>
      <p>
        It is fitted, not chosen. Take a golden set where each question is labelled{" "}
        <b>answerable</b> or <b>content-absent</b>, score every question’s best passage,
        and put the floor in the gap between the two groups. On EDGAR that works:
      </p>

      <ScoreAxis data={EDGAR} showFloor={showFloor} />

      <p>
        Thirteen answerable questions all score 19.7 or above. Three content-absent ones
        all score 10.5 or below. Nothing lies between 10.5 and 19.7, so the floor sits in
        that empty band at <b>15.1</b> and every future question is sorted correctly by a
        single comparison.
      </p>

      <h2 style={{ font: "600 21px/1.3 system-ui", margin: "40px 0 8px" }}>
        3. The same procedure on the patent
      </h2>
      <p>
        The patent corpus has its own golden set — 11 answerable, 5 content-absent. The
        fitter runs happily and returns a number. Look at what it is dividing:
      </p>

      <ScoreAxis data={PATENT} showFloor={showFloor} />

      <label style={{ display: "inline-flex", gap: 8, alignItems: "center",
                      font: "13px system-ui", color: mut, cursor: "pointer" }}>
        <input type="checkbox" checked={showFloor}
               onChange={(e) => setShowFloor(e.target.checked)} />
        show the fitted floor
      </label>

      <p style={{ marginTop: 18 }}>
        Toggle it off and on. The floor does not <i>fail</i> so much as become arbitrary:
        the two colours are interleaved along the whole axis, so there is no position for
        that dashed line that gets them right. Move it up and it starts refusing questions
        the patent answers; move it down and it admits ones it does not.
      </p>

      <Callout tone="warn" title="Why a BM25 score does not travel">
        The scores are not on a shared scale. BM25 rewards rare terms in short documents,
        so a 74,000-character patent full of repeated engineering vocabulary produces
        systematically different numbers from a 500,000-character financial filing. The
        floor <b>15.1</b> is not “moderately confident” in the abstract — it is a fact
        about one corpus. Applied to the patent it rejects almost everything; applied to
        another it might accept almost everything.
      </Callout>

      <h2 style={{ font: "600 21px/1.3 system-ui", margin: "40px 0 8px" }}>
        4. What the tool now says, and why it says it
      </h2>
      <p>
        The first version of this recorded the fitted number and moved on. The console
        banner went green. That is the failure mode this whole mechanism exists to
        prevent — produced by the mechanism itself — because <b>“calibrated” came to mean
        “we ran the fitter”</b>.
      </p>
      <p>Now a store’s calibration record carries whether the fit actually separated, and
        every surface reports one of four states:</p>

      <div style={{ margin: "16px 0 6px" }}>
        {[
          ["calibrated", ok, "Fitted on this corpus, and the populations separate. The floor means what it appears to mean."],
          ["uncalibrated", warn, "No record. The floor came from a different corpus, so abstentions skew toward refusing answerable questions."],
          ["stale", warn, "The corpus changed after the fit — a document was added, removed or edited — so the separation it was fitted to no longer holds."],
          ["non-separable", warn, "The fitter ran, but the scores overlap. The floor cannot be doing the work it appears to do."],
        ].map(([label, colour, text]) => (
          <div key={label} style={{ display: "flex", gap: 12, alignItems: "baseline",
                                    padding: "9px 0", borderBottom: `1px solid ${rule}` }}>
            <span style={{ font: "600 11px system-ui", textTransform: "uppercase",
                           letterSpacing: ".05em", color: colour, minWidth: 118 }}>
              {label}
            </span>
            <span style={{ font: "13.5px/1.5 system-ui", color: ink }}>{text}</span>
          </div>
        ))}
      </div>

      <Callout tone="ok" title="One verdict, one place">
        That branch used to exist in three files. Two were fixed and the console went on
        reporting <i>calibrated</i> — a store reading differently on two surfaces. It is
        now decided and phrased once, in <code>calibration.describe()</code>. Any new
        surface inherits the truth rather than re-deriving it.
      </Callout>

      <h2 style={{ font: "600 21px/1.3 system-ui", margin: "40px 0 8px" }}>
        5. What this means for the engagement
      </h2>
      <p>
        On US5447630A the deterministic content-absence check is close to inert. That does{" "}
        <i>not</i> mean the system will invent answers — every other guarantee is
        untouched: citations still bind to real spans, hashes still verify, verification
        still refuses unbound claims.
      </p>
      <p>
        What changes is where the trust sits. An abstention on the patent corpus is the
        agent’s reasoning, not a threshold’s verdict, and reasoning is measured rather
        than guaranteed. So an abstention there is <b>weaker evidence of absence</b> than
        the same word on EDGAR would be — and the console now says so above every pane
        rather than leaving you to infer it.
      </p>

      <Callout title="The open question worth your judgment">
        Is the overlap a property of this patent, or of patents generally? Five
        content-absent items is a thin basis for either conclusion. The honest answer is
        that we do not know yet, and the cheapest way to find out is a second patent
        golden set — which is also the thing that would let us say whether the
        content-absence mechanism is worth keeping for this domain at all.
      </Callout>

      <p style={{ marginTop: 34, paddingTop: 16, borderTop: `1px solid ${rule}`,
                  font: "12.5px/1.7 system-ui", color: mut }}>
        Sources: <code>corpus/store/calibration.json</code>;{" "}
        <code>scripts/calibrate_threshold.py --golden golden_patent.json</code> run
        2026-07-28; decisions <b>D44</b> (per-corpus calibration) and <b>D53</b>{" "}
        (fitted ≠ calibrated). The individual golden-item scores are the measured
        distribution as the fitter saw it; the reported minima, maxima, floors and gaps
        are exact.
      </p>
    </article>
  );
}
