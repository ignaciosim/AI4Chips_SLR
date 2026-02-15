#!/usr/bin/env python3
"""
Reference-recency analysis via OpenAlex.

For every paper in the corpus, computes the age of each reference
(citing_year − cited_year) and reports:
  - overall reference-age distribution and median / half-life
  - reference-age trend over publication years
  - reference-age by lifecycle stage
  - fraction of "recent" (≤5 yr) vs "classic" (>10 yr) references over time

Requires the OpenAlex corpus cache produced by citation_network.py.

Usage:
    python3 analysis/citation_recency.py                  # full corpus
    python3 analysis/citation_recency.py --ai4chips       # ai4chips only
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.parse
import urllib.request
from collections import defaultdict
from pathlib import Path

import numpy as np

BASE = Path(__file__).resolve().parent.parent
DATA = BASE / "scopus_out7"
CACHE_DIR = DATA / "openalex_cache"

AI4CHIPS_JSON = DATA / "final_ai4chips_high_only.json"
FULL_JSONL = DATA / "raw_scopus_all.jsonl"

MAILTO = "slr-pipeline@example.com"
BATCH = 50
DELAY = 0.12


# ── data loading ─────────────────────────────────────────────────────────
def load_corpus(ai4chips: bool) -> dict[str, dict]:
    if ai4chips:
        with open(AI4CHIPS_JSON) as f:
            data = json.load(f)
        return {r["doi"].strip().lower(): dict(year=r["year"], stage=r.get("stage", ""),
                title=r.get("title", "")) for r in data if r.get("doi")}
    out = {}
    with open(FULL_JSONL) as f:
        for line in f:
            d = json.loads(line)
            e = d["entry"]
            doi = (e.get("prism:doi") or "").strip().lower()
            if doi:
                out[doi] = dict(year=d.get("year"), stage=d.get("stage", ""),
                                title=e.get("dc:title", ""))
    return out


def load_oa_cache(ai4chips: bool) -> dict[str, dict]:
    fname = "openalex_ai4chips.json" if ai4chips else "openalex_full.json"
    path = CACHE_DIR / fname
    if not path.exists():
        print(f"  ERROR: run citation_network.py first to create {path}", file=sys.stderr)
        sys.exit(1)
    with open(path) as f:
        return json.load(f)


# ── fetch publication years for external references ──────────────────────
def _fetch_years_batch(oa_ids: list[str]) -> dict[str, int]:
    """Fetch {openalex_id: publication_year} for a batch of IDs."""
    id_filter = "|".join(oa_ids)
    params = urllib.parse.urlencode({
        "filter": f"openalex_id:{id_filter}",
        "per_page": BATCH,
        "mailto": MAILTO,
        "select": "id,publication_year",
    })
    url = f"https://api.openalex.org/works?{params}"
    req = urllib.request.Request(url)
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read())
            return {r["id"]: r.get("publication_year") for r in data.get("results", [])
                    if r.get("publication_year")}
        except Exception as exc:
            if attempt == 3:
                return {}
            time.sleep(2 ** attempt)
    return {}


def fetch_ref_years(all_ref_ids: set[str], cache_file: Path) -> dict[str, int]:
    """Return {openalex_id: year} for all referenced works. Caches to disk."""
    if cache_file.exists():
        print(f"  Loading ref-years cache: {cache_file}")
        with open(cache_file) as f:
            return json.load(f)

    ids = sorted(all_ref_ids)
    batches = [ids[i:i + BATCH] for i in range(0, len(ids), BATCH)]
    print(f"  Fetching publication years for {len(ids):,} external refs ({len(batches):,} batches) …")

    result: dict[str, int] = {}
    for bi, batch in enumerate(batches):
        years = _fetch_years_batch(batch)
        result.update(years)
        if (bi + 1) % 100 == 0 or bi == len(batches) - 1:
            print(f"    {bi+1:,}/{len(batches):,} batches  ({len(result):,} resolved)")
        time.sleep(DELAY)

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    with open(cache_file, "w") as f:
        json.dump(result, f)
    print(f"  Cached to {cache_file}")
    return result


# ── analysis ─────────────────────────────────────────────────────────────
def compute_ages(
    corpus: dict[str, dict],
    oa_data: dict[str, dict],
    ref_years: dict[str, int],
) -> list[dict]:
    """Return list of {doi, year, stage, ref_id, ref_year, age} records."""
    # also build intra-corpus year map
    oaid_to_year: dict[str, int] = {}
    for doi, info in oa_data.items():
        if doi in corpus and corpus[doi].get("year"):
            oaid_to_year[info["openalex_id"]] = corpus[doi]["year"]

    records = []
    for doi, meta in corpus.items():
        info = oa_data.get(doi)
        if not info:
            continue
        pub_year = meta.get("year")
        if not pub_year:
            continue
        stage = meta.get("stage", "")
        for ref_id in info.get("referenced_oa_ids", []):
            ref_yr = ref_years.get(ref_id) or oaid_to_year.get(ref_id)
            if ref_yr and ref_yr <= pub_year:
                records.append(dict(
                    doi=doi, year=pub_year, stage=stage,
                    ref_id=ref_id, ref_year=ref_yr, age=pub_year - ref_yr,
                ))
    return records


def report(records: list[dict], corpus: dict[str, dict], oa_data: dict[str, dict], label: str):
    if not records:
        print("  No reference-age data.")
        return

    ages = np.array([r["age"] for r in records])
    years = sorted(set(r["year"] for r in records))

    print(f"\n{'='*65}")
    print(f"  Reference Recency Analysis — {label}")
    print(f"{'='*65}")
    n_papers = len(set(r["doi"] for r in records))
    print(f"  Papers with resolvable refs: {n_papers:,}")
    print(f"  Total reference-age pairs  : {len(records):,}")

    # ── overall distribution ──
    print(f"\n  Overall reference-age distribution:")
    print(f"    Mean   : {ages.mean():.1f} years")
    print(f"    Median : {np.median(ages):.1f} years")
    print(f"    Std    : {ages.std():.1f} years")
    p25, p75 = np.percentile(ages, [25, 75])
    print(f"    IQR    : {p25:.0f}–{p75:.0f} years")

    # half-life: age at which 50% of all refs are accounted for
    sorted_ages = np.sort(ages)
    cum = np.arange(1, len(sorted_ages) + 1) / len(sorted_ages)
    half_life = sorted_ages[np.searchsorted(cum, 0.5)]
    print(f"    Half-life (age at 50% cumulative refs): {half_life} years")

    # age brackets
    recent = np.sum(ages <= 5)
    mid = np.sum((ages > 5) & (ages <= 10))
    classic = np.sum(ages > 10)
    print(f"\n    ≤5 yr (recent)    : {recent:,}  ({100*recent/len(ages):.1f}%)")
    print(f"    6–10 yr (mid)     : {mid:,}  ({100*mid/len(ages):.1f}%)")
    print(f"    >10 yr (classic)  : {classic:,}  ({100*classic/len(ages):.1f}%)")

    # ── age histogram ──
    print(f"\n  Reference-age histogram (years → count):")
    bins = list(range(0, 41, 2)) + [100]
    hist, _ = np.histogram(ages, bins=bins)
    max_bar = max(hist)
    for i, count in enumerate(hist):
        lo = bins[i]
        hi = bins[i + 1]
        bar_len = int(40 * count / max_bar) if max_bar else 0
        lbl = f"{lo:2d}–{hi-1:2d}" if hi <= 40 else "40+ "
        print(f"    {lbl} yr : {'█' * bar_len} {count:,}")

    # ── trend: median age by publication year ──
    print(f"\n  Median reference age by publication year:")
    print(f"    {'Year':>4s}  {'Median':>6s}  {'Mean':>6s}  {'N refs':>7s}  {'≤5yr%':>5s}  {'Half-life':>9s}")
    by_year: dict[int, list[int]] = defaultdict(list)
    for r in records:
        by_year[r["year"]].append(r["age"])
    for yr in years:
        a = np.array(by_year[yr])
        sa = np.sort(a)
        c = np.arange(1, len(sa) + 1) / len(sa)
        hl = sa[np.searchsorted(c, 0.5)]
        rec_pct = 100 * np.sum(a <= 5) / len(a)
        print(f"    {yr:4d}  {np.median(a):6.1f}  {a.mean():6.1f}  {len(a):7,}  {rec_pct:5.1f}  {hl:9d}")

    # ── by lifecycle stage ──
    stages = sorted(set(r["stage"] for r in records if r["stage"]))
    if stages:
        print(f"\n  Reference age by lifecycle stage:")
        print(f"    {'Stage':<16s}  {'Median':>6s}  {'Mean':>6s}  {'≤5yr%':>5s}  {'N refs':>7s}")
        by_stage: dict[str, list[int]] = defaultdict(list)
        for r in records:
            if r["stage"]:
                by_stage[r["stage"]].append(r["age"])
        for st in stages:
            a = np.array(by_stage[st])
            rec_pct = 100 * np.sum(a <= 5) / len(a)
            print(f"    {st:<16s}  {np.median(a):6.1f}  {a.mean():6.1f}  {rec_pct:5.1f}  {len(a):7,}")

    # ── oldest and newest reference profiles ──
    # papers with highest median ref age
    paper_ages: dict[str, list[int]] = defaultdict(list)
    for r in records:
        paper_ages[r["doi"]].append(r["age"])

    print(f"\n  Papers citing the oldest references (top 10 by median age):")
    ranked = sorted(paper_ages.items(), key=lambda x: np.median(x[1]), reverse=True)
    for doi, a in ranked[:10]:
        m = corpus.get(doi, {})
        title = (m.get("title") or "")[:50]
        yr = m.get("year", "?")
        print(f"    median {np.median(a):5.1f} yr | {yr} | {title}  (N={len(a)})")

    print(f"\n  Papers citing only recent work (top 10, ≤5yr refs, min 10 refs):")
    ranked_rec = [(doi, a) for doi, a in paper_ages.items() if len(a) >= 10]
    ranked_rec.sort(key=lambda x: np.sum(np.array(x[1]) <= 5) / len(x[1]), reverse=True)
    for doi, a in ranked_rec[:10]:
        m = corpus.get(doi, {})
        title = (m.get("title") or "")[:50]
        yr = m.get("year", "?")
        pct = 100 * np.sum(np.array(a) <= 5) / len(a)
        print(f"    {pct:5.1f}% recent | {yr} | {title}  (N={len(a)})")

    print()


# ── main ─────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="Reference recency via OpenAlex")
    parser.add_argument("--ai4chips", action="store_true",
                        help="Analyse ai4chips set only")
    args = parser.parse_args()

    ai4chips = args.ai4chips
    label = "AI-for-chips" if ai4chips else "Full corpus"

    corpus = load_corpus(ai4chips)
    oa_data = load_oa_cache(ai4chips)
    print(f"\n  {label}: {len(corpus):,} papers")

    # collect all unique external ref IDs
    corpus_oa_ids = set(info["openalex_id"] for info in oa_data.values())
    all_ref_ids = set()
    for info in oa_data.values():
        all_ref_ids.update(info.get("referenced_oa_ids", []))
    external_ids = all_ref_ids - corpus_oa_ids
    print(f"  Unique external references: {len(external_ids):,}")

    cache_file = CACHE_DIR / ("ref_years_ai4chips.json" if ai4chips else "ref_years_full.json")
    ref_years = fetch_ref_years(external_ids, cache_file)

    records = compute_ages(corpus, oa_data, ref_years)
    report(records, corpus, oa_data, label)


if __name__ == "__main__":
    main()
