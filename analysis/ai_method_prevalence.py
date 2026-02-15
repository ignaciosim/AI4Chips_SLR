"""AI method prevalence analysis using method_tags from the AI4Chips high-confidence corpus.

Note: The CSV has unquoted comma-separated multi-value fields (method_tags,
ai_methods, chip_tasks), so the standard CSV parser splits them into extra
columns. Columns 0-7 are fixed; from column 8 onward, method_tags are values
without a colon, while ai_methods and chip_tasks always contain a colon.
"""

import os

_DEFAULT_DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scopus_out7")

import argparse
import csv
from collections import Counter


def parse_row(row):
    """Extract method_tags from a raw CSV row, handling column overflow."""
    # Columns 0-7 are always: doc_id, stage, year, title, source,
    # classification, confidence, reasoning
    # From column 8 onward: method_tags (no colon), then ai_methods/chip_tasks (have colons)
    tags = []
    for val in row[8:]:
        v = val.strip()
        if not v:
            continue
        if ":" in v:
            break  # reached ai_methods/chip_tasks
        tags.append(v)
    return tags


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--datadir", default=_DEFAULT_DATA_DIR,
                        help="Path to data directory (default: scopus_out7)")
    args = parser.parse_args()
    CSV_PATH = os.path.join(args.datadir, "final_ai4chips_high_only.csv")

    total_papers = 0
    tag_counts = Counter()
    combo_counts = Counter()
    multi_method = 0

    with open(CSV_PATH, "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        next(reader)  # skip header
        for row in reader:
            doc_id = row[0].strip()
            if not doc_id:
                continue
            total_papers += 1

            tags = parse_row(row)
            if not tags:
                continue

            if len(tags) > 1:
                multi_method += 1
                combo_counts[" + ".join(sorted(tags))] += 1

            for tag in tags:
                tag_counts[tag] += 1

    # --- Overall prevalence ---
    print(f"AI Method Prevalence (N = {total_papers} papers)")
    print(f"{'Method Tag':<30}{'Papers':>8}{'% of Total':>12}{'Rank':>6}")
    print("-" * 56)
    for rank, (tag, n) in enumerate(tag_counts.most_common(), 1):
        pct = 100 * n / total_papers
        print(f"{tag:<30}{n:>8}{pct:>11.1f}%{rank:>6}")

    print(f"\nTotal method mentions: {sum(tag_counts.values())} "
          f"(avg {sum(tag_counts.values()) / total_papers:.2f} per paper)")
    print(f"Papers with multiple methods: {multi_method}/{total_papers} "
          f"({100 * multi_method / total_papers:.1f}%)")

    # --- Top method combinations ---
    if combo_counts:
        print(f"\nTop Method Combinations (papers with 2+ tags):")
        print(f"{'Combination':<55}{'Papers':>8}{'%':>8}")
        print("-" * 71)
        for combo, n in combo_counts.most_common(10):
            pct = 100 * n / total_papers
            print(f"{combo:<55}{n:>8}{pct:>7.1f}%")


if __name__ == "__main__":
    main()
