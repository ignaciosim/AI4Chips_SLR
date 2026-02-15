"""CAGR (Compound Annual Growth Rate) analysis for the AI4Chips high-confidence corpus."""

import os

_DEFAULT_DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scopus_out7")

import argparse
import csv
from collections import Counter


def cagr(start_val, end_val, periods):
    """Calculate CAGR given start value, end value, and number of periods."""
    if start_val <= 0 or periods <= 0:
        return None
    return (end_val / start_val) ** (1 / periods) - 1


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--datadir", default=_DEFAULT_DATA_DIR,
                        help="Path to data directory (default: scopus_out7)")
    args = parser.parse_args()
    CSV_PATH = os.path.join(args.datadir, "final_ai4chips_high_only.csv")

    years = []
    with open(CSV_PATH, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            doc_id = row["doc_id"].strip()
            if not doc_id:
                continue
            years.append(int(row["year"]))

    counts = Counter(years)
    sorted_years = sorted(counts)
    first_year = sorted_years[0]
    last_year = sorted_years[-1]

    # --- Year-over-Year growth ---
    print(f"{'Year':<8}{'Papers':>8}{'YoY Growth':>12}")
    print("-" * 28)
    prev = None
    for year in sorted_years:
        n = counts[year]
        if prev is not None and prev > 0:
            yoy = 100 * (n - prev) / prev
            print(f"{year:<8}{n:>8}{yoy:>+11.1f}%")
        else:
            print(f"{year:<8}{n:>8}{'—':>12}")
        prev = n
    print()

    # --- CAGR over various windows ---
    print("CAGR over selected windows:")
    print(f"{'Window':<20}{'Start':>8}{'End':>8}{'Years':>8}{'CAGR':>10}")
    print("-" * 54)

    windows = [
        ("Full period",        first_year, last_year),
        ("Last 5 years",       last_year - 5, last_year),
        ("Last 3 years",       last_year - 3, last_year),
        ("First half",         first_year, first_year + (last_year - first_year) // 2),
        ("Second half",        first_year + (last_year - first_year) // 2, last_year),
    ]

    for label, y_start, y_end in windows:
        if y_start in counts and y_end in counts and y_start < y_end:
            periods = y_end - y_start
            rate = cagr(counts[y_start], counts[y_end], periods)
            if rate is not None:
                print(f"{label:<20}{counts[y_start]:>8}{counts[y_end]:>8}{periods:>8}{rate:>+9.1%}")

    # --- Overall CAGR ---
    print()
    periods = last_year - first_year
    overall = cagr(counts[first_year], counts[last_year], periods)
    print(f"Overall CAGR ({first_year}–{last_year}): {overall:+.1%} "
          f"({counts[first_year]} → {counts[last_year]} papers over {periods} years)")


if __name__ == "__main__":
    main()
