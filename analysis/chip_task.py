"""Chip design task prevalence analysis for the AI4Chips high-confidence corpus.

Two sections:
  1. Overall totals — task frequency, rankings, top combinations
  2. Time trends — absolute counts, yearly share, and trend classification

Handles unquoted comma-separated multi-value fields in the CSV the same way
the ai_method_prevalence scripts do.
"""

import os

_DEFAULT_DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scopus_out7")

import argparse
import csv
from collections import Counter, defaultdict

# Known chip-task keys (from slr_ontology.py CHIP_DESIGN_TASKS)
TASK_KEYS = {
    "placement", "routing", "timing_analysis", "logic_synthesis",
    "power_analysis", "design_space_exploration", "analog_circuit_design",
    "verification", "calibration", "lithography_optimization",
    "hotspot_detection", "defect_detection", "yield_prediction",
    "wafer_map_analysis", "process_optimization", "test_generation",
    "fault_diagnosis", "reliability_analysis", "thermal_management",
}


def parse_chip_tasks(row):
    """Extract chip_task keys from a raw CSV row, handling column overflow.

    chip_task values have the form  key:surface_form  where key is one of
    the TASK_KEYS.  We scan columns 8+ (past the fixed fields) and collect
    every value whose key portion is a known task.
    """
    tasks = []
    for val in row[8:]:
        v = val.strip()
        if not v or ":" not in v:
            continue
        key = v.split(":")[0].strip()
        if key in TASK_KEYS:
            tasks.append(key)
    # deduplicate within a single paper (same task matched on multiple surface forms)
    return list(dict.fromkeys(tasks))


# ── Friendly display labels ──────────────────────────────────────────────
LABEL = {
    "placement": "Placement",
    "routing": "Routing",
    "timing_analysis": "Timing Analysis",
    "logic_synthesis": "Logic Synthesis",
    "power_analysis": "Power Analysis",
    "design_space_exploration": "Design Space Exploration",
    "analog_circuit_design": "Analog Circuit Design",
    "verification": "Verification",
    "calibration": "Calibration",
    "lithography_optimization": "Lithography Optimization",
    "hotspot_detection": "Hotspot Detection",
    "defect_detection": "Defect Detection",
    "yield_prediction": "Yield Prediction",
    "wafer_map_analysis": "Wafer Map Analysis",
    "process_optimization": "Process Optimization",
    "test_generation": "Test Generation",
    "fault_diagnosis": "Fault Diagnosis",
    "reliability_analysis": "Reliability Analysis",
    "thermal_management": "Thermal Management",
}


