"""Spotlight report on two emerging topical applications:

  1. Soft / Silent Error Analysis — SEU, fault injection, fault tolerance,
     silent data corruption, transient faults, radiation effects
  2. Deposition Process Optimization — ALD, CVD, PVD, thin-film deposition,
     virtual metrology for deposition processes

Both topics have seen recent growth and are industrially relevant.
This script identifies matching papers, lists them, and produces time-trend
tables in the same format as the other analysis scripts.
"""

import os

_DEFAULT_DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scopus_out7")

import argparse
import csv
from collections import Counter, defaultdict

# ── Topic keyword definitions (matched against lowercased title) ──────────

SOFT_ERROR_KW = [
    "soft error", "soft-error",
    "seu", "single event upset", "single-event upset",
    "silent data", "sdc",
    "transient fault",
    "fault injection",
    "fault tolerance",
    "radiation effect", "cosmic ray", "alpha particle",
    "critical flip-flop",
]

# Titles that match generic keywords but are NOT about soft errors
SOFT_ERROR_EXCLUDE = [
    "multi-bit flip-flop",      # physical design optimization
    "pseudo approximation",     # circuit design, not soft error
    "failure rate estimation",  # yield / high-sigma analysis
    "failure rates in pulsed",  # MRAM switching reliability
    "yield analysis",           # yield, not soft error
]

DEPOSITION_KW = [
    "atomic layer deposition", "ald",
    "chemical vapor deposition", "cvd",
    "pecvd", "mocvd", "lpcvd",
    "physical vapor deposition", "pvd",
    "sputtering",
    "thin film", "thin-film",
    "film deposition", "film thickness",
    "deposition process", "deposition control",
    "deposition condition",
    "epitaxy", "epitaxial",
    # Virtual metrology for deposition
    "virtual metrology",
    # Broad deposition mention in title
    "deposition",
]


def matches_topic(title_lower, keywords, exclude=None):
    """Return True if title matches any keyword and no exclusion."""
    if exclude:
        for ex in exclude:
            if ex in title_lower:
                return False
    return any(kw in title_lower for kw in keywords)


def parse_method_tags(row):
    """Extract method_tags (no colon) from cols 8+."""
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
    """Classify a topic's trajectory based on its year-by-year counts."""
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


TOPICS = {
    "soft_error": {
        "label": "Soft/Silent Error Analysis",
        "kw": SOFT_ERROR_KW,
        "exclude": SOFT_ERROR_EXCLUDE,
    },
    "deposition": {
        "label": "Deposition Process Optimization",
        "kw": DEPOSITION_KW,
        "exclude": None,
    },
}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--datadir", default=_DEFAULT_DATA_DIR,
                        help="Path to data directory (default: scopus_out7)")
    args = parser.parse_args()
    CSV_PATH = os.path.join(args.datadir, "final_ai4chips_high_only.csv")

    # ── Parse ─────────────────────────────────────────────────────────────
    total_papers = 0
    papers_by_year = Counter()
    topic_papers = defaultdict(list)       # topic -> [(year, title, venue, methods)]
    topic_year = defaultdict(Counter)      # topic -> {year: count}

    with open(CSV_PATH, "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        next(reader)
        for row in reader:
            doc_id = row[0].strip()
            if not doc_id:
                continue
            total_papers += 1
            year = int(row[2])
            title = row[3]
            venue = row[4]
            papers_by_year[year] += 1
            title_lower = title.lower()

            methods = parse_method_tags(row)

            for topic_key, topic_def in TOPICS.items():
                if matches_topic(title_lower, topic_def["kw"], topic_def["exclude"]):
                    topic_papers[topic_key].append((year, title, venue, methods))
                    topic_year[topic_key][year] += 1

    all_years = sorted(papers_by_year)

    # =====================================================================
    # PAPER LISTINGS
    # =====================================================================
    for topic_key in ["soft_error", "deposition"]:
        label = TOPICS[topic_key]["label"]
        papers = sorted(topic_papers[topic_key])
        n = len(papers)
        pct = 100 * n / total_papers

        print("=" * 100)
        print(f"{label.upper()}  ({n} papers, {pct:.1f}% of corpus)")
        print("=" * 100)
        for i, (year, title, venue, methods) in enumerate(papers, 1):
            method_str = ", ".join(methods) if methods else "—"
            print(f"  {i:>2}. [{year}] {title}")
            print(f"      Venue: {venue}")
            print(f"      AI Methods: {method_str}")
            print()

    # =====================================================================
    # COMBINED TIME TRENDS
    # =====================================================================
    topics_ordered = ["soft_error", "deposition"]

    # --- Absolute counts table ---
    print("=" * 100)
    print("ABSOLUTE COUNTS: Papers per topic per year")
    print("=" * 100)
    header = f"{'Topic':<35}" + "".join(f"{y:>6}" for y in all_years) + f"{'Total':>7}"
    print(header)
    print("-" * len(header))
    for topic_key in topics_ordered:
        label = TOPICS[topic_key]["label"]
        vals = [topic_year[topic_key].get(y, 0) for y in all_years]
        row_str = f"{label:<35}" + "".join(f"{v:>6}" for v in vals)
        row_str += f"{sum(vals):>7}"
        print(row_str)
    totals = [papers_by_year[y] for y in all_years]
    print("-" * len(header))
    print(f"{'ALL PAPERS':<35}" + "".join(f"{t:>6}" for t in totals) + f"{sum(totals):>7}")

    # --- Percentage share table ---
    print()
    print("=" * 100)
    print("SHARE: Topic as % of each year's papers")
    print("=" * 100)
    header = f"{'Topic':<35}" + "".join(f"{y:>6}" for y in all_years)
    print(header)
    print("-" * len(header))
    for topic_key in topics_ordered:
        label = TOPICS[topic_key]["label"]
        parts = []
        for y in all_years:
            n = topic_year[topic_key].get(y, 0)
            total_y = papers_by_year[y]
            if n == 0:
                parts.append(f"{'—':>6}")
            else:
                pct = 100 * n / total_y
                parts.append(f"{pct:>5.0f}%")
        print(f"{label:<35}" + "".join(parts))

    # --- Trend summary ---
    print()
    print("=" * 100)
    print("TREND SUMMARY")
    print("=" * 100)
    print(f"{'Topic':<35}{'Total':>7}{'Recent 3yr':>11}{'Recent %':>10}  {'Trend'}")
    print("-" * 90)
    for topic_key in topics_ordered:
        label = TOPICS[topic_key]["label"]
        total = sum(topic_year[topic_key].values())
        recent = sum(topic_year[topic_key].get(y, 0) for y in all_years[-3:])
        recent_pct = 100 * recent / total if total > 0 else 0
        tl = trend_label(topic_year[topic_key], all_years)
        print(f"{label:<35}{total:>7}{recent:>11}{recent_pct:>9.0f}%  {tl}")

    # --- Method breakdown per topic ---
    for topic_key in topics_ordered:
        label = TOPICS[topic_key]["label"]
        method_counts = Counter()
        for year, title, venue, methods in topic_papers[topic_key]:
            for m in methods:
                method_counts[m] += 1
        if method_counts:
            n = len(topic_papers[topic_key])
            print()
            print(f"AI METHODS used in {label} (N = {n}):")
            print(f"  {'Method':<30}{'Papers':>8}{'%':>8}")
            print(f"  {'-' * 46}")
            for m, c in method_counts.most_common():
                pct = 100 * c / n
                print(f"  {m:<30}{c:>8}{pct:>7.0f}%")


if __name__ == "__main__":
    main()
