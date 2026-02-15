"""Analog vs Digital target analysis for the AI4Chips high-confidence corpus.

Classifies each paper as targeting analog, digital, or domain-agnostic
circuit domains using two signal sources:
  1. chip_task entity tags (from classify_scopus.py)
  2. title keyword matching

Categories:
  - analog:           clear analog/mixed-signal signal
  - digital:          clear digital/logic signal
  - both:             signals for both analog and digital
  - domain-agnostic:  no clear analog/digital signal (reliability, fab, etc.)

Outputs:
  1. Overall totals — category counts and shares
  2. Time trends — absolute counts, yearly share, and trend classification
"""

import os

_DEFAULT_DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scopus_out7")

import argparse
import csv
from collections import Counter, defaultdict

# ── Classification signals ────────────────────────────────────────────────

# Chip-task keys that indicate analog domain
ANALOG_TASKS = {"analog_circuit_design", "calibration"}

# Chip-task keys that indicate digital domain
DIGITAL_TASKS = {
    "placement", "routing", "timing_analysis", "logic_synthesis",
    "test_generation", "verification", "hotspot_detection",
}

# Title keywords (matched case-insensitively)
ANALOG_TITLE_KW = [
    "analog", "mixed-signal", "mixed signal", "adc", "dac",
    "pll", "phase-locked", "phase locked",
    "op-amp", "opamp", "operational amplifier",
    "amplifier design", "amplifier circuit",
    "ota", "lna", "vco", "mixer",
    "rf circuit", "rf design", "rf ic", "rfic",
    "transistor sizing", "analog ic", "analog layout",
    "comparator", "bandgap", "ldo", "voltage regulator",
    "oscillator design", "ring oscillator",
]

DIGITAL_TITLE_KW = [
    "digital", "fpga", "rtl", "verilog", "vhdl", "systemverilog",
    "netlist", "gate-level", "gate level",
    "flip-flop", "flip flop", "flop",
    "asic", "standard cell", "cell library",
    "soc ", "system-on-chip", "system on chip",
    "microprocessor", "processor design",
    "noc", "network-on-chip", "network on chip",
    "cache", "boolean", "logic circuit", "logic gate",
]

# Known chip-task keys for entity parsing
ALL_TASK_KEYS = {
    "placement", "routing", "timing_analysis", "logic_synthesis",
    "power_analysis", "design_space_exploration", "analog_circuit_design",
    "verification", "calibration", "lithography_optimization",
    "hotspot_detection", "defect_detection", "yield_prediction",
    "wafer_map_analysis", "process_optimization", "test_generation",
    "fault_diagnosis", "reliability_analysis", "thermal_management",
    "security_analysis",
}


def parse_chip_tasks(row):
    """Extract chip_task keys from a raw CSV row, handling column overflow."""
    tasks = []
    for val in row[8:]:
        v = val.strip()
        if not v or ":" not in v:
            continue
        key = v.split(":")[0].strip()
        if key in ALL_TASK_KEYS:
            tasks.append(key)
    return list(dict.fromkeys(tasks))


def classify_analog_digital(row):
    """Return one of: analog, digital, both, domain-agnostic."""
    tasks = set(parse_chip_tasks(row))
    title = row[3].lower()

    has_analog = bool(tasks & ANALOG_TASKS) or any(kw in title for kw in ANALOG_TITLE_KW)
    has_digital = bool(tasks & DIGITAL_TASKS) or any(kw in title for kw in DIGITAL_TITLE_KW)

    if has_analog and has_digital:
        return "both"
    elif has_analog:
        return "analog"
    elif has_digital:
        return "digital"
    else:
        return "domain-agnostic"


def trend_label(counts_by_year, all_years):
    """Classify a category's trajectory based on its year-by-year counts."""
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


