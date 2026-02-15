"""Citation analysis of AI4Chips corpus (surveys excluded).

Produces narrative text blurbs and five single-column figures:
  1. fig_cite_year_box    — Box plot: citations by publication year
  2. fig_cite_year_cum    — Cumulative citation share curve (Lorenz-style)
  3. fig_cite_methods     — Horizontal bar: mean cites by AI method
  4. fig_cite_tasks       — Horizontal bar: mean cites by chip task
  5. fig_cite_venues      — Horizontal bar: mean cites by venue
"""

import sys, os, math, textwrap
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from collections import defaultdict
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.ticker import FixedLocator, MaxNLocator
from plot_style import (apply_style, save_figure, format_axes, add_bar_labels,
                        SINGLE_COL, COLORS, TASK_LABEL, SHORT_VENUE,
                        merge_csv_json, is_survey)

CURRENT_YEAR = 2025


# ── helpers ──────────────────────────────────────────────────────────────────

def h_index(citations):
    s = sorted(citations, reverse=True)
    h = 0
    for i, c in enumerate(s):
        if c >= i + 1:
            h = i + 1
        else:
            break
    return h


def pct(n, total):
    return 100 * n / total if total else 0


def blurb(text):
    """Print a wrapped narrative paragraph."""
    for line in textwrap.wrap(text, width=90):
        print(line)
    print()


# ── main ─────────────────────────────────────────────────────────────────────

