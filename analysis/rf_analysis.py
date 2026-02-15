"""RF / high-frequency presence analysis across the full SLR corpus.

Scans paper titles for RF-related keywords grouped into sub-categories,
then reports:
  1. Overall RF paper count and share of corpus
  2. Year-by-year trend table
  3. Breakdown by RF sub-category
  4. Top venues for RF papers
  5. Overlap with the ai4chips high-confidence set
  6. Sample titles (per sub-category)
"""

import os

_DEFAULT_DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scopus_out7")

import argparse
import csv
import json
import re
from collections import Counter, defaultdict

# ── RF keyword categories ─────────────────────────────────────────────────
# Each value is a list of (compiled_regex, label) tuples.
# Regexes use word boundaries; compiled with IGNORECASE where needed.

def _kw(pattern, flags=re.IGNORECASE):
    return re.compile(pattern, flags)

RF_CATEGORIES = {
    "Core RF/RFIC": [
        (_kw(r"\bRF\b"),                   "RF"),
        (_kw(r"\bradio.frequency\b"),      "radio frequency"),
        (_kw(r"\brfic\b"),                 "RFIC"),
        (_kw(r"\brf\s*circuit"),           "RF circuit"),
        (_kw(r"\brf\s*design"),            "RF design"),
        (_kw(r"\brf\s*ic\b"),              "RF IC"),
        (_kw(r"\brf\s*front.end"),         "RF front-end"),
    ],
    "mmWave / High-freq": [
        (_kw(r"\bmmwave\b"),               "mmWave"),
        (_kw(r"\bmm[\s-]?wave\b"),         "mm-wave"),
        (_kw(r"\bmillimeter[\s-]?wave\b"), "millimeter wave"),
        (_kw(r"\bmicrowave\b"),            "microwave"),
        (_kw(r"\b\d+\s*GHz\b"),            "GHz"),
        (_kw(r"\bTHz\b"),                  "THz"),
        (_kw(r"\bMM[\s-]?IC\b"),           "MMIC"),
        (_kw(r"\bMMIC\b"),                 "MMIC"),
    ],
    "RF building blocks": [
        (_kw(r"\bLNA\b"),                  "LNA"),
        (_kw(r"\blow[\s-]?noise\s*amplifier"), "low-noise amplifier"),
        (_kw(r"\bpower\s*amplifier\b"),    "power amplifier"),
        (_kw(r"\bVCO\b"),                  "VCO"),
        (_kw(r"\bmixer\b"),                "mixer"),
        (_kw(r"\bbalun\b"),                "balun"),
        (_kw(r"\bfrequency\s*synthesi"),   "frequency synthesizer"),
        (_kw(r"\bduplexer\b"),             "duplexer"),
        (_kw(r"\bsaw\s*filter\b"),         "SAW filter"),
    ],
    "Wireless / Comms": [
        (_kw(r"\bantenna\b"),              "antenna"),
        (_kw(r"\bbeam\s*form"),            "beamforming"),
        (_kw(r"\bphased[\s-]?array\b"),    "phased array"),
        (_kw(r"\b5G\b"),                   "5G"),
        (_kw(r"\b6G\b"),                   "6G"),
        (_kw(r"\btransceiver\b"),          "transceiver"),
        (_kw(r"\bMIMO\b"),                 "MIMO"),
        (_kw(r"\bradar\b"),                "radar"),
        (_kw(r"\bwireless\b"),             "wireless"),
    ],
}

# Flat list for any-match check
ALL_RF_PATTERNS = [
    (pat, label, cat)
    for cat, items in RF_CATEGORIES.items()
    for pat, label in items
]

# Venue normalization (same as plot_style.py)
VENUE_ALIASES = {"Integration the VLSI Journal": "Integration"}
SHORT_VENUE = {
    "IEEE Transactions on Computer Aided Design of Integrated Circuits and Systems":
        "IEEE TCAD",
    "ACM Transactions on Design Automation of Electronic Systems":
        "ACM TODAES",
    "IEEE Transactions on Semiconductor Manufacturing":
        "IEEE TSM",
    "Microelectronics Reliability":
        "Microelec. Reliability",
    "Microelectronics Journal":
        "Microelec. Journal",
    "IEEE Transactions on Very Large Scale Integration VLSI Systems":
        "IEEE TVLSI",
    "Integration":
        "Integration",
    "Journal of Industrial Information Integration":
        "J. Ind. Info. Integ.",
    "IEEE Design and Test":
        "IEEE D&T",
}


def short_venue(raw):
    v = VENUE_ALIASES.get(raw, raw)
    return SHORT_VENUE.get(v, v)


def classify_rf(title):
    """Return set of matched (category, label) tuples for a title."""
    matches = set()
    for pat, label, cat in ALL_RF_PATTERNS:
        if pat.search(title):
            matches.add((cat, label))
    return matches


def load_jsonl(jsonl_path):
    papers = []
    with open(jsonl_path, "r", encoding="utf-8") as f:
        for line in f:
            obj = json.loads(line)
            entry = obj.get("entry", {})
            papers.append({
                "doc_id": entry.get("eid", ""),
                "title": entry.get("dc:title", ""),
                "year": obj.get("year", 0),
                "venue": entry.get("prism:publicationName", ""),
                "cited_by": int(entry.get("citedby-count", 0) or 0),
            })
    return papers


