#!/usr/bin/env python3
"""
Linguistic term-frequency analysis across corpus + external references.

Tracks the prevalence of key ML/AI terms in paper titles over time,
using both the corpus (N≈5k) and the external references it cites (N≈86k).

Usage:
    python3 analysis/linguistic_terms.py
"""
from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
DATA = BASE / "scopus_out7"
CACHE_DIR = DATA / "openalex_cache"


# ── data loading ─────────────────────────────────────────────────────────
def load_corpus_titles() -> list[dict]:
    """Return [{title, year, source='corpus'}]."""
    rows = []
    with open(DATA / "raw_scopus_all.jsonl") as f:
        for line in f:
            d = json.loads(line)
            e = d["entry"]
            title = (e.get("dc:title") or "").strip()
            year = d.get("year")
            if title and year:
                rows.append(dict(title=title, year=int(year), source="corpus"))
    return rows


def load_external_titles() -> list[dict]:
    """Return [{title, year, source='external'}]."""
    path = CACHE_DIR / "ref_metadata_full.json"
    if not path.exists():
        print(f"  ERROR: run fetch_ref_titles.py first")
        return []
    with open(path) as f:
        meta = json.load(f)
    rows = []
    for oa_id, info in meta.items():
        title = (info.get("title") or "").strip()
        year = info.get("year")
        if title and year and isinstance(year, int):
            rows.append(dict(title=title, year=year, source="external"))
    return rows


# ── term matching ────────────────────────────────────────────────────────
# Terms to track: single words and multi-word phrases
TERMS = {
    # broad
    "learning":             r"\blearning\b",
    "neural":               r"\bneural\b",
    # specific methods
    "machine learning":     r"\bmachine\s+learning\b",
    "deep learning":        r"\bdeep\s+learning\b",
    "reinforcement learning": r"\breinforcement\s+learning\b",
    "transfer learning":    r"\btransfer\s+learning\b",
    "neural network":       r"\bneural\s+network",
    "convolutional":        r"\bconvolutional\b",
    "recurrent":            r"\brecurrent\b",
    "GAN / adversarial":    r"\b(gan|adversarial)\b",
    "transformer":          r"\btransformer\b",
    "graph neural":         r"\bgraph\s+neural\b",
    "LLM / language model": r"\b(llm|large\s+language\s+model|language\s+model)\b",
    "bayesian":             r"\bbayesian\b",
    "optimization":         r"\boptimiz",
    "automat(ed/ic)":       r"\bautomat",
}


def match_terms(title: str) -> list[str]:
    t = title.lower()
    return [name for name, pat in TERMS.items() if re.search(pat, t)]


# ── analysis ─────────────────────────────────────────────────────────────
def analyze(rows: list[dict], label: str, year_range: tuple[int, int] = (1980, 2025)):
    ymin, ymax = year_range
    filtered = [r for r in rows if ymin <= r["year"] <= ymax]
    print(f"\n{'='*75}")
    print(f"  Linguistic Term Analysis — {label}")
    print(f"  Papers with titles in {ymin}–{ymax}: {len(filtered):,}")
    print(f"{'='*75}")

    # count papers per year
    papers_by_year: dict[int, int] = defaultdict(int)
    for r in filtered:
        papers_by_year[r["year"]] += 1

    # count term hits per year
    term_by_year: dict[str, dict[int, int]] = {t: defaultdict(int) for t in TERMS}
    term_total: dict[str, int] = defaultdict(int)
    for r in filtered:
        hits = match_terms(r["title"])
        for t in hits:
            term_by_year[t][r["year"]] += 1
            term_total[t] += 1

    years = list(range(ymin, ymax + 1))
    active_years = [y for y in years if papers_by_year[y] > 0]

    # ── overall term prevalence ──
    print(f"\n  Overall term prevalence (% of titles containing term):")
    n = len(filtered)
    for term in TERMS:
        pct = 100 * term_total[term] / n if n else 0
        bar = "█" * int(pct * 2)
        print(f"    {term:<24s}  {term_total[term]:6,}  ({pct:5.2f}%)  {bar}")

    # ── yearly trend table for key terms ──
    key_terms = ["learning", "neural", "machine learning", "deep learning",
                 "reinforcement learning", "neural network", "GAN / adversarial",
                 "transformer", "graph neural", "LLM / language model"]

    # Show 5-year bins for readability
    bins = []
    for start in range(ymin, ymax + 1, 5):
        end = min(start + 4, ymax)
        bins.append((start, end))

    print(f"\n  Term frequency by 5-year period (% of titles in that period):")
    hdr = f"  {'Term':<24s}"
    for s, e in bins:
        hdr += f"  {s}-{str(e)[-2:]:>2s}"
    print(hdr)
    print("  " + "-" * (len(hdr) - 2))

    for term in key_terms:
        row = f"  {term:<24s}"
        for s, e in bins:
            n_papers = sum(papers_by_year[y] for y in range(s, e + 1))
            n_hits = sum(term_by_year[term][y] for y in range(s, e + 1))
            pct = 100 * n_hits / n_papers if n_papers else 0
            row += f"  {pct:6.2f}"
        print(row)

    # ── annual detail for recent years (2015-2025) ──
    print(f"\n  Annual detail (2015–2025), % of titles:")
    recent = list(range(2015, 2026))
    hdr2 = f"  {'Term':<24s}"
    for y in recent:
        hdr2 += f" {str(y)[-2:]:>5s}"
    print(hdr2)
    print("  " + "-" * (len(hdr2) - 2))

    for term in key_terms:
        row = f"  {term:<24s}"
        for y in recent:
            n_p = papers_by_year[y]
            n_h = term_by_year[term][y]
            pct = 100 * n_h / n_p if n_p else 0
            row += f" {pct:5.1f}"
        print(row)

    # paper counts row
    row = f"  {'(N papers)':<24s}"
    for y in recent:
        row += f" {papers_by_year[y]:5,}"
    print(row)

    # ── first appearance ──
    print(f"\n  First year each term appears in a title:")
    for term in TERMS:
        yrs = [y for y in active_years if term_by_year[term][y] > 0]
        first = min(yrs) if yrs else "never"
        print(f"    {term:<24s}  {first}")

    print()


# ── main ─────────────────────────────────────────────────────────────────
def main():
    corpus = load_corpus_titles()
    external = load_external_titles()
    combined = corpus + external

    print(f"\n  Loaded: {len(corpus):,} corpus + {len(external):,} external = {len(combined):,} total")

    analyze(combined, "Combined (corpus + external references)")
    analyze(corpus, "Corpus only (N≈5k)")


if __name__ == "__main__":
    main()
