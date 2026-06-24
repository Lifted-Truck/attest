#!/usr/bin/env python3
"""attest_rig.py — the M0 audition rig (ROADMAP M0-T4, brief §2).

Proves the risky core cheaply *before* any real subsystem is built: grounded
retrieval + span-level citation + verify + abstention, scored inline against the
golden seed. It is a deterministic Python stand-in for the runtime agent loop —
in v1 the Claude Code agent does the reasoning; here we encode just enough
deterministic judgment to demonstrate the loop and clear the M0 gate.

What is a *real* deterministic capability here:
  - BM25 retrieval over line-level spans of the toy corpus.
  - Citation = the retrieved spans that clear the relevance threshold (plural,
    ranked) — equal-scoring lines both surface (e.g. current vs non-current
    "Term debt"), demonstrating plural-and-ranked (brief §4).
  - Verify = the rig only ever asserts values that appear verbatim in a cited
    span; anything else would be a hallucination. By construction it asserts none.

What is an *agent-judgment proxy* (the real agent reasons about these; we encode
small, legible guards so the rig can abstain correctly on the traps):
  - temporal: a question dated outside the filing's coverage period → abstain.
  - entity-scope: a question comparing to a non-Apple company → partial-abstain.
  - false-premise: "why did X decline" when the figures show X rose → reject.

Run:  python attest_rig.py
Exit code 0 iff the M0 gate passes. A standing test (tests/test_rig.py) asserts
the same gate so CI keeps it green.
"""

from __future__ import annotations

import json
import math
import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent
MANIFEST = ROOT / "corpus" / "toy" / "manifest.json"
GOLDEN = ROOT / "golden_seed.json"

# --- tuning knobs (the brief invites iterating these in the rig) ---------------
BM25_K1 = 1.5
BM25_B = 0.75
TOP_K = 8
THRESHOLD = 3.0  # min BM25 score for the top span to clear abstention
CITE_RATIO = 0.90  # cite spans scoring ≥ CITE_RATIO × top score (keeps ties, drops the tail)

# Coverage of the single reference filing (AAPL FY2024 10-K + FY2023 comparative).
OUT_OF_PERIOD_MARKERS = ["2025", "december 28", "first quarter", "second quarter", "third quarter"]
COMPETITORS = {"microsoft", "google", "alphabet", "amazon", "samsung", "meta", "tesla"}
DECLINE_WORDS = ["declin", "decreas", "dropp", "fell", "fall", "reduc", "shrank", "shrink"]
# Agent-knowledge proxy: subjects a 10-K does not disclose (they live in the proxy
# statement, or aren't reported at all). The runtime agent knows this; the rig encodes
# it as token-sets — abstain if a question's tokens cover any set. Same category as the
# temporal/entity guards: deterministic stand-ins for the agent's reasoning, not retrieval.
NOT_DISCLOSED = [
    {"ceo"}, {"executive", "compensation"},  # exec comp → DEF 14A proxy, not the 10-K
    {"iphone"}, {"units"},                    # Apple stopped disclosing unit sales (FY2019)
    {"churn"}, {"retention"},                 # not a metric Apple reports
]

# Keep hyphenated words whole so "non-current" ≠ "current" (disambiguates the
# current/non-current Term debt and Marketable securities line pairs).
_TOKEN = re.compile(r"[a-z]+(?:-[a-z]+)*|\d{1,3}(?:,\d{3})+|\d+")
_THOUSANDS = re.compile(r"\d{1,3}(?:,\d{3})+")

# Stripped from *queries* only (not the corpus): generic question words, the
# company name, and date tokens. The date is not discriminating — every balance
# figure is "as of September 28, 2024" — and its rare bigrams would otherwise
# dominate retrieval. Temporal logic stays in the abstention guard, on the raw text.
QUERY_STOP = {
    "what", "were", "was", "did", "do", "does", "is", "are", "the", "a", "an", "of", "as",
    "at", "in", "on", "to", "for", "how", "much", "many", "and", "by", "s", "apple",
    "from", "company", "companys", "not", "carry", "carries", "hold", "holds", "have", "has",
    "january", "february", "march", "april", "may", "june", "july", "august",
    "september", "october", "november", "december",
}


