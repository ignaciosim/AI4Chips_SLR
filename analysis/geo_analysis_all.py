"""Geographic analysis of the FULL Scopus corpus (all papers, not just ai4chips).

Reads raw_scopus_all.jsonl directly. No classification/method data is available
for the full corpus, so this script focuses on publication geography.

Sections:
  1. Country prevalence — overall ranking
  2. Country time trends — absolute counts, share%, trend labels
  3. Period comparison — 2015-2020 vs 2021-2025
  4. Regional distribution + trends
  5. Emerging countries detail
  6. Venue distribution by country (top countries)
  7. Lifecycle stage by country (top countries)
  8. Citation impact by country (top countries)

A paper is counted once per unique country in its affiliation list.
"""

import os

_DEFAULT_DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scopus_out7")

import argparse
import json
from collections import Counter, defaultdict
import math

CURRENT_YEAR = 2025

# ── Region definitions ────────────────────────────────────────────────────

ESTABLISHED_LEADERS = {"China", "United States"}

EUROPE = {
    "Germany", "France", "United Kingdom", "Netherlands", "Belgium",
    "Switzerland", "Austria", "Italy", "Denmark", "Greece", "Portugal",
    "Sweden", "Finland", "Spain", "Norway", "Ireland", "Poland",
    "Czech Republic", "Hungary", "Romania", "Croatia", "Serbia",
    "Bulgaria", "Slovenia", "Lithuania", "Latvia", "Estonia",
    "Luxembourg", "Slovakia", "Cyprus", "Malta",
}

EAST_ASIA_TIGERS = {"South Korea", "Taiwan", "Japan", "Singapore", "Hong Kong"}


def get_region(country):
    if country in ESTABLISHED_LEADERS:
        return country
    if country in EUROPE:
        return "Europe"
    if country in EAST_ASIA_TIGERS:
        return "East Asia (excl. China)"
    if country == "Canada":
        return "Canada"
    return "Emerging & Other"


# ── Venue short names ─────────────────────────────────────────────────────

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