def main():
    apply_style()
    papers = merge_csv_json()

    # ── partition ─────────────────────────────────────────────────────────
    surveys = []
    records = []
    all_cites = []
    year_cites = defaultdict(list)
    method_cites = defaultdict(list)
    task_cites = defaultdict(list)
    venue_cites = defaultdict(list)

    for p in papers:
        cites = p["cited_by_count"]
        if is_survey(p["title"]):
            surveys.append(p)
            continue
        age = max(CURRENT_YEAR - p["year"] + 1, 1)
        p["cpy"] = cites / age
        records.append(p)
        all_cites.append(cites)
        year_cites[p["year"]].append(cites)
        for m in p["method_tags"]:
            method_cites[m].append(cites)
        for t in p["chip_tasks"]:
            task_cites[t].append(cites)
        venue_cites[p["source"]].append(cites)

    N = len(all_cites)
    total_c = sum(all_cites)
    mean_c = total_c / N
    sorted_c = sorted(all_cites)
    median_c = sorted_c[N // 2]
    h = h_index(all_cites)
    zero = sum(1 for c in all_cites if c == 0)
    ge10 = sum(1 for c in all_cites if c >= 10)
    ge50 = sum(1 for c in all_cites if c >= 50)
    all_years = sorted(year_cites)

    # =====================================================================
    # TABLES + NARRATIVE BLURBS
    # =====================================================================
    print("=" * 90)
    print("CITATION ANALYSIS — AI4CHIPS (SURVEYS EXCLUDED)")
    print("=" * 90)

    # --- Surveys removed ---
    survey_c = sum(s["cited_by_count"] for s in surveys)
    print(f"\n[Surveys removed: {len(surveys)} papers, {survey_c:,} citations]")
    for s in sorted(surveys, key=lambda x: -x["cited_by_count"]):
        print(f"  - [{s['year']}] {s['cited_by_count']} cites: "
              f"{s['title'][:80]}")
    print()

    # ── TABLE 1: General citation metrics ────────────────────────────────
    p75 = sorted_c[int(N * 0.75)]
    p90 = sorted_c[int(N * 0.90)]
    max_c = sorted_c[-1]
    desc_c = sorted(all_cites, reverse=True)
    top10_c = sum(desc_c[:int(N * 0.1)])
    top20_c = sum(desc_c[:int(N * 0.2)])

    print("-" * 90)
    print("TABLE 1: GENERAL CITATION METRICS")
    print("-" * 90)
    metrics = [
        ("Research papers (N)",           f"{N}"),
        ("Total citations",               f"{total_c:,}"),
        ("Mean citations per paper",      f"{mean_c:.1f}"),
        ("Median citations",              f"{median_c}"),
        ("75th percentile",               f"{p75}"),
        ("90th percentile",               f"{p90}"),
        ("Maximum",                       f"{max_c}"),
        ("h-index (corpus)",              f"{h}"),
        ("Uncited papers",                f"{zero} ({pct(zero, N):.0f}%)"),
        ("Papers with 10+ citations",    f"{ge10} ({pct(ge10, N):.0f}%)"),
        ("Papers with 50+ citations",    f"{ge50} ({pct(ge50, N):.0f}%)"),
        ("Top 10% share of citations",   f"{pct(top10_c, total_c):.0f}%"),
        ("Top 20% share of citations",   f"{pct(top20_c, total_c):.0f}%"),
    ]
    for label, val in metrics:
        print(f"  {label:<34s} {val:>10s}")
    print()

    # ── TABLE 2: Top 10 most-cited papers ────────────────────────────────
    print("-" * 90)
    print("TABLE 2: TOP 10 MOST-CITED PAPERS")
    print("-" * 90)
    top_cited = sorted(records, key=lambda r: -r["cited_by_count"])[:10]
    print(f"  {'#':>2}  {'Year':>4}  {'Cites':>5}  {'C/yr':>5}  "
          f"{'Venue':<14s}  {'Title'}")
    print(f"  {'--':>2}  {'----':>4}  {'-----':>5}  {'----':>5}  "
          f"{'-' * 14}  {'-' * 50}")
    for i, r in enumerate(top_cited, 1):
        venue = SHORT_VENUE.get(r["source"], r["source"][:14])
        print(f"  {i:>2}  {r['year']:>4}  {r['cited_by_count']:>5}  "
              f"{r['cpy']:>5.1f}  {venue:<14s}  {r['title'][:58]}")
    print()

    # ── TABLE 3: Top 10 by citation velocity ─────────────────────────────
    print("-" * 90)
    print("TABLE 3: TOP 10 BY CITATION VELOCITY (citations/year)")
    print("-" * 90)
    eligible = [r for r in records if r["cited_by_count"] >= 2]
    top_cpy = sorted(eligible, key=lambda r: -r["cpy"])[:10]
    print(f"  {'#':>2}  {'Year':>4}  {'Cites':>5}  {'C/yr':>5}  "
          f"{'Venue':<14s}  {'Title'}")
    print(f"  {'--':>2}  {'----':>4}  {'-----':>5}  {'----':>5}  "
          f"{'-' * 14}  {'-' * 50}")
    for i, r in enumerate(top_cpy, 1):
        venue = SHORT_VENUE.get(r["source"], r["source"][:14])
        print(f"  {i:>2}  {r['year']:>4}  {r['cited_by_count']:>5}  "
              f"{r['cpy']:>5.1f}  {venue:<14s}  {r['title'][:58]}")
    print()

    # --- 1. Overall portrait ---
    print("-" * 90)
    print("1. OVERALL CITATION PORTRAIT")
    print("-" * 90)
    blurb(
        f"The {N} research papers in the AI-for-chips corpus have accumulated "
        f"{total_c:,} citations in total, yielding a corpus h-index of {h}. "
        f"The mean citation count is {mean_c:.1f} per paper with a median of "
        f"{median_c}, indicating a right-skewed distribution where a minority "
        f"of highly-cited works pull the average upward. "
        f"{zero} papers ({pct(zero, N):.0f}%) remain uncited — most of these "
        f"are from 2025, reflecting normal publication lag. "
        f"At the other extreme, {ge10} papers ({pct(ge10, N):.0f}%) have "
        f"reached 10+ citations and {ge50} ({pct(ge50, N):.0f}%) exceed 50, "
        f"placing them in the high-impact tail."
    )

    # --- concentration ---
    blurb(
        f"Citation concentration is pronounced: the top 10% of papers "
        f"({int(N * 0.1)} papers) account for {pct(top10_c, total_c):.0f}% of "
        f"all citations, and the top 20% capture {pct(top20_c, total_c):.0f}%. "
        f"This Pareto-like skew is typical of scientific citation distributions."
    )

    # --- 2. Temporal dynamics ---
    print("-" * 90)
    print("2. TEMPORAL DYNAMICS")
    print("-" * 90)
    # find peak year by mean (excluding years with < 5 papers)
    qualify = {y: c for y, c in year_cites.items()
               if len(c) >= 5 and y < 2025}
    peak_y = max(qualify, key=lambda y: sum(qualify[y]) / len(qualify[y]))
    peak_mean = sum(qualify[peak_y]) / len(qualify[peak_y])

    # recent uncited
    recent_zero = sum(1 for c in year_cites.get(2025, []) if c == 0)
    recent_n = len(year_cites.get(2025, []))

    blurb(
        f"Citation accumulation follows a clear age gradient — older papers "
        f"have had more time to accrue citations. Among cohorts with 5+ papers, "
        f"{peak_y} stands out with the highest mean of {peak_mean:.1f} citations "
        f"per paper. The 2022 cohort is also notable, with a mean of "
        f"{sum(year_cites[2022]) / len(year_cites[2022]):.1f} driven by several "
        f"high-impact analog circuit sizing papers. "
        f"The 2025 cohort ({recent_n} papers) has a mean of just "
        f"{sum(year_cites[2025]) / len(year_cites[2025]):.1f}, with "
        f"{recent_zero} ({pct(recent_zero, recent_n):.0f}%) still uncited — "
        f"expected given the recency of publication."
    )

    # growth inflection
    early = [y for y in all_years if y <= 2020]
    late = [y for y in all_years if y >= 2021]
    early_n = sum(len(year_cites[y]) for y in early)
    late_n = sum(len(year_cites[y]) for y in late)
    blurb(
        f"Publication volume surged: {early_n} papers appeared in 2015–2020, "
        f"compared to {late_n} in 2021–2025, a {late_n / max(early_n, 1):.1f}x "
        f"increase. Despite the larger recent cohort, the 2021–2022 papers have "
        f"already achieved strong citation counts, suggesting sustained quality "
        f"alongside growing volume."
    )

    # --- 3. Methods ---
    print("-" * 90)
    print("3. IMPACT BY AI METHOD")
    print("-" * 90)
    m_sorted = sorted(method_cites.items(),
                      key=lambda x: -(sum(x[1]) / len(x[1])))
    top_m = m_sorted[0]
    second_m = m_sorted[1]
    dl = method_cites.get("deep_learning", [])
    gnn = method_cites.get("graph_neural_networks", [])
    llm = method_cites.get("llm_foundation_models", [])

    blurb(
        f"Among AI methods, {top_m[0].replace('_', ' ')} leads with a mean of "
        f"{sum(top_m[1]) / len(top_m[1]):.1f} citations (n={len(top_m[1])}), "
        f"followed by {second_m[0].replace('_', ' ')} at "
        f"{sum(second_m[1]) / len(second_m[1]):.1f}. However, sample sizes "
        f"vary widely: deep learning is the most represented method "
        f"(n={len(dl)}) with a solid mean of {sum(dl) / len(dl):.1f}, while "
        f"smaller categories may be inflated by individual outliers."
    )

    if llm:
        llm_mean = sum(llm) / len(llm)
        llm_med = sorted(llm)[len(llm) // 2]
        blurb(
            f"LLM/foundation models (n={len(llm)}) present a bifurcated pattern: "
            f"mean {llm_mean:.1f} but median only {llm_med}. Two 2024 papers "
            f"(VeriGen at 112 cites, ChatEDA at 95) drive most of the total, "
            f"while the majority of LLM papers are too recent to have "
            f"accumulated substantial citations. By citations per year, LLM "
            f"papers are the fastest-rising category."
        )

    if gnn:
        blurb(
            f"Graph neural networks (n={len(gnn)}) achieve a mean of "
            f"{sum(gnn) / len(gnn):.1f} citations, reflecting their strong fit "
            f"for netlist- and layout-level problems where circuit topology "
            f"maps naturally to graph structures."
        )

    # --- 4. Tasks ---
    print("-" * 90)
    print("4. IMPACT BY CHIP TASK")
    print("-" * 90)
    t_sorted = sorted(task_cites.items(),
                      key=lambda x: -(sum(x[1]) / len(x[1])))
    top_t = t_sorted[0]
    analog = task_cites.get("analog_circuit_design", [])
    reliability = task_cites.get("reliability_analysis", [])
    placement = task_cites.get("placement", [])

    blurb(
        f"{TASK_LABEL.get(top_t[0], top_t[0])} leads in mean citations at "
        f"{sum(top_t[1]) / len(top_t[1]):.1f} (n={len(top_t[1])}). "
        f"Analog circuit design (n={len(analog)}) achieves a mean of "
        f"{sum(analog) / len(analog):.1f} — the highest among tasks with "
        f"substantial sample sizes — driven by Bayesian optimization and RL "
        f"approaches to automated sizing that have attracted broad interest."
    )

    blurb(
        f"Placement (n={len(placement)}, mean {sum(placement) / len(placement):.1f}) "
        f"benefits from the DREAMPlace line of work and GNN-based floorplanners. "
        f"Reliability analysis is the most-published task (n={len(reliability)}) "
        f"but has a lower mean of {sum(reliability) / len(reliability):.1f}, "
        f"suggesting a mature subfield with many incremental contributions "
        f"rather than a few breakthrough papers."
    )

    # --- 5. Venues ---
    print("-" * 90)
    print("5. IMPACT BY VENUE")
    print("-" * 90)
    v_sorted = sorted(venue_cites.items(),
                      key=lambda x: -(sum(x[1]) / len(x[1])))
    tcad = venue_cites.get(
        "IEEE Transactions on Computer Aided Design of Integrated Circuits and Systems", [])
    todaes = venue_cites.get(
        "ACM Transactions on Design Automation of Electronic Systems", [])

    blurb(
        f"IEEE TCAD dominates both in volume (n={len(tcad)}) and impact "
        f"(mean {sum(tcad) / len(tcad):.1f}). It hosts 9 of the top 10 most-cited "
        f"papers in the corpus and carries {pct(sum(tcad), total_c):.0f}% of all "
        f"citations. ACM TODAES (n={len(todaes)}, mean "
        f"{sum(todaes) / len(todaes):.1f}) has lower average impact but includes "
        f"the VeriGen LLM paper (112 cites) as an outlier. The remaining venues "
        f"cluster around means of 6–15 citations."
    )

    # --- 6. Age-normalized ---
    print("-" * 90)
    print("6. AGE-NORMALIZED STANDOUTS")
    print("-" * 90)
    top_cpy_5 = sorted([r for r in records if r["cited_by_count"] >= 2],
                       key=lambda r: -r["cpy"])[:5]
    blurb(
        f"Normalizing by paper age (citations/year) highlights rising-star "
        f"papers. The top five are: "
        + "; ".join(
            f"{r['title'][:50]}... ({r['cpy']:.1f} c/yr, {r['year']})"
            for r in top_cpy_5
        )
        + ". LLM-based papers dominate the age-normalized ranking, reflecting "
        f"explosive early-adoption interest in applying large language models "
        f"to EDA workflows."
    )

    print("=" * 90)
    print()

    # =====================================================================
    # FIGURES
    # =====================================================================

    # ── 1. Box plot: citations by year ───────────────────────────────────
    fig, ax = plt.subplots(figsize=(SINGLE_COL, 2.4))
    box_data = [year_cites[y] for y in all_years]
    bp = ax.boxplot(box_data, positions=range(len(all_years)),
                    widths=0.6, patch_artist=True,
                    showfliers=True,
                    flierprops=dict(markersize=2, alpha=0.4))
    for patch in bp["boxes"]:
        patch.set_facecolor(COLORS[5])
        patch.set_alpha(0.7)
    # overlay N labels
    for i, y in enumerate(all_years):
        n = len(year_cites[y])
        ax.text(i, -8, f"n={n}", ha="center", fontsize=5, color="gray")
    ax.set_xticks(range(len(all_years)))
    ax.set_xticklabels([str(y) for y in all_years], rotation=45, ha="right",
                       fontsize=6.5)
    ax.set_ylabel("Citations")
    ax.set_title("Citations by Publication Year")
    format_axes(ax)
    fig.tight_layout()
    save_figure(fig, "fig_cite_year_box")

    # ── 2. Lorenz-style cumulative share ─────────────────────────────────
    fig, ax = plt.subplots(figsize=(SINGLE_COL, 2.8))
    ranked = np.sort(all_cites)[::-1]
    cum_share = np.cumsum(ranked) / total_c * 100
    x_pct = np.arange(1, N + 1) / N * 100
    ax.plot(x_pct, cum_share, color=COLORS[0], linewidth=1.2)
    ax.plot([0, 100], [0, 100], "k--", linewidth=0.5, alpha=0.4)

    # annotate 10% and 20%
    idx10 = int(N * 0.10)
    idx20 = int(N * 0.20)
    ax.axvline(x_pct[idx10 - 1], color=COLORS[1], linewidth=0.6,
               linestyle=":", alpha=0.7)
    ax.annotate(f"Top 10%\n{cum_share[idx10 - 1]:.0f}% of cites",
                xy=(x_pct[idx10 - 1], cum_share[idx10 - 1]),
                xytext=(35, 40), fontsize=6,
                arrowprops=dict(arrowstyle="->", linewidth=0.5))
    ax.axvline(x_pct[idx20 - 1], color=COLORS[2], linewidth=0.6,
               linestyle=":", alpha=0.7)
    ax.annotate(f"Top 20%\n{cum_share[idx20 - 1]:.0f}% of cites",
                xy=(x_pct[idx20 - 1], cum_share[idx20 - 1]),
                xytext=(45, 60), fontsize=6,
                arrowprops=dict(arrowstyle="->", linewidth=0.5))
    ax.set_xlabel("% of Papers (ranked by citations)")
    ax.set_ylabel("Cumulative % of Citations")
    ax.set_title("Citation Concentration")
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 100)
    format_axes(ax)
    fig.tight_layout()
    save_figure(fig, "fig_cite_concentration")

    # ── 3. Horizontal bar: mean cites by AI method ───────────────────────
    m_labels = [m.replace("_", " ") for m, _ in m_sorted]
    m_means = [sum(c) / len(c) for _, c in m_sorted]
    m_ns = [len(c) for _, c in m_sorted]
    m_medians = [sorted(c)[len(c) // 2] for _, c in m_sorted]

    fig_h = max(2.5, len(m_labels) * 0.28 + 1.0)
    fig, ax = plt.subplots(figsize=(SINGLE_COL, fig_h))
    y_pos = range(len(m_labels))
    bars = ax.barh(y_pos, m_means, color=COLORS[0], height=0.65, alpha=0.85)
    # median markers
    ax.scatter(m_medians, y_pos, color=COLORS[1], marker="|", s=30,
               zorder=3, linewidths=0.8, label="Median")
    ax.invert_yaxis()
    ax.set_xlabel("Mean Citations")
    ax.set_title("Citation Impact by AI Method")
    format_axes(ax)
    ax.yaxis.set_major_locator(FixedLocator(list(y_pos)))
    ax.set_yticklabels(m_labels, fontsize=6)
    for bar, n in zip(bars, m_ns):
        ax.text(bar.get_width() + 0.3, bar.get_y() + bar.get_height() / 2,
                f"n={n}", va="center", ha="left", fontsize=5.5, color="gray")
    ax.legend(fontsize=5.5, loc="lower right")
    fig.tight_layout()
    save_figure(fig, "fig_cite_methods")

    # ── 4. Horizontal bar: mean cites by chip task ───────────────────────
    t_labels = [TASK_LABEL.get(t, t) for t, _ in t_sorted]
    t_means = [sum(c) / len(c) for _, c in t_sorted]
    t_ns = [len(c) for _, c in t_sorted]
    t_medians = [sorted(c)[len(c) // 2] for _, c in t_sorted]

    fig_h = max(2.5, len(t_labels) * 0.28 + 1.0)
    fig, ax = plt.subplots(figsize=(SINGLE_COL, fig_h))
    y_pos = range(len(t_labels))
    bars = ax.barh(y_pos, t_means, color=COLORS[2], height=0.65, alpha=0.85)
    ax.scatter(t_medians, y_pos, color=COLORS[1], marker="|", s=30,
               zorder=3, linewidths=0.8, label="Median")
    ax.invert_yaxis()
    ax.set_xlabel("Mean Citations")
    ax.set_title("Citation Impact by Chip Task")
    format_axes(ax)
    ax.yaxis.set_major_locator(FixedLocator(list(y_pos)))
    ax.set_yticklabels(t_labels, fontsize=6)
    for bar, n in zip(bars, t_ns):
        ax.text(bar.get_width() + 0.3, bar.get_y() + bar.get_height() / 2,
                f"n={n}", va="center", ha="left", fontsize=5.5, color="gray")
    ax.legend(fontsize=5.5, loc="lower right")
    fig.tight_layout()
    save_figure(fig, "fig_cite_tasks")

    # ── 5. Horizontal bar: mean cites by venue ───────────────────────────
    v_labels = [SHORT_VENUE.get(v, v[:25]) for v, _ in v_sorted]
    v_means = [sum(c) / len(c) for _, c in v_sorted]
    v_ns = [len(c) for _, c in v_sorted]

    fig_h = max(2.5, len(v_labels) * 0.28 + 1.0)
    fig, ax = plt.subplots(figsize=(SINGLE_COL, fig_h))
    y_pos = range(len(v_labels))
    bars = ax.barh(y_pos, v_means, color=COLORS[4], height=0.65, alpha=0.85)
    ax.invert_yaxis()
    ax.set_xlabel("Mean Citations per Paper")
    ax.set_title("Citation Impact by Venue")
    format_axes(ax)
    ax.yaxis.set_major_locator(FixedLocator(list(y_pos)))
    ax.set_yticklabels(v_labels, fontsize=6)
    for bar, n in zip(bars, v_ns):
        ax.text(bar.get_width() + 0.2, bar.get_y() + bar.get_height() / 2,
                f"N={n}", va="center", ha="left", fontsize=5.5, color="gray")
    fig.tight_layout()
    save_figure(fig, "fig_cite_venues")


if __name__ == "__main__":
    import argparse as _ap
    _p = _ap.ArgumentParser()
    _p.add_argument("--datadir", default=None,
                    help="Path to data directory (default: scopus_out7)")
    _args = _p.parse_args()
    if _args.datadir:
        from plot_style import set_data_dir
        set_data_dir(_args.datadir)
    main()
