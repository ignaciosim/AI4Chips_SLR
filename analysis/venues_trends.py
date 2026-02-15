"""Venue prevalence analysis for the AI4Chips high-confidence corpus.

Counts papers per publication venue, with time trends.
Normalizes known venue name variants (e.g. "Integration the VLSI Journal"
→ "Integration").

Outputs:
  1. Overall totals — venue frequency and ranking
  2. Time trends — absolute counts, yearly share, and trend classification
"""

import os

_DEFAULT_DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scopus_out7")

import argparse
import csv
from collections import Counter, defaultdict

# ── Venue name normalization ──────────────────────────────────────────────
# Maps variant names to a canonical form.

VENUE_ALIASES = {
    "Integration the VLSI Journal": "Integration",
}

# Short labels for display (long IEEE names)
SHORT_LABEL = {
    "IEEE Transactions on Computer Aided Design of Integrated Circuits and Systems":
        "IEEE TCAD",
    "ACM Transactions on Design Automation of Electronic Systems":
        "ACM TODAES",
    "IEEE Transactions on Semiconductor Manufacturing":
        "IEEE TSM",
    "Microelectronics Reliability":
        "Microelectronics Reliability",
    "Microelectronics Journal":
        "Microelectronics Journal",
    "IEEE Transactions on Very Large Scale Integration VLSI Systems":
        "IEEE TVLSI",
    "Integration":
        "Integration",
    "Journal of Industrial Information Integration":
        "J. Ind. Info. Integration",
}


def normalize_venue(raw):
    return VENUE_ALIASES.get(raw, raw)


def short(venue):
    return SHORT_LABEL.get(venue, venue)


def trend_label(counts_by_year, all_years):
    """Classify a venue's trajectory based on its year-by-year counts."""
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


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--datadir", default=_DEFAULT_DATA_DIR,
                        help="Path to data directory (default: scopus_out7)")
    args = parser.parse_args()
    CSV_PATH = os.path.join(args.datadir, "final_ai4chips_high_only.csv")

    # ── Parse ─────────────────────────────────────────────────────────────
    total_papers = 0
    venue_counts = Counter()
    papers_by_year = Counter()
    venue_year = defaultdict(Counter)

    with open(CSV_PATH, "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        next(reader)
        for row in reader:
            doc_id = row[0].strip()
            if not doc_id:
                continue
            total_papers += 1
            year = int(row[2])
            venue = normalize_venue(row[4].strip())

            papers_by_year[year] += 1
            venue_counts[venue] += 1
            venue_year[venue][year] += 1

    all_years = sorted(papers_by_year)
    all_venues = sorted(venue_year, key=lambda v: -sum(venue_year[v].values()))

    # =====================================================================
    # SECTION 1: OVERALL TOTALS
    # =====================================================================
    print("=" * 80)
    print(f"VENUE PREVALENCE  (N = {total_papers} high-confidence ai4chips papers)")
    print("=" * 80)
    print(f"{'Venue':<30}{'Papers':>8}{'% of Total':>12}{'Rank':>6}")
    print("-" * 56)
    for rank, venue in enumerate(all_venues, 1):
        n = venue_counts[venue]
        pct = 100 * n / total_papers
        print(f"{short(venue):<30}{n:>8}{pct:>11.1f}%{rank:>6}")
    print("-" * 56)
    print(f"{'TOTAL':<30}{total_papers:>8}{'100.0%':>12}")
    print(f"\nUnique venues: {len(all_venues)}")

    # =====================================================================
    # SECTION 2: TIME TRENDS
    # =====================================================================

    # --- Absolute counts table ---
    print()
    print("=" * 100)
    print("ABSOLUTE COUNTS: Papers per venue per year")
    print("=" * 100)
    header = f"{'Venue':<30}" + "".join(f"{y:>6}" for y in all_years) + f"{'Total':>7}"
    print(header)
    print("-" * len(header))
    for venue in all_venues:
        vals = [venue_year[venue].get(y, 0) for y in all_years]
        row_str = f"{short(venue):<30}" + "".join(f"{v:>6}" for v in vals)
        row_str += f"{sum(vals):>7}"
        print(row_str)
    totals = [papers_by_year[y] for y in all_years]
    print("-" * len(header))
    print(f"{'ALL PAPERS':<30}" + "".join(f"{t:>6}" for t in totals) + f"{sum(totals):>7}")

    # --- Percentage share table ---
    print()
    print("=" * 100)
    print("SHARE: Venue as % of each year's papers")
    print("=" * 100)
    header = f"{'Venue':<30}" + "".join(f"{y:>6}" for y in all_years)
    print(header)
    print("-" * len(header))
    for venue in all_venues:
        parts = []
        for y in all_years:
            n = venue_year[venue].get(y, 0)
            total_y = papers_by_year[y]
            if n == 0:
                parts.append(f"{'—':>6}")
            else:
                pct = 100 * n / total_y
                parts.append(f"{pct:>5.0f}%")
        print(f"{short(venue):<30}" + "".join(parts))

    # --- Trend summary ---
    print()
    print("=" * 100)
    print("TREND SUMMARY")
    print("=" * 100)
    print(f"{'Venue':<30}{'Total':>7}{'Recent 3yr':>11}{'Recent %':>10}  {'Trend'}")
    print("-" * 85)
    for venue in all_venues:
        total = sum(venue_year[venue].values())
        recent = sum(venue_year[venue].get(y, 0) for y in all_years[-3:])
        recent_pct = 100 * recent / total if total > 0 else 0
        label = trend_label(venue_year[venue], all_years)
        print(f"{short(venue):<30}{total:>7}{recent:>11}{recent_pct:>9.0f}%  {label}")


if __name__ == "__main__":
    main()