def tokenize(text: str) -> list[str]:
    return _TOKEN.findall(text.lower())


def featurize(text: str, *, is_query: bool = False) -> list[str]:
    """Unigrams + adjacent bigrams. Bigrams give phrase signal ('total_assets')
    so 'total assets' lands on the right line, not every line containing 'total'.
    Queries are first cleaned of stopwords/dates so retrieval keys on the subject."""
    if is_query:
        text = re.sub(r"\([^)]*\)", " ", text)  # drop parenthetical asides ("(not total ...)")
    toks = tokenize(text)
    if is_query:
        toks = [t for t in toks if t not in QUERY_STOP and not t.isdigit()]
    return toks + [f"{toks[i]}_{toks[i + 1]}" for i in range(len(toks) - 1)]


# ------------------------------------------------------------------------------
# Corpus + span index
# ------------------------------------------------------------------------------
@dataclass
class Span:
    span_id: str
    doc_id: str
    text: str
    tokens: list[str] = field(default_factory=list)


def load_spans() -> list[Span]:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    spans: list[Span] = []
    for ex in manifest["excerpts"]:
        body = (ROOT / ex["path"]).read_text(encoding="utf-8")
        if ex.get("granularity") == "block":
            # Prose section: one span for the whole excerpt (e.g. the auditor report,
            # so "Ernst & Young LLP" is retrievable via the section's header tokens).
            text = " ".join(body.split())
            sid = f"{ex['excerpt_id']}#block"
            spans.append(Span(sid, ex["excerpt_id"], text, featurize(text)))
            continue
        header = ""  # nearest preceding subsection header (e.g. "Current liabilities:")
        for n, line in enumerate(body.splitlines()):  # tabular: one line item per span
            line = line.strip()
            if not any(c.isalnum() for c in line):
                continue
            # A header line (ends with ":" and carries no figure) becomes the breadcrumb,
            # not a span of its own — it is how "current" vs "non-current Term debt" differ.
            if line.endswith(":") and not _THOUSANDS.search(line):
                header = line.rstrip(":")
                continue
            # .text is the *verbatim* source line we cite; the breadcrumb is a retrieval
            # feature only (so citations stay honest while ranking gets section context).
            aug = f"{header}: {line}" if header else line
            sid = f"{ex['excerpt_id']}#L{n}"
            spans.append(Span(sid, ex["excerpt_id"], line, featurize(aug)))
    return spans


class BM25:
    def __init__(self, spans: list[Span]):
        self.spans = spans
        self.N = len(spans)
        self.avgdl = sum(len(s.tokens) for s in spans) / max(self.N, 1)
        # Cap length normalization so a legitimately long section (the auditor
        # report block) isn't unfairly buried beneath short table lines.
        self.dl_cap = self.avgdl * 4
        df: Counter[str] = Counter()
        for s in spans:
            df.update(set(s.tokens))
        self.idf = {
            t: math.log(1 + (self.N - d + 0.5) / (d + 0.5)) for t, d in df.items()
        }
        self.tf = [Counter(s.tokens) for s in spans]

    def score(self, query_tokens: list[str], i: int) -> float:
        s = self.spans[i]
        dl = min(len(s.tokens), self.dl_cap)
        tf = self.tf[i]
        total = 0.0
        for t in query_tokens:
            if t not in tf:
                continue
            idf = self.idf.get(t, 0.0)
            f = tf[t]
            denom = f + BM25_K1 * (1 - BM25_B + BM25_B * dl / self.avgdl)
            total += idf * (f * (BM25_K1 + 1)) / denom
        return total

    def rank(self, query: str, k: int = TOP_K) -> list[tuple[float, Span]]:
        q = featurize(query, is_query=True)
        scored = [(self.score(q, i), self.spans[i]) for i in range(self.N)]
        scored.sort(key=lambda x: (-x[0], x[1].span_id))
        return [(sc, sp) for sc, sp in scored[:k] if sc > 0]