def trend_label(counts_by_year, all_years):
    """Classify trajectory based on year-by-year counts."""
    years_present = sorted(y for y in all_years if counts_by_year.get(y, 0) > 0)
    if not years_present:
        return "inactive"

    values = [counts_by_year.get(y, 0) for y in all_years]
    peak_year = max(all_years, key=lambda y: counts_by_year.get(y, 0))
    peak_val = counts_by_year[peak_year]
    total = sum(values)

    recent_years = all_years[-3:]
    recent_sum = sum(counts_by_year.get(y, 0) for y in recent_years)
    recent_share = recent_sum / total if total > 0 else 0

    last_val = counts_by_year.get(all_years[-1], 0)
    second_last_val = counts_by_year.get(all_years[-2], 0)

    if total <= 3:
        return "too few data points"

    if peak_year in all_years[-2:] and recent_share >= 0.5:
        return f"RISING (peak {peak_year})"
    elif peak_year == all_years[-1]:
        return f"RISING (peak {peak_year})"
    elif last_val >= peak_val * 0.8 and recent_share >= 0.4:
        return f"RISING (near peak, peak {peak_year})"
    elif peak_year in all_years[-3:] and last_val >= peak_val * 0.5:
        return f"STABLE-HIGH (peak {peak_year})"
    elif last_val < peak_val * 0.5 and peak_year not in all_years[-3:]:
        return f"DECLINING (peaked {peak_year})"
    elif last_val == 0 and second_last_val == 0:
        return f"FADED (peaked {peak_year})"
    elif peak_year in all_years[len(all_years) // 2:]:
        return f"STABLE (peak {peak_year})"
    else:
        return f"MIXED (peak {peak_year})"


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

    # ── Load data ─────────────────────────────────────────────────────────
    total_papers = 0
    papers_by_year = Counter()
    country_counts = Counter()
    country_year = defaultdict(Counter)
    region_counts = Counter()
    region_year = defaultdict(Counter)
    country_venue = defaultdict(Counter)     # country -> {venue: count}
    country_stage = defaultdict(Counter)     # country -> {stage: count}
    country_cites = defaultdict(list)        # country -> [cite counts]
    collab_papers = 0
    no_affil = 0

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

            if not countries:
                no_affil += 1
                continue

            if len(countries) > 1:
                collab_papers += 1

            for c in countries:
                country_counts[c] += 1
                country_year[c][year] += 1
                country_venue[c][venue] += 1
                country_stage[c][stage] += 1
                country_cites[c].append(cites)

                region = get_region(c)
                region_counts[region] += 1
                region_year[region][year] += 1

    all_years = sorted(papers_by_year)
    all_countries = sorted(country_counts, key=lambda c: -country_counts[c])

    # =====================================================================
    # SECTION 1: COUNTRY PREVALENCE
    # =====================================================================
    print("=" * 80)
    print(f"COUNTRY PREVALENCE — FULL CORPUS  (N = {total_papers} papers, "
          f"{len(all_countries)} countries)")
    print("=" * 80)
    print(f"{'Country':<30}{'Papers':>8}{'% of Total':>12}{'Rank':>6}")
    print("-" * 56)
    for rank, c in enumerate(all_countries[:25], 1):
        n = country_counts[c]
        pct = 100 * n / total_papers
        print(f"{c:<30}{n:>8}{pct:>11.1f}%{rank:>6}")
    remaining = len(all_countries) - 25
    if remaining > 0:
        rem_n = sum(country_counts[c] for c in all_countries[25:])
        print(f"{'(+ ' + str(remaining) + ' more countries)':<30}{rem_n:>8}"
              f"{100 * rem_n / total_papers:>11.1f}%")
    print("-" * 56)
    print(f"\nInternational collaborations: {collab_papers}/{total_papers} "
          f"({100 * collab_papers / total_papers:.1f}%)")
    if no_affil:
        print(f"Papers with no affiliation data: {no_affil}")

    # =====================================================================
    # SECTION 2: COUNTRY TIME TRENDS (top 15)
    # =====================================================================
    top_countries = all_countries[:15]

    print()
    print("=" * 110)
    print("ABSOLUTE COUNTS: Papers per country per year (top 15)")
    print("=" * 110)
    header = f"{'Country':<20}" + "".join(f"{y:>6}" for y in all_years) + f"{'Total':>7}"
    print(header)
    print("-" * len(header))
    for c in top_countries:
        vals = [country_year[c].get(y, 0) for y in all_years]
        row_str = f"{c:<20}" + "".join(f"{v:>6}" for v in vals)
        row_str += f"{sum(vals):>7}"
        print(row_str)
    totals = [papers_by_year[y] for y in all_years]
    print("-" * len(header))
    print(f"{'ALL PAPERS':<20}" + "".join(f"{t:>6}" for t in totals) + f"{sum(totals):>7}")

    # --- Share ---
    print()
    print("=" * 110)
    print("SHARE: Country as % of each year's papers (top 15)")
    print("=" * 110)
    header = f"{'Country':<20}" + "".join(f"{y:>6}" for y in all_years)
    print(header)
    print("-" * len(header))
    for c in top_countries:
        parts = []
        for y in all_years:
            n = country_year[c].get(y, 0)
            total_y = papers_by_year[y]
            if n == 0:
                parts.append(f"{'—':>6}")
            else:
                pct = 100 * n / total_y
                parts.append(f"{pct:>5.0f}%")
        print(f"{c:<20}" + "".join(parts))

    # --- Trend summary ---
    print()
    print("=" * 110)
    print("TREND SUMMARY (top 15 countries)")
    print("=" * 110)
    print(f"{'Country':<20}{'Total':>7}{'Recent 3yr':>11}{'Recent %':>10}  {'Trend'}")
    print("-" * 80)
    for c in top_countries:
        total = sum(country_year[c].values())
        recent = sum(country_year[c].get(y, 0) for y in all_years[-3:])
        recent_pct = 100 * recent / total if total > 0 else 0
        label = trend_label(country_year[c], all_years)
        print(f"{c:<20}{total:>7}{recent:>11}{recent_pct:>9.0f}%  {label}")

    # =====================================================================
    # SECTION 3: PERIOD COMPARISON
    # =====================================================================
    early_years = [y for y in all_years if y <= 2020]
    late_years  = [y for y in all_years if y >= 2021]
    early_total = sum(papers_by_year[y] for y in early_years)
    late_total  = sum(papers_by_year[y] for y in late_years)

    print()
    print("=" * 110)
    print(f"PERIOD COMPARISON: 2015-2020 vs 2021-2025 (top 15 countries)")
    print("=" * 110)
    print(f"{'Country':<20}"
          f"{'2015-2020':>10}{'Share':>8}"
          f"{'2021-2025':>12}{'Share':>8}"
          f"{'Change':>10}")
    print("-" * 68)
    for c in top_countries:
        e = sum(country_year[c].get(y, 0) for y in early_years)
        l = sum(country_year[c].get(y, 0) for y in late_years)
        e_pct = 100 * e / early_total if early_total else 0
        l_pct = 100 * l / late_total  if late_total  else 0
        delta = l_pct - e_pct
        sign = "+" if delta > 0 else ""
        print(f"{c:<20}"
              f"{e:>10}{e_pct:>7.1f}%"
              f"{l:>12}{l_pct:>7.1f}%"
              f"{sign}{delta:>9.1f}pp")
    print("-" * 68)
    print(f"{'ALL PAPERS':<20}"
          f"{early_total:>10}{'100.0%':>8}"
          f"{late_total:>12}{'100.0%':>8}")

    # =====================================================================
    # SECTION 4: REGIONAL DISTRIBUTION
    # =====================================================================
    print()
    print("=" * 110)
    print("REGIONAL DISTRIBUTION")
    print("=" * 110)
    region_order = sorted(region_counts, key=lambda r: -region_counts[r])
    print(f"{'Region':<30}{'Papers':>8}{'% of Total':>12}")
    print("-" * 50)
    for r in region_order:
        n = region_counts[r]
        pct = 100 * n / total_papers
        print(f"{r:<30}{n:>8}{pct:>11.1f}%")

    # Regional time trends
    print()
    header = f"{'Region':<30}" + "".join(f"{y:>6}" for y in all_years) + f"{'Total':>7}"
    print(header)
    print("-" * len(header))
    for r in region_order:
        vals = [region_year[r].get(y, 0) for y in all_years]
        row_str = f"{r:<30}" + "".join(f"{v:>6}" for v in vals)
        row_str += f"{sum(vals):>7}"
        print(row_str)

    print()
    print(f"{'Region':<30}{'Total':>7}{'Recent 3yr':>11}{'Recent %':>10}  {'Trend'}")
    print("-" * 85)
    for r in region_order:
        total = sum(region_year[r].values())
        recent = sum(region_year[r].get(y, 0) for y in all_years[-3:])
        recent_pct = 100 * recent / total if total > 0 else 0
        label = trend_label(region_year[r], all_years)
        print(f"{r:<30}{total:>7}{recent:>11}{recent_pct:>9.0f}%  {label}")

    # =====================================================================
    # SECTION 5: EMERGING COUNTRIES DETAIL
    # =====================================================================
    print()
    print("=" * 110)
    print("EMERGING & OTHER COUNTRIES — DETAIL (3+ papers)")
    print("=" * 110)
    emerging_countries = [c for c in all_countries
                          if c not in ESTABLISHED_LEADERS
                          and c not in EUROPE
                          and c not in EAST_ASIA_TIGERS
                          and c != "Canada"
                          and country_counts[c] >= 3]
    if emerging_countries:
        print(f"{'Country':<25}{'Papers':>8}{'Years':>12}{'Collab%':>10}  {'Top Venue'}")
        print("-" * 95)
        for c in emerging_countries:
            n = country_counts[c]
            years_active = sorted(y for y in all_years if country_year[c].get(y, 0) > 0)
            yr_range = f"{years_active[0]}-{years_active[-1]}" if len(years_active) > 1 else str(years_active[0])
            top_v = country_venue[c].most_common(1)[0]
            top_venue = SHORT_VENUE.get(top_v[0], top_v[0][:25])
            print(f"{c:<25}{n:>8}{yr_range:>12}{'':>10}  {top_venue} ({top_v[1]})")

    # =====================================================================
    # SECTION 6: VENUE DISTRIBUTION BY COUNTRY (top 10)
    # =====================================================================
    print()
    print("=" * 110)
    print("TOP VENUE PER COUNTRY (top 15)")
    print("=" * 110)
    print(f"{'Country':<20}{'Papers':>8}  {'Top Venue':<25}{'Venue N':>8}{'Venue %':>9}"
          f"  {'2nd Venue':<25}{'2nd N':>6}")
    print("-" * 105)
    for c in top_countries:
        n = country_counts[c]
        top2 = country_venue[c].most_common(2)
        v1 = SHORT_VENUE.get(top2[0][0], top2[0][0][:25])
        v1_n = top2[0][1]
        v1_pct = 100 * v1_n / n
        if len(top2) > 1:
            v2 = SHORT_VENUE.get(top2[1][0], top2[1][0][:25])
            v2_n = top2[1][1]
        else:
            v2 = "—"
            v2_n = 0
        print(f"{c:<20}{n:>8}  {v1:<25}{v1_n:>8}{v1_pct:>8.0f}%"
              f"  {v2:<25}{v2_n:>6}")

    # =====================================================================
    # SECTION 7: LIFECYCLE STAGE BY COUNTRY (top 10)
    # =====================================================================
    print()
    print("=" * 110)
    print("LIFECYCLE STAGE DISTRIBUTION BY COUNTRY (top 10)")
    print("=" * 110)
    stages = ["design", "fabrication", "in_field", "packaging"]
    stage_label = {"design": "Design", "fabrication": "Fabrication",
                   "in_field": "In-Field", "packaging": "Packaging"}
    top10 = all_countries[:10]
    header = f"{'Country':<20}" + "".join(f"{stage_label.get(s, s):>14}" for s in stages) + f"{'Total':>8}"
    print(header)
    print("-" * len(header))
    for c in top10:
        n = country_counts[c]
        parts = []
        for s in stages:
            cnt = country_stage[c].get(s, 0)
            if cnt == 0:
                parts.append(f"{'—':>14}")
            else:
                pct = 100 * cnt / n
                parts.append(f"{cnt:>5} ({pct:>4.0f}%)" + "  ")
        print(f"{c:<20}" + "".join(parts) + f"{n:>8}")

    # =====================================================================
    # SECTION 8: CITATION IMPACT BY COUNTRY (top 15)
    # =====================================================================
    print()
    print("=" * 110)
    print("CITATION IMPACT BY COUNTRY (top 15)")
    print("=" * 110)
    print(f"{'Country':<20}{'Papers':>8}{'Total C':>9}{'Mean':>7}{'Median':>8}"
          f"{'Max':>7}{'h-idx':>7}{'C>=10':>7}{'C>=50':>7}")
    print("-" * 80)
    for c in top_countries:
        cites = sorted(country_cites[c])
        n = len(cites)
        total_c = sum(cites)
        mean = total_c / n if n else 0
        med = cites[n // 2] if n else 0
        mx = cites[-1] if cites else 0
        h = h_index(cites)
        ge10 = sum(1 for x in cites if x >= 10)
        ge50 = sum(1 for x in cites if x >= 50)
        print(f"{c:<20}{n:>8}{total_c:>9}{mean:>7.1f}{med:>8}"
              f"{mx:>7}{h:>7}{ge10:>7}{ge50:>7}")


if __name__ == "__main__":
    main()
