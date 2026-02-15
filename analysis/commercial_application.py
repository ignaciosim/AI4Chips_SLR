"""Commercial application area analysis for the AI4Chips high-confidence corpus.

Classifies each paper into a commercial application area using chip_task
entity tags, lifecycle stage, and title keywords.

Categories:
  - EDA                    Physical design & logic synthesis tools
                           (placement, routing, timing, synthesis, DSE, power, hotspot)
  - Analog/Mixed-Signal    Analog & mixed-signal design automation
                           (analog circuit design, transistor sizing)
  - Manufacturing          Fab process, lithography, yield, wafer, defect
  - Modeling & Simulation  Device/circuit modeling, calibration, compact models
  - Test & Diagnosis       Test generation, fault diagnosis, verification
  - Reliability            Aging, degradation, electromigration, soft errors, thermal
  - Security               Hardware trojans, PUFs, counterfeit detection

Outputs:
  1. Overall totals — category counts and shares
  2. Time trends — absolute counts, yearly share, and trend classification
"""

import os

_DEFAULT_DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scopus_out7")

import argparse
import csv
from collections import Counter, defaultdict

# ── Known entity keys ─────────────────────────────────────────────────────

ALL_TASK_KEYS = {
    "placement", "routing", "timing_analysis", "logic_synthesis",
    "power_analysis", "design_space_exploration", "analog_circuit_design",
    "verification", "calibration", "lithography_optimization",
    "hotspot_detection", "defect_detection", "yield_prediction",
    "wafer_map_analysis", "process_optimization", "test_generation",
    "fault_diagnosis", "reliability_analysis", "thermal_management",
    "security_analysis",
}

# ── Task-to-category mapping ─────────────────────────────────────────────
# Each chip_task key maps to a primary commercial area.

TASK_TO_CAT = {
    # EDA — physical design & logic synthesis
    "placement":                "eda",
    "routing":                  "eda",
    "timing_analysis":          "eda",
    "logic_synthesis":          "eda",
    "design_space_exploration": "eda",
    "power_analysis":           "eda",
    "hotspot_detection":        "eda",

    # Analog / Mixed-Signal
    "analog_circuit_design":    "analog_ms",

    # Manufacturing
    "lithography_optimization": "manufacturing",
    "process_optimization":     "manufacturing",
    "yield_prediction":         "manufacturing",
    "wafer_map_analysis":       "manufacturing",
    "defect_detection":         "manufacturing",

    # Modeling & Simulation
    "calibration":              "modeling_sim",

    # Test & Diagnosis
    "test_generation":          "test_diag",
    "fault_diagnosis":          "test_diag",
    "verification":             "test_diag",

    # Reliability
    "reliability_analysis":     "reliability",
    "thermal_management":       "reliability",

    # Security
    "security_analysis":        "security",
}

# ── Title keyword fallback (for papers whose tasks don't resolve clearly) ─

TITLE_KW_CAT = [
    # EDA
    ("eda", [
        "placement", "routing", "floor plan", "floorplan",
        "timing closure", "timing analysis", "static timing",
        "logic synthesis", "high-level synthesis", "hls",
        "power grid", "ir drop", "power delivery",
        "design space exploration", "dse",
        "standard cell", "cell library",
    ]),
    # Analog/MS
    ("analog_ms", [
        "analog", "mixed-signal", "mixed signal",
        "adc", "dac", "pll", "op-amp", "opamp", "ota", "lna", "vco",
        "amplifier design", "transistor sizing", "analog ic",
        "rf circuit", "rf design", "rfic",
    ]),
    # Manufacturing
    ("manufacturing", [
        "lithography", "opc", "mask optimization", "inverse lithography",
        "yield prediction", "yield enhancement", "yield optimization",
        "wafer map", "wafer bin", "wafer-level",
        "defect detection", "defect classification",
        "process control", "process optimization",
        "etch", "cmp", "deposition", "metrology",
        "virtual metrology",
    ]),
    # Modeling & Simulation
    ("modeling_sim", [
        "compact model", "spice model", "device model",
        "parameter extraction", "model extraction",
        "circuit modeling", "device characterization",
        "surrogate model", "metamodel",
        "simulation acceleration",
    ]),
    # Test & Diagnosis
    ("test_diag", [
        "test generation", "atpg", "test pattern",
        "fault diagnosis", "fault localization",
        "verification", "formal verification",
        "coverage prediction", "debug",
    ]),
    # Reliability
    ("reliability", [
        "reliability", "aging", "degradation", "electromigration",
        "bti", "nbti", "hci", "tddb", "wear-out",
        "soft error", "seu", "single event upset",
        "fault injection", "fault tolerance",
        "failure rate", "lifetime prediction",
        "thermal management", "thermal-aware",
    ]),
    # Security
    ("security", [
        "hardware trojan", "trojan detection",
        "counterfeit", "puf", "physically unclonable",
        "side-channel", "side channel",
    ]),
]


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