def load_ai4chips_ids(csv_path):
    ids = set()
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        next(reader)
        for row in reader:
            doc_id = row[0].strip()
            if doc_id:
                ids.add(doc_id)
    return ids


def trend_label(counts_by_year, all_years):
    years_present = sorted(y for y in all_years if counts_by_year.get(y, 0) > 0)
    if not years_present:
        return "inactive"
    values = [counts_by_year.get(y, 0) for y in all_years]
    total = sum(values)
    if total <= 3:
        return "too few data points"
    peak_year = max(all_years, key=lambda y: counts_by_year.get(y, 0))
    peak_val = counts_by_year[peak_year]
    recent_years = all_years[-3:]
    recent_sum = sum(counts_by_year.get(y, 0) for y in recent_years)
    recent_share = recent_sum / total if total > 0 else 0
    last_val = counts_by_year.get(all_years[-1], 0)
    second_last_val = counts_by_year.get(all_years[-2], 0)
    if peak_year in all_years[-2:] and recent_share >= 0.5:
        return f"RISING (peak {peak_year})"
    if peak_year == all_years[-1]:
        return f"RISING (peak {peak_year})"
    if last_val >= peak_val * 0.8 and recent_share >= 0.4:
        return f"RISING (near peak, peak {peak_year})"
    if peak_year in all_years[-3:] and last_val >= peak_val * 0.5:
        return f"STABLE-HIGH (peak {peak_year})"
    if last_val < peak_val * 0.5 and peak_year not in all_years[-3:]:
        return f"DECLINING (peaked {peak_year})"
    if last_val == 0 and second_last_val == 0:
        return f"FADED (peaked {peak_year})"
    if peak_year in all_years[len(all_years) // 2:]:
        return f"STABLE (peak {peak_year})"
    return f"MIXED (peak {peak_year})"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--datadir", default=_DEFAULT_DATA_DIR,
                        help="Path to data directory (default: scopus_out7)")
    args = parser.parse_args()
    JSONL_PATH = os.path.join(args.datadir, "raw_scopus_all.jsonl")
    CSV_PATH = os.path.join(args.datadir, "final_ai4chips_high_only.csv")

    papers = load_jsonl(JSONL_PATH)
    ai4chips_ids = load_ai4chips_ids(CSV_PATH)
    total_corpus = len(papers)

    # Classify each paper
    rf_papers = []       # papers with at least one RF match
    year_all = Counter()  # all papers by year
    year_rf = Counter()   # RF papers by year
    cat_counts = Counter()  # RF sub-category counts
    cat_year = defaultdict(Counter)  # category -> year -> count
    venue_rf = Counter()
    rf_in_ai4chips = []
    keyword_hits = Counter()  # individual keyword hit counts

    for p in papers:
        year_all[p["year"]] += 1
        matches = classify_rf(p["title"])
        if not matches:
            continue

        rf_papers.append(p)
        year_rf[p["year"]] += 1
        venue_rf[short_venue(p["venue"])] += 1

        cats_seen = set()
        for cat, label in matches:
            keyword_hits[label] += 1
            if cat not in cats_seen:
                cat_counts[cat] += 1
                cat_year[cat][p["year"]] += 1
                cats_seen.add(cat)

        if p["doc_id"] in ai4chips_ids:
            rf_in_ai4chips.append(p)

    all_years = sorted(year_all)
    n_rf = len(rf_papers)

    # =================================================================
    # SECTION 1: OVERALL TOTALS
    # =================================================================
    print("=" * 70)
    print(f"RF / HIGH-FREQUENCY PRESENCE  (corpus N = {total_corpus})")
    print("=" * 70)
    print(f"  Papers with RF keywords in title:  {n_rf}  "
          f"({100 * n_rf / total_corpus:.1f}% of corpus)")
    print(f"  Papers WITHOUT RF keywords:        {total_corpus - n_rf}  "
          f"({100 * (total_corpus - n_rf) / total_corpus:.1f}%)")

    # =================================================================
    # SECTION 2: BREAKDOWN BY RF SUB-CATEGORY
    # =================================================================
    print()
    print("=" * 70)
    print("RF SUB-CATEGORY BREAKDOWN  (a paper may appear in multiple categories)")
    print("=" * 70)
    print(f"{'Sub-category':<25}{'Papers':>8}{'% of RF':>10}{'% of corpus':>13}")
    print("-" * 56)
    for cat in RF_CATEGORIES:
        n = cat_counts[cat]
        pct_rf = 100 * n / n_rf if n_rf else 0
        pct_all = 100 * n / total_corpus
        print(f"  {cat:<23}{n:>8}{pct_rf:>9.1f}%{pct_all:>12.1f}%")

    # Top individual keywords
    print()
    print("Top keyword hits:")
    for kw, cnt in keyword_hits.most_common(15):
        print(f"  {kw:<25}{cnt:>5}  ({100 * cnt / n_rf:.1f}% of RF papers)")

    # =================================================================
    # SECTION 3: YEAR-BY-YEAR TRENDS
    # =================================================================
    print()
    print("=" * 90)
    print("YEAR-BY-YEAR:  RF papers / total papers (% share)")
    print("=" * 90)
    header = f"{'Year':<8}{'RF':>6}{'Total':>7}{'Share':>8}"
    print(header)
    print("-" * 29)
    for y in all_years:
        r = year_rf.get(y, 0)
        t = year_all[y]
        pct = 100 * r / t if t else 0
        print(f"  {y:<6}{r:>6}{t:>7}{pct:>7.1f}%")
    print("-" * 29)
    print(f"  {'TOTAL':<6}{n_rf:>6}{total_corpus:>7}"
          f"{100 * n_rf / total_corpus:>7.1f}%")

    # Category trend table
    print()
    print("=" * 90)
    print("ABSOLUTE COUNTS BY SUB-CATEGORY PER YEAR")
    print("=" * 90)
    header = f"{'Sub-category':<25}" + "".join(f"{y:>6}" for y in all_years) + f"{'Total':>7}"
    print(header)
    print("-" * len(header))
    for cat in RF_CATEGORIES:
        vals = [cat_year[cat].get(y, 0) for y in all_years]
        row_str = f"  {cat:<23}" + "".join(f"{v:>6}" for v in vals)
        row_str += f"{sum(vals):>7}"
        print(row_str)
    totals_row = [year_rf.get(y, 0) for y in all_years]
    print("-" * len(header))
    print(f"  {'ANY RF (unique)':<23}" + "".join(f"{v:>6}" for v in totals_row)
          + f"{n_rf:>7}")

    # Trend summary
    print()
    print("=" * 90)
    print("TREND SUMMARY BY SUB-CATEGORY")
    print("=" * 90)
    print(f"{'Sub-category':<25}{'Total':>7}{'Recent 3yr':>11}{'Recent %':>10}  {'Trend'}")
    print("-" * 80)
    for cat in RF_CATEGORIES:
        total = sum(cat_year[cat].values())
        recent = sum(cat_year[cat].get(y, 0) for y in all_years[-3:])
        recent_pct = 100 * recent / total if total > 0 else 0
        label = trend_label(cat_year[cat], all_years)
        print(f"  {cat:<23}{total:>7}{recent:>11}{recent_pct:>9.0f}%  {label}")
    # Overall RF trend
    total_rf_all = n_rf
    recent_rf = sum(year_rf.get(y, 0) for y in all_years[-3:])
    recent_rf_pct = 100 * recent_rf / total_rf_all if total_rf_all else 0
    label = trend_label(year_rf, all_years)
    print(f"  {'ALL RF':<23}{total_rf_all:>7}{recent_rf:>11}{recent_rf_pct:>9.0f}%  {label}")

    # =================================================================
    # SECTION 4: TOP VENUES
    # =================================================================
    print()
    print("=" * 70)
    print("TOP VENUES FOR RF PAPERS")
    print("=" * 70)
    print(f"{'Venue':<30}{'RF papers':>10}{'% of RF':>10}")
    print("-" * 50)
    for venue, cnt in venue_rf.most_common(10):
        pct = 100 * cnt / n_rf
        print(f"  {venue:<28}{cnt:>10}{pct:>9.1f}%")

    # =================================================================
    # SECTION 5: OVERLAP WITH AI4CHIPS
    # =================================================================
    print()
    print("=" * 70)
    print(f"OVERLAP WITH AI4CHIPS HIGH-CONFIDENCE SET  (N = {len(ai4chips_ids)})")
    print("=" * 70)
    n_overlap = len(rf_in_ai4chips)
    print(f"  RF papers also in ai4chips:  {n_overlap}  "
          f"({100 * n_overlap / n_rf:.1f}% of RF, "
          f"{100 * n_overlap / len(ai4chips_ids):.1f}% of ai4chips)")
    if rf_in_ai4chips:
        print()
        print("  These papers:")
        for p in sorted(rf_in_ai4chips, key=lambda x: x["year"]):
            matches = classify_rf(p["title"])
            cats = ", ".join(sorted({cat for cat, _ in matches}))
            print(f"    [{p['year']}] {p['title']}")
            print(f"           Matched: {cats}")

    # =================================================================
    # SECTION 6: SAMPLE TITLES BY CATEGORY
    # =================================================================
    print()
    print("=" * 70)
    print("SAMPLE RF TITLES (up to 5 per sub-category)")
    print("=" * 70)
    # Group papers by category
    cat_papers = defaultdict(list)
    for p in rf_papers:
        matches = classify_rf(p["title"])
        for cat, _ in matches:
            cat_papers[cat].append(p)

    for cat in RF_CATEGORIES:
        print(f"\n  {cat}:")
        samples = sorted(cat_papers[cat], key=lambda x: -x["cited_by"])[:5]
        for p in samples:
            print(f"    [{p['year']}] (cit={p['cited_by']:>3}) {p['title']}")


if __name__ == "__main__":
    main()
