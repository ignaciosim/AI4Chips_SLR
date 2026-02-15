"""Geographic analysis of the AI4Chips high-confidence corpus.

Uses the JSON file for affiliation/country data and the CSV for method tags
(the JSON only stores the first method tag per paper).

Sections:
  1. Country prevalence — overall ranking
  2. Country time trends — absolute counts, share%, trend labels
  3. AI method adoption by top countries
  4. Emerging regions — countries outside traditional leaders (US, China, Europe)

A paper is counted once per unique country in its affiliation list.
"""

import os

_DEFAULT_DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scopus_out7")

import argparse
import csv
import json
from collections import Counter, defaultdict

# ── Region definitions ────────────────────────────────────────────────────

ESTABLISHED_LEADERS = {"China", "United States"}

EUROPE = {
    "Germany", "France", "United Kingdom", "Netherlands", "Belgium",
    "Switzerland", "Austria", "Italy", "Denmark", "Greece", "Portugal",
    "Sweden", "Finland", "Spain", "Norway", "Ireland", "Poland",
    "Czech Republic", "Hungary", "Romania",
}

EAST_ASIA_TIGERS = {"South Korea", "Taiwan", "Japan", "Singapore", "Hong Kong"}

EMERGING = {
    "India", "Iran", "Brazil", "Turkey", "Tunisia",
    "Armenia", "United Arab Emirates",
    # Add more as they appear in data
}

def get_region(country):
    if country in ESTABLISHED_LEADERS:
        return country  # show individually
    if country in EUROPE:
        return "Europe"
    if country in EAST_ASIA_TIGERS:
        return "East Asia (excl. China)"
    if country == "Canada":
        return "Canada"
    return "Emerging & Other"


# ── Chip task keys (from slr_ontology.py) ─────────────────────────────────

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


# ── Parse method tags and chip tasks from CSV ─────────────────────────────

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
            tasks[doc_id] = list(dict.fromkeys(ctasks))  # dedupe
    return methods, tasks