def classify_commercial(row):
    """Return a commercial application category for the paper.

    Strategy:
      1. Map each chip_task to its commercial category via TASK_TO_CAT.
      2. If exactly one category dominates, use it.
      3. If multiple categories tie, use priority ordering.
      4. If no chip_tasks resolved, fall back to title keywords.
    """
    tasks = parse_chip_tasks(row)
    title = row[3].lower()

    # Collect category votes from chip_tasks
    cat_votes = Counter()
    for t in tasks:
        cat = TASK_TO_CAT.get(t)
        if cat:
            cat_votes[cat] += 1

    if cat_votes:
        # Return the category with the most task votes
        # On ties, use priority: eda > analog_ms > manufacturing > modeling_sim > test_diag > reliability > security
        priority = ["eda", "analog_ms", "manufacturing", "modeling_sim",
                     "test_diag", "reliability", "security"]
        top_count = cat_votes.most_common(1)[0][1]
        for cat in priority:
            if cat_votes.get(cat, 0) == top_count:
                return cat

    # Fallback: title keywords
    for cat, keywords in TITLE_KW_CAT:
        if any(kw in title for kw in keywords):
            return cat

    return "other"


# ── Display ──────────────────────────────────────────────────────────────

CATEGORIES = [
    "eda", "analog_ms", "manufacturing", "modeling_sim",
    "test_diag", "reliability", "security", "other",
]

CAT_LABEL = {
    "eda":              "EDA",
    "analog_ms":        "Analog/Mixed-Signal",
    "manufacturing":    "Manufacturing",
    "modeling_sim":     "Modeling & Simulation",
    "test_diag":        "Test & Diagnosis",
    "reliability":      "Reliability",
    "security":         "Security",
    "other":            "Other",
}


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
    cat_year = defaultdict(Counter)

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

            cat = classify_commercial(row)
            cat_counts[cat] += 1
            cat_year[cat][year] += 1

    all_years = sorted(papers_by_year)
    # Only show categories that have papers
    active_cats = [c for c in CATEGORIES if cat_counts[c] > 0]

    # =====================================================================
    # SECTION 1: OVERALL TOTALS
    # =====================================================================
    print("=" * 70)
    print(f"COMMERCIAL APPLICATION AREA  (N = {total_papers} high-confidence ai4chips papers)")
    print("=" * 70)
    print(f"{'Application Area':<25}{'Papers':>8}{'% of Total':>12}{'Rank':>6}")
    print("-" * 51)
    for rank, cat in enumerate(sorted(active_cats, key=lambda c: -cat_counts[c]), 1):
        n = cat_counts[cat]
        pct = 100 * n / total_papers
        print(f"{CAT_LABEL[cat]:<25}{n:>8}{pct:>11.1f}%{rank:>6}")
    print("-" * 51)
    print(f"{'TOTAL':<25}{total_papers:>8}{'100.0%':>12}")

    # =====================================================================
    # SECTION 2: TIME TRENDS
    # =====================================================================

    # --- Absolute counts table ---
    print()
    print("=" * 100)
    print("ABSOLUTE COUNTS: Papers per application area per year")
    print("=" * 100)
    header = f"{'Application Area':<25}" + "".join(f"{y:>6}" for y in all_years) + f"{'Total':>7}"
    print(header)
    print("-" * len(header))
    for cat in active_cats:
        vals = [cat_year[cat].get(y, 0) for y in all_years]
        row_str = f"{CAT_LABEL[cat]:<25}" + "".join(f"{v:>6}" for v in vals)
        row_str += f"{sum(vals):>7}"
        print(row_str)
    totals = [papers_by_year[y] for y in all_years]
    print("-" * len(header))
    print(f"{'ALL PAPERS':<25}" + "".join(f"{t:>6}" for t in totals) + f"{sum(totals):>7}")

    # --- Percentage share table ---
    print()
    print("=" * 100)
    print("SHARE: Application area as % of each year's papers")
    print("=" * 100)
    header = f"{'Application Area':<25}" + "".join(f"{y:>6}" for y in all_years)
    print(header)
    print("-" * len(header))
    for cat in active_cats:
        parts = []
        for y in all_years:
            n = cat_year[cat].get(y, 0)
            total_y = papers_by_year[y]
            if n == 0:
                parts.append(f"{'—':>6}")
            else:
                pct = 100 * n / total_y
                parts.append(f"{pct:>5.0f}%")
        print(f"{CAT_LABEL[cat]:<25}" + "".join(parts))

    # --- Trend summary ---
    print()
    print("=" * 100)
    print("TREND SUMMARY")
    print("=" * 100)
    print(f"{'Application Area':<25}{'Total':>7}{'Recent 3yr':>11}{'Recent %':>10}  {'Trend'}")
    print("-" * 80)
    for cat in active_cats:
        total = sum(cat_year[cat].values())
        recent = sum(cat_year[cat].get(y, 0) for y in all_years[-3:])
        recent_pct = 100 * recent / total if total > 0 else 0
        label = trend_label(cat_year[cat], all_years)
        print(f"{CAT_LABEL[cat]:<25}{total:>7}{recent:>11}{recent_pct:>9.0f}%  {label}")


if __name__ == "__main__":
    main()
