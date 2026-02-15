"""Citation impact analysis for the AI4Chips high-confidence corpus.

Uses JSON for citation counts and affiliations, CSV for method tags and
chip tasks (JSON only stores the first method tag).

Sections:
  1. Overall citation statistics
  2. Citations by publication year (mean, median, h-index per cohort)
  3. Most-cited papers (top 20)
  4. Citation impact by AI method
  5. Citation impact by chip task
  6. Citation impact by venue
  7. Age-normalized impact (citations per year since publication)
"""

import os

_DEFAULT_DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scopus_out7")

import argparse
import csv
import json
import math
from collections import Counter, defaultdict

CURRENT_YEAR = 2025  # latest full year in corpus

# ── Chip task keys ────────────────────────────────────────────────────────

TASK_KEYS = {
    "placement", "routing", "timing_analysis", "logic_synthesis",
    "power_analysis", "design_space_exploration", "analog_circuit_design",
    "verification", "calibration", "lithography_optimization",
    "hotspot_detection", "defect_detection", "yield_prediction",
    "wafer_map_analysis", "process_optimization", "test_generation",
    "fault_diagnosis", "reliability_analysis", "thermal_management",
    "security_analysis",
}

TASK_LABEL = {
    "placement": "Placement",
    "routing": "Routing",
    "timing_analysis": "Timing Analysis",
    "logic_synthesis": "Logic Synthesis",
    "power_analysis": "Power Analysis",
    "design_space_exploration": "Design Space Expl.",
    "analog_circuit_design": "Analog Circuit",
    "verification": "Verification",
    "calibration": "Calibration",
    "lithography_optimization": "Lithography Opt.",
    "hotspot_detection": "Hotspot Detection",
    "defect_detection": "Defect Detection",
    "yield_prediction": "Yield Prediction",
    "wafer_map_analysis": "Wafer Map Analysis",
    "process_optimization": "Process Opt.",
    "test_generation": "Test Generation",
    "fault_diagnosis": "Fault Diagnosis",
    "reliability_analysis": "Reliability",
    "thermal_management": "Thermal Mgmt",
    "security_analysis": "Security",
}

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


def load_csv_data(csv_path):
    """Return dicts: doc_id -> method tags, doc_id -> chip task keys."""
    methods = {}
    tasks = {}
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        next(reader)
        for row in reader:
            doc_id = row[0].strip()
            if not doc_id:
                continue
            mtags = []
            ctasks = []
            for val in row[8:]:
                v = val.strip()
                if not v:
                    continue
                if ":" in v:
                    key = v.split(":")[0].strip()
                    if key in TASK_KEYS:
                        ctasks.append(key)
                else:
                    mtags.append(v)
            methods[doc_id] = mtags
            tasks[doc_id] = list(dict.fromkeys(ctasks))
    return methods, tasks


def h_index(citations):
    """Compute h-index for a list of citation counts."""
    s = sorted(citations, reverse=True)
    h = 0
    for i, c in enumerate(s):
        if c >= i + 1:
            h = i + 1
        else:
            break
    return h


def percentile(values, p):
    """Compute p-th percentile (0-100) of a sorted list."""
    if not values:
        return 0
    k = (len(values) - 1) * p / 100
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return values[int(k)]
    return values[f] * (c - k) + values[c] * (k - f)


def stats_row(citations):
    """Return (n, mean, median, p75, p90, max, h, total) for a group."""
    if not citations:
        return (0, 0, 0, 0, 0, 0, 0, 0)
    s = sorted(citations)
    n = len(s)
    mean = sum(s) / n
    med = percentile(s, 50)
    p75 = percentile(s, 75)
    p90 = percentile(s, 90)
    mx = s[-1]
    h = h_index(s)
    total = sum(s)
    return (n, mean, med, p75, p90, mx, h, total)