# Display order
CATEGORIES = ["analog", "digital", "both", "domain-agnostic"]
CAT_LABEL = {
    "analog": "Analog",
    "digital": "Digital",
    "both": "Both",
    "domain-agnostic": "Domain-Agnostic",
}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--datadir", default=_DEFAULT_DATA_DIR,
                        help="Path to data directory (default: scopus_out7)")
    args = parser.parse_args()
    CSV_PATH = os.path.join(args.datadir, "final_ai4chips_high_only.csv")

    # ── Parse ─────────────────────────────────────────────────────────────
    total_papers = 0
    cat_counts = Counter()
    papers_by_year = Counter()
    cat_year = defaultdict(Counter)  # category -> {year: count}

    with open(CSV_PATH, "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        next(reader)
        for row in reader:
            doc_id = row[0].strip()
            if not doc_id:
                continue
            total_papers += 1
            year = int(row[2])
            papers_by_year[year] += 1

            cat = classify_analog_digital(row)
            cat_counts[cat] += 1
            cat_year[cat][year] += 1

    all_years = sorted(papers_by_year)

    # =====================================================================
    # SECTION 1: OVERALL TOTALS
    # =====================================================================
    print("=" * 70)
    print(f"ANALOG vs DIGITAL TARGET  (N = {total_papers} high-confidence ai4chips papers)")
    print("=" * 70)
    print(f"{'Category':<20}{'Papers':>8}{'% of Total':>12}")
    print("-" * 40)
    for cat in CATEGORIES:
        n = cat_counts[cat]
        pct = 100 * n / total_papers
        print(f"{CAT_LABEL[cat]:<20}{n:>8}{pct:>11.1f}%")
    print("-" * 40)
    print(f"{'TOTAL':<20}{total_papers:>8}{'100.0%':>12}")

    # Analog + Digital only breakdown
    ad_total = cat_counts["analog"] + cat_counts["digital"] + cat_counts["both"]
    if ad_total > 0:
        print(f"\nAmong papers with a clear analog/digital signal (N = {ad_total}):")
        for cat in ["analog", "digital", "both"]:
            n = cat_counts[cat]
            pct = 100 * n / ad_total
            print(f"  {CAT_LABEL[cat]:<16}{n:>8}{pct:>11.1f}%")

    # =====================================================================
    # SECTION 2: TIME TRENDS
    # =====================================================================

    # --- Absolute counts table ---
    print()
    print("=" * 100)
    print("ABSOLUTE COUNTS: Papers per category per year")
    print("=" * 100)
    header = f"{'Category':<20}" + "".join(f"{y:>6}" for y in all_years) + f"{'Total':>7}"
    print(header)
    print("-" * len(header))
    for cat in CATEGORIES:
        vals = [cat_year[cat].get(y, 0) for y in all_years]
        row_str = f"{CAT_LABEL[cat]:<20}" + "".join(f"{v:>6}" for v in vals)
        row_str += f"{sum(vals):>7}"
        print(row_str)
    totals = [papers_by_year[y] for y in all_years]
    print("-" * len(header))
    print(f"{'ALL PAPERS':<20}" + "".join(f"{t:>6}" for t in totals) + f"{sum(totals):>7}")

    # --- Percentage share table ---
    print()
    print("=" * 100)
    print("SHARE: Category as % of each year's papers")
    print("=" * 100)
    header = f"{'Category':<20}" + "".join(f"{y:>6}" for y in all_years)
    print(header)
    print("-" * len(header))
    for cat in CATEGORIES:
        parts = []
        for y in all_years:
            n = cat_year[cat].get(y, 0)
            total_y = papers_by_year[y]
            if n == 0:
                parts.append(f"{'—':>6}")
            else:
                pct = 100 * n / total_y
                parts.append(f"{pct:>5.0f}%")
        print(f"{CAT_LABEL[cat]:<20}" + "".join(parts))

    # --- Trend summary ---
    print()
    print("=" * 100)
    print("TREND SUMMARY")
    print("=" * 100)
    print(f"{'Category':<20}{'Total':>7}{'Recent 3yr':>11}{'Recent %':>10}  {'Trend'}")
    print("-" * 75)
    for cat in CATEGORIES:
        total = sum(cat_year[cat].values())
        recent = sum(cat_year[cat].get(y, 0) for y in all_years[-3:])
        recent_pct = 100 * recent / total if total > 0 else 0
        label = trend_label(cat_year[cat], all_years)
        print(f"{CAT_LABEL[cat]:<20}{total:>7}{recent:>11}{recent_pct:>9.0f}%  {label}")


if __name__ == "__main__":
    main()