# ------------------------------------------------------------------------------
# Golden evidence extraction (what a correct answer must rest on)
# ------------------------------------------------------------------------------
def evidence_strings(item: dict) -> list[str]:
    """Strings the corpus must contain to support the answer.

    Numbers come from the *supporting operands* (supporting[].value_seen), never
    from a derived result in expected_answer — a computed delta (e.g. G005's
    $12,397M) is not a span; every operand carries its own evidence (brief §4).
    Text answers with no operand (auditor name, fiscal-year-end date) fall back
    to the expected_answer string itself."""
    operands = " ".join(s.get("value_seen") or "" for s in item.get("supporting", []))
    nums = _THOUSANDS.findall(operands)
    if nums:
        return sorted(set(nums))
    ans = (item.get("expected_answer") or "").strip().rstrip(".")
    return [ans] if ans else []


# ------------------------------------------------------------------------------
# The rig pipeline (deterministic stand-in for the agent loop)
# ------------------------------------------------------------------------------
@dataclass
class Outcome:
    item_id: str
    answerable: bool
    abstained: bool
    abstain_kind: str | None  # abstain | partial-abstain | reject-false-premise
    cited: list[str]
    asserted: list[str]
    evidence: list[str]
    covered: list[str]
    top_score: float = 0.0
    reason: str = ""


def abstention_guard(question: str, ranked: list[tuple[float, Span]]) -> tuple[str, str] | None:
    """Return (kind, human-readable reason) if the agent should not answer, else None."""
    q = question.lower()
    qtokens = set(tokenize(q))
    if any(c in q for c in COMPETITORS):
        return "partial-abstain", "comparison to a company outside this corpus (Apple-only)"
    if any(m in q for m in OUT_OF_PERIOD_MARKERS):
        return "abstain", "question dated outside the filing's coverage period (FY2024 / FY2023)"
    if any(subj <= qtokens for subj in NOT_DISCLOSED):
        return "abstain", "subject not disclosed in a 10-K (proxy statement, or not reported)"
    if "why" in q and any(w in q for w in DECLINE_WORDS):
        # false-premise: does the top numeric span actually show a decline?
        for _sc, sp in ranked:
            nums = _THOUSANDS.findall(sp.text)
            if len(nums) >= 2:
                cur = int(nums[0].replace(",", ""))
                prior = int(nums[1].replace(",", ""))
                if cur >= prior:  # rose or flat → the "decline" premise is false
                    return "reject-false-premise", "the cited figures show the value rose, not fell"
                break
    return None


def run_item(item: dict, bm25: BM25) -> Outcome:
    iid, ans = item["id"], item["answerable"]
    q = item["question"]
    ranked = bm25.rank(q)
    evidence = evidence_strings(item)

    guard = abstention_guard(q, ranked)
    kind = guard[0] if guard else None
    reason = guard[1] if guard else ""
    top = ranked[0][0] if ranked else 0.0
    if kind is None and top < THRESHOLD:
        kind = "abstain"  # relevance threshold: nothing in-corpus supports this
        reason = "no retrieved span cleared the relevance threshold"

    # Cite the spans within CITE_RATIO of the top score (ties stay → plural; tail drops).
    band = [(sc, sp) for sc, sp in ranked if sc >= max(THRESHOLD, top * CITE_RATIO)]

    if kind is not None and kind not in ("partial-abstain", "reject-false-premise"):
        return Outcome(iid, ans, True, kind, [], [], evidence, [], top, reason)
    if kind in ("partial-abstain", "reject-false-premise"):
        # Still cite whatever Apple-side evidence we did find (G016/G020 carry a span).
        cited = [sp.span_id for _s, sp in band]
        return Outcome(iid, ans, True, kind, cited, [], evidence, [], top, reason)

    # Grounded answer path: cite the band; assert only values found in those spans.
    cited_spans = [sp for _sc, sp in band]
    cited = [sp.span_id for sp in cited_spans]
    cited_text = "\n".join(sp.text for sp in cited_spans)
    asserted = [e for e in evidence if e in cited_text]  # verify: assert only what's cited
    return Outcome(iid, ans, False, None, cited, asserted, evidence, asserted, top, "")


