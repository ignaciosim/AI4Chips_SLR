"""Publication volume per year for the AI4Chips high-confidence corpus."""

import os

_DEFAULT_DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scopus_out7")

import argparse
import csv
from collections import Counter


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

    total = len(years)
    counts = Counter(years)

    # Table header
    print(f"{'Year':<8}{'Papers':>8}{'% of Total':>12}{'Cumulative':>12}{'Cum %':>10}")
    print("-" * 50)

    cumulative = 0
    for year in sorted(counts):
        n = counts[year]
        cumulative += n
        pct = 100 * n / total
        cum_pct = 100 * cumulative / total
        print(f"{year:<8}{n:>8}{pct:>11.1f}%{cumulative:>12}{cum_pct:>9.1f}%")

    print("-" * 50)
    print(f"{'TOTAL':<8}{total:>8}{'100.0%':>12}")


if __name__ == "__main__":
    main()
