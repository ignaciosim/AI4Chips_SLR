"""Geographic analysis of Nordic countries in the FULL Scopus corpus.

Reads raw_scopus_all.jsonl. Outputs:
  1. Country prevalence — absolute counts per year
  2. Country share — % of each year's papers
  3. Period comparison — 2015-2020 vs 2021-2025
  4. Venue distribution by Nordic country
  5. Citation impact by Nordic country
"""

import os

_DEFAULT_DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scopus_out7")

import argparse
import json
from collections import Counter, defaultdict

NORDIC = ["Denmark", "Finland", "Sweden", "Norway", "Iceland"]

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
}


def h_index(citations):
    s = sorted(citations, reverse=True)
    h = 0
    for i, c in enumerate(s):
        if c >= i + 1:
            h = i + 1
        else:
            break
    return h


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--datadir", default=_DEFAULT_DATA_DIR,
                        help="Path to data directory (default: scopus_out7)")
    args = parser.parse_args()
    JSONL_PATH = os.path.join(args.datadir, "raw_scopus_all.jsonl")

    # ── Load data ──────────────────────────────────────────────────────────
    total_papers = 0
    papers_by_year = Counter()
    country_year = defaultdict(Counter)
    country_counts = Counter()
    country_venue = defaultdict(Counter)
    country_stage = defaultdict(Counter)
    country_cites = defaultdict(list)

    with open(JSONL_PATH, "r", encoding="utf-8") as f:
        for line in f:
            record = json.loads(line)
            entry = record.get("entry", {})
            year = record.get("year")
            stage = record.get("stage", "")
            venue_raw = entry.get("prism:publicationName", "")
            venue = VENUE_ALIASES.get(venue_raw, venue_raw)
            cites = int(entry.get("citedby-count") or 0)

            total_papers += 1
            papers_by_year[year] += 1

            affiliations = entry.get("affiliation") or []
            countries = set()
            for a in affiliations:
                c = a.get("affiliation-country", "")
                if c:
                    countries.add(c)

            nordic_here = [c for c in countries if c in NORDIC]
            for c in nordic_here:
                country_counts[c] += 1
                country_year[c][year] += 1
                country_venue[c][venue] += 1
                country_stage[c][stage] += 1
                country_cites[c].append(cites)

    all_years = sorted(papers_by_year)
    active_nordic = [c for c in NORDIC if country_counts[c] > 0]

    # =====================================================================
    # SECTION 1: ABSOLUTE COUNTS
    # =====================================================================
    print("=" * 100)
    print(f"NORDIC COUNTRIES — ABSOLUTE COUNTS  (Full corpus N = {total_papers})")
    print("=" * 100)
    header = f"{'Country':<12}" + "".join(f"{y:>6}" for y in all_years) + f"{'Total':>7}"
    print(header)
    print("-" * len(header))
    for c in active_nordic:
        vals = [country_year[c].get(y, 0) for y in all_years]
        print(f"{c:<12}" + "".join(f"{v:>6}" for v in vals) + f"{sum(vals):>7}")
    # Nordic total row
    nordic_vals = [sum(country_year[c].get(y, 0) for c in active_nordic) for y in all_years]
    print("-" * len(header))
    print(f"{'Nordic':<12}" + "".join(f"{v:>6}" for v in nordic_vals) + f"{sum(nordic_vals):>7}")
    corpus_vals = [papers_by_year[y] for y in all_years]
    print(f"{'Corpus':<12}" + "".join(f"{v:>6}" for v in corpus_vals) + f"{sum(corpus_vals):>7}")

    # =====================================================================
    # SECTION 2: SHARE (%)
    # =====================================================================
    print()
    print("=" * 100)
    print("NORDIC COUNTRIES — SHARE OF CORPUS (%)")
    print("=" * 100)
    header = f"{'Country':<12}" + "".join(f"{y:>7}" for y in all_years) + f"{'Avg':>7}"
    print(header)
    print("-" * len(header))
    for c in active_nordic:
        parts = []
        for y in all_years:
            n = country_year[c].get(y, 0)
            total_y = papers_by_year[y]
            if n == 0:
                parts.append(f"{'—':>7}")
            else:
                parts.append(f"{100 * n / total_y:>6.1f}%")
        avg = 100 * country_counts[c] / total_papers
        print(f"{c:<12}" + "".join(parts) + f"{avg:>6.1f}%")
    # Nordic total row
    parts = []
    for y in all_years:
        n = sum(country_year[c].get(y, 0) for c in active_nordic)
        total_y = papers_by_year[y]
        if n == 0:
            parts.append(f"{'—':>7}")
        else:
            parts.append(f"{100 * n / total_y:>6.1f}%")
    nordic_total = sum(country_counts[c] for c in active_nordic)
    avg_nordic = 100 * nordic_total / total_papers
    print("-" * len(header))
    print(f"{'Nordic':<12}" + "".join(parts) + f"{avg_nordic:>6.1f}%")

    # =====================================================================
    # SECTION 3: PERIOD COMPARISON
    # =====================================================================
    early_years = [y for y in all_years if y <= 2020]
    late_years = [y for y in all_years if y >= 2021]
    early_total = sum(papers_by_year[y] for y in early_years)
    late_total = sum(papers_by_year[y] for y in late_years)

    print()
    print("=" * 100)
    print("PERIOD COMPARISON: 2015-2020 vs 2021-2025")
    print("=" * 100)
    print(f"{'Country':<12}"
          f"{'2015-2020':>10}{'Share':>8}"
          f"{'2021-2025':>12}{'Share':>8}"
          f"{'Change':>10}")
    print("-" * 60)
    for c in active_nordic:
        e = sum(country_year[c].get(y, 0) for y in early_years)
        l = sum(country_year[c].get(y, 0) for y in late_years)
        e_pct = 100 * e / early_total if early_total else 0
        l_pct = 100 * l / late_total if late_total else 0
        delta = l_pct - e_pct
        sign = "+" if delta > 0 else ""
        print(f"{c:<12}"
              f"{e:>10}{e_pct:>7.2f}%"
              f"{l:>12}{l_pct:>7.2f}%"
              f"{sign}{delta:>8.2f}pp")
    # Nordic total
    e = sum(sum(country_year[c].get(y, 0) for y in early_years) for c in active_nordic)
    l = sum(sum(country_year[c].get(y, 0) for y in late_years) for c in active_nordic)
    e_pct = 100 * e / early_total
    l_pct = 100 * l / late_total
    delta = l_pct - e_pct
    sign = "+" if delta > 0 else ""
    print("-" * 60)
    print(f"{'Nordic':<12}"
          f"{e:>10}{e_pct:>7.2f}%"
          f"{l:>12}{l_pct:>7.2f}%"
          f"{sign}{delta:>8.2f}pp")

    # =====================================================================
    # SECTION 4: VENUE DISTRIBUTION
    # =====================================================================
    print()
    print("=" * 100)
    print("TOP VENUES FOR NORDIC PAPERS")
    print("=" * 100)
    # Aggregate all Nordic venues
    all_nordic_venues = Counter()
    for c in active_nordic:
        all_nordic_venues += country_venue[c]
    print(f"{'Venue':<35}{'Papers':>8}{'% of Nordic':>12}")
    print("-" * 55)
    for v, n in all_nordic_venues.most_common(10):
        short = SHORT_VENUE.get(v, v[:33])
        print(f"{short:<35}{n:>8}{100 * n / nordic_total:>11.1f}%")

    # Per country top venue
    print()
    print(f"{'Country':<12}{'Papers':>8}  {'Top Venue':<30}{'N':>5}{'%':>7}")
    print("-" * 65)
    for c in active_nordic:
        n = country_counts[c]
        top = country_venue[c].most_common(1)
        if top:
            v, vn = top[0]
            short = SHORT_VENUE.get(v, v[:28])
            print(f"{c:<12}{n:>8}  {short:<30}{vn:>5}{100 * vn / n:>6.0f}%")

    # =====================================================================
    # SECTION 5: LIFECYCLE STAGE
    # =====================================================================
    print()
    print("=" * 100)
    print("LIFECYCLE STAGE DISTRIBUTION")
    print("=" * 100)
    stages = ["design", "fabrication", "in_field", "packaging"]
    stage_label = {"design": "Design", "fabrication": "Fab.",
                   "in_field": "In-Field", "packaging": "Pkg."}
    header = f"{'Country':<12}" + "".join(f"{stage_label.get(s, s):>12}" for s in stages) + f"{'Total':>8}"
    print(header)
    print("-" * len(header))
    for c in active_nordic:
        n = country_counts[c]
        parts = []
        for s in stages:
            cnt = country_stage[c].get(s, 0)
            if cnt == 0:
                parts.append(f"{'—':>12}")
            else:
                parts.append(f"{cnt:>4} ({100 * cnt / n:>4.0f}%)")
        print(f"{c:<12}" + "".join(parts) + f"{n:>8}")

    # =====================================================================
    # SECTION 6: CITATION IMPACT
    # =====================================================================
    print()
    print("=" * 100)
    print("CITATION IMPACT")
    print("=" * 100)
    print(f"{'Country':<12}{'Papers':>8}{'Total C':>9}{'Mean':>7}{'Median':>8}"
          f"{'Max':>7}{'h-idx':>7}{'C>=10':>7}{'C>=50':>7}")
    print("-" * 72)
    for c in active_nordic:
        cites = sorted(country_cites[c])
        n = len(cites)
        total_c = sum(cites)
        mean = total_c / n if n else 0
        med = cites[n // 2] if n else 0
        mx = cites[-1] if cites else 0
        h = h_index(cites)
        ge10 = sum(1 for x in cites if x >= 10)
        ge50 = sum(1 for x in cites if x >= 50)
        print(f"{c:<12}{n:>8}{total_c:>9}{mean:>7.1f}{med:>8}"
              f"{mx:>7}{h:>7}{ge10:>7}{ge50:>7}")
    # Nordic aggregate
    all_cites = []
    for c in active_nordic:
        all_cites.extend(country_cites[c])
    all_cites.sort()
    n = len(all_cites)
    if n:
        print("-" * 72)
        print(f"{'Nordic':<12}{n:>8}{sum(all_cites):>9}{sum(all_cites)/n:>7.1f}"
              f"{all_cites[n//2]:>8}{all_cites[-1]:>7}{h_index(all_cites):>7}"
              f"{sum(1 for x in all_cites if x>=10):>7}"
              f"{sum(1 for x in all_cites if x>=50):>7}")


if __name__ == "__main__":
    main()