def trend_label(counts_by_year, all_years):
    """Classify trajectory based on year-by-year counts."""
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
    JSON_PATH = os.path.join(args.datadir, "final_ai4chips_high_only.json")
    CSV_PATH = os.path.join(args.datadir, "final_ai4chips_high_only.csv")

    # ── Load data ─────────────────────────────────────────────────────────
    with open(JSON_PATH, "r", encoding="utf-8") as f:
        papers = json.load(f)

    csv_methods, csv_tasks = load_csv_data(CSV_PATH)

    total_papers = len(papers)
    papers_by_year = Counter()
    country_counts = Counter()
    country_year = defaultdict(Counter)
    region_counts = Counter()
    region_year = defaultdict(Counter)
    country_methods = defaultdict(Counter)   # country -> {method: count}
    country_tasks = defaultdict(Counter)     # country -> {task: count}
    collab_papers = 0
    no_affil = 0

    for p in papers:
        year = p["year"]
        doc_id = p["doc_id"]
        papers_by_year[year] += 1

        affiliations = p.get("affiliations") or []
        countries = set()
        for a in affiliations:
            c = a.get("affiliation-country", "")
            if c:
                countries.add(c)

        if not countries:
            no_affil += 1
            continue

        if len(countries) > 1:
            collab_papers += 1

        methods = csv_methods.get(doc_id, [])
        tasks = csv_tasks.get(doc_id, [])

        for c in countries:
            country_counts[c] += 1
            country_year[c][year] += 1
            for m in methods:
                country_methods[c][m] += 1
            for t in tasks:
                country_tasks[c][t] += 1

            region = get_region(c)
            region_counts[region] += 1
            region_year[region][year] += 1

    all_years = sorted(papers_by_year)
    all_countries = sorted(country_counts, key=lambda c: -country_counts[c])

    # =====================================================================
    # SECTION 1: COUNTRY PREVALENCE
    # =====================================================================
    print("=" * 70)
    print(f"COUNTRY PREVALENCE  (N = {total_papers} papers, {len(all_countries)} countries)")
    print("=" * 70)
    print(f"{'Country':<30}{'Papers':>8}{'% of Total':>12}{'Rank':>6}")
    print("-" * 56)
    for rank, c in enumerate(all_countries, 1):
        n = country_counts[c]
        pct = 100 * n / total_papers
        print(f"{c:<30}{n:>8}{pct:>11.1f}%{rank:>6}")
    print("-" * 56)
    print(f"\nInternational collaborations: {collab_papers}/{total_papers} "
          f"({100 * collab_papers / total_papers:.1f}%)")
    if no_affil:
        print(f"Papers with no affiliation data: {no_affil}")

    # =====================================================================
    # SECTION 2: COUNTRY TIME TRENDS (top 10 countries)
    # =====================================================================
    top_countries = all_countries[:10]

    # --- Absolute counts ---
    print()
    print("=" * 110)
    print("ABSOLUTE COUNTS: Papers per country per year (top 10)")
    print("=" * 110)
    header = f"{'Country':<20}" + "".join(f"{y:>6}" for y in all_years) + f"{'Total':>7}"
    print(header)
    print("-" * len(header))
    for c in top_countries:
        vals = [country_year[c].get(y, 0) for y in all_years]
        row_str = f"{c:<20}" + "".join(f"{v:>6}" for v in vals)
        row_str += f"{sum(vals):>7}"
        print(row_str)
    totals = [papers_by_year[y] for y in all_years]
    print("-" * len(header))
    print(f"{'ALL PAPERS':<20}" + "".join(f"{t:>6}" for t in totals) + f"{sum(totals):>7}")

    # --- Share ---
    print()
    print("=" * 110)
    print("SHARE: Country as % of each year's papers (top 10)")
    print("=" * 110)
    header = f"{'Country':<20}" + "".join(f"{y:>6}" for y in all_years)
    print(header)
    print("-" * len(header))
    for c in top_countries:
        parts = []
        for y in all_years:
            n = country_year[c].get(y, 0)
            total_y = papers_by_year[y]
            if n == 0:
                parts.append(f"{'—':>6}")
            else:
                pct = 100 * n / total_y
                parts.append(f"{pct:>5.0f}%")
        print(f"{c:<20}" + "".join(parts))

    # --- Trend summary ---
    print()
    print("=" * 110)
    print("TREND SUMMARY (top 10 countries)")
    print("=" * 110)
    print(f"{'Country':<20}{'Total':>7}{'Recent 3yr':>11}{'Recent %':>10}  {'Trend'}")
    print("-" * 80)
    for c in top_countries:
        total = sum(country_year[c].values())
        recent = sum(country_year[c].get(y, 0) for y in all_years[-3:])
        recent_pct = 100 * recent / total if total > 0 else 0
        label = trend_label(country_year[c], all_years)
        print(f"{c:<20}{total:>7}{recent:>11}{recent_pct:>9.0f}%  {label}")

    # --- Period comparison: 2015-2020 vs 2021-2025 ---
    early_years = [y for y in all_years if y <= 2020]
    late_years  = [y for y in all_years if y >= 2021]
    early_total = sum(papers_by_year[y] for y in early_years)
    late_total  = sum(papers_by_year[y] for y in late_years)

    print()
    print("=" * 110)
    print(f"PERIOD COMPARISON: 2015-2020 vs 2021-2025 (top 10 countries)")
    print("=" * 110)
    print(f"{'Country':<20}"
          f"{'2015-2020':>10}{'Share':>8}"
          f"{'2021-2025':>12}{'Share':>8}"
          f"{'Change':>10}")
    print("-" * 68)
    for c in top_countries:
        e = sum(country_year[c].get(y, 0) for y in early_years)
        l = sum(country_year[c].get(y, 0) for y in late_years)
        e_pct = 100 * e / early_total if early_total else 0
        l_pct = 100 * l / late_total  if late_total  else 0
        delta = l_pct - e_pct
        sign = "+" if delta > 0 else ""
        print(f"{c:<20}"
              f"{e:>10}{e_pct:>7.1f}%"
              f"{l:>12}{l_pct:>7.1f}%"
              f"{sign}{delta:>9.1f}pp")
    print("-" * 68)
    print(f"{'ALL PAPERS':<20}"
          f"{early_total:>10}{'100.0%':>8}"
          f"{late_total:>12}{'100.0%':>8}")

    # =====================================================================
    # SECTION 3: AI METHOD ADOPTION BY TOP COUNTRIES
    # =====================================================================
    print()
    print("=" * 110)
    print("AI METHOD ADOPTION BY COUNTRY (top 8 countries, methods with 3+ papers)")
    print("=" * 110)

    # Collect all methods that appear across top countries
    top8 = all_countries[:8]
    all_methods_set = set()
    for c in top8:
        for m, cnt in country_methods[c].items():
            if cnt >= 1:
                all_methods_set.add(m)
    # Order methods by global frequency
    global_method_counts = Counter()
    for c in all_countries:
        for m, cnt in country_methods[c].items():
            global_method_counts[m] += cnt
    methods_ordered = sorted(all_methods_set, key=lambda m: -global_method_counts[m])

    # Print as a country × method table (showing counts)
    header = f"{'Method':<28}" + "".join(f"{c[:12]:>13}" for c in top8)
    print(header)
    print("-" * len(header))
    for m in methods_ordered:
        row_str = f"{m:<28}"
        for c in top8:
            cnt = country_methods[c].get(m, 0)
            n_papers = country_counts[c]
            if cnt == 0:
                row_str += f"{'—':>13}"
            else:
                pct = 100 * cnt / n_papers
                row_str += f"{cnt:>4} ({pct:>4.0f}%)" + " "
        print(row_str)

    # Per-country top method (share-based)
    print()
    print("Top method per country (by share of that country's papers):")
    for c in top8:
        if not country_methods[c]:
            continue
        top_m = country_methods[c].most_common(1)[0]
        pct = 100 * top_m[1] / country_counts[c]
        print(f"  {c:<20} {top_m[0]:<28} {top_m[1]:>3} papers ({pct:.0f}%)")

    # =====================================================================
    # SECTION 3b: CHIP TASK PREFERENCE BY COUNTRY (top 8)
    # =====================================================================
    print()
    print("=" * 110)
    print("CHIP TASK PREFERENCE BY COUNTRY (top 8 countries)")
    print("=" * 110)

    # Collect tasks that appear at least once across top8
    global_task_counts = Counter()
    for c in all_countries:
        for t, cnt in country_tasks[c].items():
            global_task_counts[t] += cnt
    tasks_ordered = sorted(global_task_counts, key=lambda t: -global_task_counts[t])

    header = f"{'Chip Task':<20}" + "".join(f"{c[:12]:>13}" for c in top8)
    print(header)
    print("-" * len(header))
    for t in tasks_ordered:
        row_str = f"{TASK_LABEL.get(t, t):<20}"
        for c in top8:
            cnt = country_tasks[c].get(t, 0)
            n_papers = country_counts[c]
            if cnt == 0:
                row_str += f"{'—':>13}"
            else:
                pct = 100 * cnt / n_papers
                row_str += f"{cnt:>4} ({pct:>4.0f}%)" + " "
        print(row_str)

    # Per-country top task
    print()
    print("Top chip task per country (by share of that country's papers):")
    for c in top8:
        if not country_tasks[c]:
            continue
        top_t = country_tasks[c].most_common(1)[0]
        pct = 100 * top_t[1] / country_counts[c]
        print(f"  {c:<20} {TASK_LABEL.get(top_t[0], top_t[0]):<25} {top_t[1]:>3} papers ({pct:.0f}%)")

    # =====================================================================
    # SECTION 4: REGIONAL VIEW
    # =====================================================================
    print()
    print("=" * 110)
    print("REGIONAL DISTRIBUTION")
    print("=" * 110)
    region_order = sorted(region_counts, key=lambda r: -region_counts[r])
    print(f"{'Region':<30}{'Papers':>8}{'% of Total':>12}")
    print("-" * 50)
    for r in region_order:
        n = region_counts[r]
        pct = 100 * n / total_papers
        print(f"{r:<30}{n:>8}{pct:>11.1f}%")

    # Regional time trends
    print()
    header = f"{'Region':<30}" + "".join(f"{y:>6}" for y in all_years) + f"{'Total':>7}"
    print(header)
    print("-" * len(header))
    for r in region_order:
        vals = [region_year[r].get(y, 0) for y in all_years]
        row_str = f"{r:<30}" + "".join(f"{v:>6}" for v in vals)
        row_str += f"{sum(vals):>7}"
        print(row_str)

    print()
    print(f"{'Region':<30}{'Total':>7}{'Recent 3yr':>11}{'Recent %':>10}  {'Trend'}")
    print("-" * 85)
    for r in region_order:
        total = sum(region_year[r].values())
        recent = sum(region_year[r].get(y, 0) for y in all_years[-3:])
        recent_pct = 100 * recent / total if total > 0 else 0
        label = trend_label(region_year[r], all_years)
        print(f"{r:<30}{total:>7}{recent:>11}{recent_pct:>9.0f}%  {label}")

    # =====================================================================
    # SECTION 5: EMERGING REGIONS DETAIL
    # =====================================================================
    print()
    print("=" * 110)
    print("EMERGING & OTHER COUNTRIES — DETAIL")
    print("=" * 110)
    emerging_countries = [c for c in all_countries
                          if c not in ESTABLISHED_LEADERS
                          and c not in EUROPE
                          and c not in EAST_ASIA_TIGERS
                          and c != "Canada"]
    if emerging_countries:
        print(f"{'Country':<22}{'Papers':>7}{'Years':>12}  {'Methods Used'}")
        print("-" * 90)
        for c in emerging_countries:
            n = country_counts[c]
            years_active = sorted(y for y in all_years if country_year[c].get(y, 0) > 0)
            yr_range = f"{years_active[0]}-{years_active[-1]}" if len(years_active) > 1 else str(years_active[0])
            methods = ", ".join(m for m, _ in country_methods[c].most_common(3))
            print(f"{c:<22}{n:>7}{yr_range:>12}  {methods}")

        # Chip task table for emerging countries
        print()
        print("Chip task focus — Emerging & Other countries:")
        emg_with_tasks = [c for c in emerging_countries if country_tasks[c]]
        if emg_with_tasks:
            # Collect tasks present in emerging countries
            emg_task_totals = Counter()
            for c in emg_with_tasks:
                for t, cnt in country_tasks[c].items():
                    emg_task_totals[t] += cnt
            emg_tasks_ordered = sorted(emg_task_totals, key=lambda t: -emg_task_totals[t])

            header = f"{'Chip Task':<22}" + "".join(f"{c[:14]:>15}" for c in emg_with_tasks)
            print(header)
            print("-" * len(header))
            for t in emg_tasks_ordered:
                row_str = f"{TASK_LABEL.get(t, t):<22}"
                for c in emg_with_tasks:
                    cnt = country_tasks[c].get(t, 0)
                    if cnt == 0:
                        row_str += f"{'—':>15}"
                    else:
                        row_str += f"{cnt:>15}"
                print(row_str)
    else:
        print("  (no emerging countries found)")


if __name__ == "__main__":
    main()
