"""AI method prevalence trends over time for the AI4Chips high-confidence corpus.

Tracks each method_tag by year to identify rising, peaking, and declining methods.
Handles unquoted comma-separated multi-value fields in the CSV.
"""

import os

_DEFAULT_DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scopus_out7")

import argparse
import csv
from collections import Counter, defaultdict


def parse_method_tags(row):
    """Extract method_tags from a raw CSV row, handling column overflow."""
    tags = []
    for val in row[8:]:
        v = val.strip()
        if not v:
            continue
        if ":" in v:
            break
        tags.append(v)
    return tags


def trend_label(counts_by_year, all_years):
    """Classify a method's trajectory based on its year-by-year counts."""
    years_present = sorted(y for y in all_years if counts_by_year.get(y, 0) > 0)
    if not years_present:
        return "inactive"

    values = [counts_by_year.get(y, 0) for y in all_years]
    first_year = years_present[0]
    last_year = years_present[-1]
    peak_year = max(all_years, key=lambda y: counts_by_year.get(y, 0))
    peak_val = counts_by_year[peak_year]

    # Recent activity: last 3 years
    recent_years = all_years[-3:]
    recent_sum = sum(counts_by_year.get(y, 0) for y in recent_years)
    total = sum(values)
    recent_share = recent_sum / total if total > 0 else 0

    # Early activity: first 3 years with data
    early_years = all_years[:3]
    early_sum = sum(counts_by_year.get(y, 0) for y in early_years)

    # Last year value vs peak
    last_val = counts_by_year.get(all_years[-1], 0)
    second_last_val = counts_by_year.get(all_years[-2], 0)

    # Trend classification
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
    elif peak_year in all_years[len(all_years)//2:]:
        return f"STABLE (peak {peak_year})"
    else:
        return f"MIXED (peak {peak_year})"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--datadir", default=_DEFAULT_DATA_DIR,
                        help="Path to data directory (default: scopus_out7)")
    args = parser.parse_args()
    CSV_PATH = os.path.join(args.datadir, "final_ai4chips_high_only.csv")

    # Parse data
    papers_by_year = Counter()
    method_year = defaultdict(Counter)  # method -> {year: count}

    with open(CSV_PATH, "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        next(reader)
        for row in reader:
            doc_id = row[0].strip()
            if not doc_id:
                continue
            year = int(row[2])
            papers_by_year[year] += 1
            for tag in parse_method_tags(row):
                method_year[tag][year] += 1

    all_years = sorted(papers_by_year)
    all_methods = sorted(method_year, key=lambda m: -sum(method_year[m].values()))

    # --- Absolute counts table ---
    print("=" * 90)
    print("ABSOLUTE COUNTS: Papers per method per year")
    print("=" * 90)
    header = f"{'Method':<28}" + "".join(f"{y:>6}" for y in all_years) + f"{'Total':>7}"
    print(header)
    print("-" * len(header))
    for method in all_methods:
        vals = [method_year[method].get(y, 0) for y in all_years]
        row_str = f"{method:<28}" + "".join(f"{v:>6}" for v in vals)
        row_str += f"{sum(vals):>7}"
        print(row_str)
    # Totals row
    totals = [papers_by_year[y] for y in all_years]
    print("-" * len(header))
    print(f"{'ALL PAPERS':<28}" + "".join(f"{t:>6}" for t in totals) + f"{sum(totals):>7}")

    # --- Percentage share table (method as % of that year's papers) ---
    print()
    print("=" * 90)
    print("SHARE: Method as % of each year's papers")
    print("=" * 90)
    header = f"{'Method':<28}" + "".join(f"{y:>6}" for y in all_years)
    print(header)
    print("-" * len(header))
    for method in all_methods:
        parts = []
        for y in all_years:
            n = method_year[method].get(y, 0)
            total_y = papers_by_year[y]
            if n == 0:
                parts.append(f"{'—':>6}")
            else:
                pct = 100 * n / total_y
                parts.append(f"{pct:>5.0f}%")
        print(f"{method:<28}" + "".join(parts))

    # --- Trend summary ---
    print()
    print("=" * 90)
    print("TREND SUMMARY")
    print("=" * 90)
    print(f"{'Method':<28}{'Total':>7}{'Recent 3yr':>11}{'Recent %':>10}  {'Trend'}")
    print("-" * 85)
    for method in all_methods:
        total = sum(method_year[method].values())
        recent = sum(method_year[method].get(y, 0) for y in all_years[-3:])
        recent_pct = 100 * recent / total if total > 0 else 0
        label = trend_label(method_year[method], all_years)
        print(f"{method:<28}{total:>7}{recent:>11}{recent_pct:>9.0f}%  {label}")


if __name__ == "__main__":
    main()