def trend_label(counts_by_year, all_years):
    """Classify a task's trajectory based on its year-by-year counts."""
    years_present = sorted(y for y in all_years if counts_by_year.get(y, 0) > 0)
    if not years_present:
        return "inactive"

    values = [counts_by_year.get(y, 0) for y in all_years]
    peak_year = max(all_years, key=lambda y: counts_by_year.get(y, 0))
    peak_val = counts_by_year[peak_year]
    total = sum(values)

    # Recent activity: last 3 years
    recent_years = all_years[-3:]
    recent_sum = sum(counts_by_year.get(y, 0) for y in recent_years)
    recent_share = recent_sum / total if total > 0 else 0

    # Last year value vs peak
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
    papers_with_tasks = 0
    tag_counts = Counter()
    combo_counts = Counter()
    multi_task = 0
    papers_by_year = Counter()
    task_year = defaultdict(Counter)  # task -> {year: count}

    with open(CSV_PATH, "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        next(reader)  # skip header
        for row in reader:
            doc_id = row[0].strip()
            if not doc_id:
                continue
            total_papers += 1
            year = int(row[2])
            papers_by_year[year] += 1

            tasks = parse_chip_tasks(row)
            if not tasks:
                continue

            papers_with_tasks += 1
            if len(tasks) > 1:
                multi_task += 1
                combo_counts[" + ".join(sorted(LABEL.get(t, t) for t in tasks))] += 1

            for t in tasks:
                tag_counts[t] += 1
                task_year[t][year] += 1

    all_years = sorted(papers_by_year)
    all_tasks = sorted(task_year, key=lambda t: -sum(task_year[t].values()))

    # =====================================================================
    # SECTION 1: OVERALL TOTALS
    # =====================================================================
    print("=" * 70)
    print(f"CHIP DESIGN TASK PREVALENCE  (N = {total_papers} high-confidence ai4chips papers)")
    print("=" * 70)
    print(f"{'Task':<30}{'Papers':>8}{'% of Total':>12}{'Rank':>6}")
    print("-" * 56)
    for rank, (task, n) in enumerate(tag_counts.most_common(), 1):
        pct = 100 * n / total_papers
        print(f"{LABEL.get(task, task):<30}{n:>8}{pct:>11.1f}%{rank:>6}")

    total_mentions = sum(tag_counts.values())
    print(f"\nTotal task mentions: {total_mentions} "
          f"(avg {total_mentions / total_papers:.2f} per paper)")
    print(f"Papers with any chip task: {papers_with_tasks}/{total_papers} "
          f"({100 * papers_with_tasks / total_papers:.1f}%)")
    print(f"Papers with multiple tasks: {multi_task}/{total_papers} "
          f"({100 * multi_task / total_papers:.1f}%)")

    # Top combinations
    if combo_counts:
        print(f"\nTop Task Combinations (papers with 2+ tasks):")
        print(f"{'Combination':<55}{'Papers':>8}{'%':>8}")
        print("-" * 71)
        for combo, n in combo_counts.most_common(15):
            pct = 100 * n / total_papers
            print(f"{combo:<55}{n:>8}{pct:>7.1f}%")

    # =====================================================================
    # SECTION 2: TIME TRENDS
    # =====================================================================

    # --- Absolute counts table ---
    print()
    print("=" * 100)
    print("ABSOLUTE COUNTS: Papers per chip task per year")
    print("=" * 100)
    header = f"{'Task':<30}" + "".join(f"{y:>6}" for y in all_years) + f"{'Total':>7}"
    print(header)
    print("-" * len(header))
    for task in all_tasks:
        vals = [task_year[task].get(y, 0) for y in all_years]
        row_str = f"{LABEL.get(task, task):<30}" + "".join(f"{v:>6}" for v in vals)
        row_str += f"{sum(vals):>7}"
        print(row_str)
    # Totals row
    totals = [papers_by_year[y] for y in all_years]
    print("-" * len(header))
    print(f"{'ALL PAPERS':<30}" + "".join(f"{t:>6}" for t in totals) + f"{sum(totals):>7}")

    # --- Percentage share table ---
    print()
    print("=" * 100)
    print("SHARE: Task as % of each year's papers")
    print("=" * 100)
    header = f"{'Task':<30}" + "".join(f"{y:>6}" for y in all_years)
    print(header)
    print("-" * len(header))
    for task in all_tasks:
        parts = []
        for y in all_years:
            n = task_year[task].get(y, 0)
            total_y = papers_by_year[y]
            if n == 0:
                parts.append(f"{'—':>6}")
            else:
                pct = 100 * n / total_y
                parts.append(f"{pct:>5.0f}%")
        print(f"{LABEL.get(task, task):<30}" + "".join(parts))

    # --- Trend summary ---
    print()
    print("=" * 100)
    print("TREND SUMMARY")
    print("=" * 100)
    print(f"{'Task':<30}{'Total':>7}{'Recent 3yr':>11}{'Recent %':>10}  {'Trend'}")
    print("-" * 90)
    for task in all_tasks:
        total = sum(task_year[task].values())
        recent = sum(task_year[task].get(y, 0) for y in all_years[-3:])
        recent_pct = 100 * recent / total if total > 0 else 0
        label = trend_label(task_year[task], all_years)
        print(f"{LABEL.get(task, task):<30}{total:>7}{recent:>11}{recent_pct:>9.0f}%  {label}")


if __name__ == "__main__":
    main()