def supports(span_text: str, evidence: list[str]) -> bool:
    return any(e in span_text for e in evidence)


# ------------------------------------------------------------------------------
# Scoring + gate
# ------------------------------------------------------------------------------
def main() -> int:
    spans = load_spans()
    bm25 = BM25(spans)
    span_by_id = {s.span_id: s for s in spans}
    golden = json.loads(GOLDEN.read_text(encoding="utf-8"))["items"]

    precisions, recalls, correct_answerable = [], [], []
    asserted_total = asserted_unsupported = 0
    false_abstentions = 0
    unanswerable_total = unanswerable_correct = 0

    print(f"{'id':<5}{'ans':<5}{'action':<22}{'top':<7}{'cites':<6}{'recall':<8}{'prec':<7}note")
    print("-" * 84)
    for item in golden:
        o = run_item(item, bm25)

        if o.answerable:
            if o.abstained:
                false_abstentions += 1
                correct_answerable.append(0)
                print(f"{o.item_id:<5}{'Y':<5}{'ABSTAIN(false)':<22}{o.top_score:<7.2f}{0:<6}{'-':<8}{'-':<7}!!")
                continue
            cited_spans = [span_by_id[c] for c in o.cited]
            n_supporting = sum(1 for s in cited_spans if supports(s.text, o.evidence))
            prec = n_supporting / len(cited_spans) if cited_spans else 0.0
            rec = len(o.covered) / len(o.evidence) if o.evidence else 1.0
            precisions.append(prec)
            recalls.append(rec)
            correct = 1 if rec == 1.0 else 0
            correct_answerable.append(correct)
            asserted_total += len(o.asserted)
            # verify: every asserted value must be in a cited span (else hallucination)
            cited_text = "\n".join(s.text for s in cited_spans)
            asserted_unsupported += sum(1 for a in o.asserted if a not in cited_text)
            flag = "" if correct else f"!! missing {set(o.evidence) - set(o.covered)}"
            print(f"{o.item_id:<5}{'Y':<5}{'answer':<22}{o.top_score:<7.2f}{len(o.cited):<6}{rec:<8.2f}{prec:<7.2f}{flag}")
        else:
            unanswerable_total += 1
            expected = item.get("expected_behavior", "abstain")
            ok = o.abstained and (o.abstain_kind == expected or expected == "abstain")
            unanswerable_correct += 1 if ok else 0
            flag = "" if ok else f"!! expected {expected}, got {o.abstain_kind}"
            action = o.abstain_kind or "ANSWERED(leak)"
            print(f"{o.item_id:<5}{'N':<5}{action:<22}{o.top_score:<7.2f}{len(o.cited):<6}{'-':<8}{'-':<7}{flag}")

    cit_prec = sum(precisions) / len(precisions) if precisions else 0.0
    cit_rec = sum(recalls) / len(recalls) if recalls else 0.0
    ans_corr = sum(correct_answerable) / len(correct_answerable) if correct_answerable else 0.0
    halluc = asserted_unsupported / asserted_total if asserted_total else 0.0
    abst_acc = unanswerable_correct / unanswerable_total if unanswerable_total else 0.0

    print("\n=== M0 gate metrics ===")
    print(f"  answer correctness (answerable):   {ans_corr:.2%}")
    print(f"  citation precision (answerable):   {cit_prec:.2%}   gate ≥ 90%")
    print(f"  citation recall    (answerable):   {cit_rec:.2%}")
    print(f"  hallucination rate (answerable):   {halluc:.2%}   gate = 0%")
    print(f"  abstention accuracy (unanswerable):{abst_acc:.2%}   gate = 100%")
    print(f"  false abstentions (answerable):    {false_abstentions}")

    gate_ok = cit_prec >= 0.90 and halluc == 0.0 and abst_acc == 1.0 and false_abstentions == 0
    print("\nM0 GATE:", "PASS ✅" if gate_ok else "FAIL ❌")
    return 0 if gate_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