def print_stats_table(label_col, groups, col_width=25):
    """Print a formatted stats table. groups: list of (label, [citations])."""
    header = (f"{label_col:<{col_width}}"
              f"{'N':>5}{'Mean':>7}{'Med':>6}{'P75':>6}{'P90':>6}"
              f"{'Max':>6}{'h-idx':>6}{'Total':>8}")
    print(header)
    print("-" * len(header))
    for label, cites in groups:
        n, mean, med, p75, p90, mx, h, total = stats_row(cites)
        print(f"{label:<{col_width}}"
              f"{n:>5}{mean:>7.1f}{med:>6.0f}{p75:>6.0f}{p90:>6.0f}"
              f"{mx:>6}{h:>6}{total:>8}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--datadir", default=_DEFAULT_DATA_DIR,
                        help="Path to data directory (default: scopus_out7)")
    args = parser.parse_args()
    JSON_PATH = os.path.join(args.datadir, "final_ai4chips_high_only.json")
    CSV_PATH = os.path.join(args.datadir, "final_ai4chips_high_only.csv")

    # ── Load data ─────────────────────────────────────────────────────────
    with open(JSON_PATH, "r", encoding="utf-8") as f:
        papers = json.load(f)

    csv_methods, csv_tasks = load_csv_data(CSV_PATH)

    all_cites = []
    year_cites = defaultdict(list)
    method_cites = defaultdict(list)
    task_cites = defaultdict(list)
    venue_cites = defaultdict(list)
    paper_records = []  # for top-cited listing

    for p in papers:
        doc_id = p["doc_id"]
        year = p["year"]
        cites = int(p.get("cited_by_count") or 0)
        venue = VENUE_ALIASES.get(p["publication"], p["publication"])
        title = p["title"]

        all_cites.append(cites)
        year_cites[year].append(cites)
        venue_cites[venue].append(cites)

        methods = csv_methods.get(doc_id, [])
        tasks = csv_tasks.get(doc_id, [])

        for m in methods:
            method_cites[m].append(cites)
        for t in tasks:
            task_cites[t].append(cites)

        age = max(CURRENT_YEAR - year + 1, 1)
        cpy = cites / age
        paper_records.append({
            "doc_id": doc_id, "year": year, "title": title,
            "venue": venue, "cites": cites, "methods": methods,
            "tasks": tasks, "cites_per_year": cpy,
        })

    all_years = sorted(year_cites)
    s = sorted(all_cites)
    total_papers = len(all_cites)

    # =====================================================================
    # SECTION 1: OVERALL STATISTICS
    # =====================================================================
    print("=" * 80)
    print(f"CITATION IMPACT ANALYSIS  (N = {total_papers} papers)")
    print("=" * 80)
    n, mean, med, p75, p90, mx, h, total = stats_row(all_cites)
    print(f"  Total citations:       {total:,}")
    print(f"  Mean per paper:        {mean:.1f}")
    print(f"  Median:                {med:.0f}")
    print(f"  75th percentile:       {p75:.0f}")
    print(f"  90th percentile:       {p90:.0f}")
    print(f"  Max:                   {mx}")
    print(f"  h-index (corpus):      {h}")
    print(f"  Papers with 0 cites:   {sum(1 for c in all_cites if c == 0)} "
          f"({100 * sum(1 for c in all_cites if c == 0) / total_papers:.0f}%)")
    print(f"  Papers with 10+ cites: {sum(1 for c in all_cites if c >= 10)} "
          f"({100 * sum(1 for c in all_cites if c >= 10) / total_papers:.0f}%)")
    print(f"  Papers with 50+ cites: {sum(1 for c in all_cites if c >= 50)} "
          f"({100 * sum(1 for c in all_cites if c >= 50) / total_papers:.0f}%)")

    # =====================================================================
    # SECTION 2: CITATIONS BY PUBLICATION YEAR
    # =====================================================================
    print()
    print("=" * 80)
    print("CITATIONS BY PUBLICATION YEAR")
    print("=" * 80)
    year_groups = [(str(y), year_cites[y]) for y in all_years]
    print_stats_table("Year", year_groups, col_width=8)

    # =====================================================================
    # SECTION 3: MOST-CITED PAPERS (top 20)
    # =====================================================================
    print()
    print("=" * 100)
    print("TOP 20 MOST-CITED PAPERS")
    print("=" * 100)
    top_cited = sorted(paper_records, key=lambda r: -r["cites"])[:20]
    for i, r in enumerate(top_cited, 1):
        mstr = ", ".join(r["methods"]) if r["methods"] else "—"
        print(f"  {i:>2}. [{r['year']}] {r['cites']:>4} cites  "
              f"({r['cites_per_year']:.1f}/yr)  {r['title'][:75]}")
        print(f"      {SHORT_VENUE.get(r['venue'], r['venue'])}  |  Methods: {mstr}")
        print()

    # =====================================================================
    # SECTION 4: CITATION IMPACT BY AI METHOD
    # =====================================================================
    print("=" * 80)
    print("CITATION IMPACT BY AI METHOD")
    print("=" * 80)
    method_groups = sorted(method_cites.items(), key=lambda x: -sum(x[1]) / len(x[1]))
    method_groups = [(m, c) for m, c in method_groups]
    print_stats_table("AI Method", method_groups, col_width=28)

    # =====================================================================
    # SECTION 5: CITATION IMPACT BY CHIP TASK
    # =====================================================================
    print()
    print("=" * 80)
    print("CITATION IMPACT BY CHIP TASK")
    print("=" * 80)
    task_groups = sorted(task_cites.items(), key=lambda x: -sum(x[1]) / len(x[1]))
    task_groups = [(TASK_LABEL.get(t, t), c) for t, c in task_groups]
    print_stats_table("Chip Task", task_groups, col_width=25)

    # =====================================================================
    # SECTION 6: CITATION IMPACT BY VENUE
    # =====================================================================
    print()
    print("=" * 80)
    print("CITATION IMPACT BY VENUE")
    print("=" * 80)
    venue_groups = sorted(venue_cites.items(), key=lambda x: -sum(x[1]) / len(x[1]))
    venue_groups = [(SHORT_VENUE.get(v, v), c) for v, c in venue_groups]
    print_stats_table("Venue", venue_groups, col_width=25)

    # =====================================================================
    # SECTION 7: AGE-NORMALIZED IMPACT (citations per year)
    # =====================================================================
    print()
    print("=" * 100)
    print("AGE-NORMALIZED: TOP 20 BY CITATIONS PER YEAR (min 2 citations)")
    print("=" * 100)
    eligible = [r for r in paper_records if r["cites"] >= 2]
    top_cpy = sorted(eligible, key=lambda r: -r["cites_per_year"])[:20]
    print(f"  {'#':>3}  {'Year':>4}  {'Cites':>5}  {'C/Yr':>5}  {'Title':<70}  {'Methods'}")
    print(f"  {'-' * 3}  {'-' * 4}  {'-' * 5}  {'-' * 5}  {'-' * 70}  {'-' * 20}")
    for i, r in enumerate(top_cpy, 1):
        mstr = ", ".join(r["methods"][:3]) if r["methods"] else "—"
        print(f"  {i:>3}  {r['year']:>4}  {r['cites']:>5}  "
              f"{r['cites_per_year']:>5.1f}  {r['title'][:70]:<70}  {mstr}")

    # =====================================================================
    # SECTION 8: CITATION BRACKETS BY YEAR
    # =====================================================================
    print()
    print("=" * 80)
    print("CITATION BRACKETS: Papers by citation range per year")
    print("=" * 80)
    brackets = [
        ("0", lambda c: c == 0),
        ("1-5", lambda c: 1 <= c <= 5),
        ("6-20", lambda c: 6 <= c <= 20),
        ("21-50", lambda c: 21 <= c <= 50),
        ("50+", lambda c: c > 50),
    ]
    header = f"{'Bracket':<10}" + "".join(f"{y:>6}" for y in all_years) + f"{'Total':>7}"
    print(header)
    print("-" * len(header))
    for label, test in brackets:
        vals = [sum(1 for c in year_cites[y] if test(c)) for y in all_years]
        row_str = f"{label:<10}" + "".join(f"{v:>6}" for v in vals) + f"{sum(vals):>7}"
        print(row_str)
    totals = [len(year_cites[y]) for y in all_years]
    print("-" * len(header))
    print(f"{'ALL':<10}" + "".join(f"{t:>6}" for t in totals) + f"{sum(totals):>7}")


if __name__ == "__main__":
    main()
