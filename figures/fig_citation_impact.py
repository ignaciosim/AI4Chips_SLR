"""Figure: Citation impact (surveys excluded) — separate single-column plots for
box plot by year, mean cites by AI method, and mean cites by chip task."""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from collections import defaultdict
import matplotlib.pyplot as plt
from matplotlib.ticker import FixedLocator
from plot_style import (apply_style, save_figure, format_axes, SINGLE_COL,
                        COLORS, TASK_LABEL, VENUE_ALIASES,
                        merge_csv_json, is_survey)


def main():
    apply_style()
    papers = merge_csv_json()

    year_cites = defaultdict(list)
    method_cites = defaultdict(list)
    task_cites = defaultdict(list)

    for p in papers:
        if is_survey(p["title"]):
            continue
        cites = p["cited_by_count"]
        year_cites[p["year"]].append(cites)
        for m in p["method_tags"]:
            method_cites[m].append(cites)
        for t in p["chip_tasks"]:
            task_cites[t].append(cites)

    all_years = sorted(year_cites)

    # ── Box plot: citations by year ────────────────────────────────────────
    fig, ax = plt.subplots(figsize=(SINGLE_COL, 3.5))
    box_data = [year_cites[y] for y in all_years]
    bp = ax.boxplot(box_data, positions=range(len(all_years)),
                    widths=0.6, patch_artist=True,
                    showfliers=True, flierprops=dict(markersize=2, alpha=0.5))
    for patch in bp["boxes"]:
        patch.set_facecolor(COLORS[5])
        patch.set_alpha(0.7)
    ax.set_xticks(range(len(all_years)))
    ax.set_xticklabels([str(y) for y in all_years], rotation=45, ha="right")
    ax.set_xlabel("Publication Year")
    ax.set_ylabel("Citations")
    ax.set_title("Citations by Year")
    format_axes(ax)
    fig.tight_layout()
    save_figure(fig, "fig_citation_boxplot")

    # ── Horizontal bar: mean cites by AI method ────────────────────────────
    method_sorted = sorted(method_cites.items(),
                           key=lambda x: -(sum(x[1]) / len(x[1])))
    m_labels = [m for m, _ in method_sorted]
    m_means = [sum(c) / len(c) for _, c in method_sorted]
    m_ns = [len(c) for _, c in method_sorted]

    fig_h = max(2.5, len(m_labels) * 0.28 + 1.0)
    fig, ax = plt.subplots(figsize=(SINGLE_COL, fig_h))
    y_pos = range(len(m_labels))
    bars = ax.barh(y_pos, m_means, color=COLORS[0], height=0.65)
    ax.invert_yaxis()
    ax.set_xlabel("Mean Citations")
    ax.set_title("Impact by AI Method")
    format_axes(ax)
    ax.yaxis.set_major_locator(FixedLocator(list(y_pos)))
    ax.set_yticklabels(m_labels, fontsize=6)
    for bar, n in zip(bars, m_ns):
        ax.text(bar.get_width() + 0.2, bar.get_y() + bar.get_height() / 2,
                f"n={n}", va="center", ha="left", fontsize=5.5, color="gray")
    fig.tight_layout()
    save_figure(fig, "fig_citation_methods")

    # ── Horizontal bar: mean cites by chip task ────────────────────────────
    task_sorted = sorted(task_cites.items(),
                         key=lambda x: -(sum(x[1]) / len(x[1])))
    t_labels = [TASK_LABEL.get(t, t) for t, _ in task_sorted]
    t_means = [sum(c) / len(c) for _, c in task_sorted]
    t_ns = [len(c) for _, c in task_sorted]

    fig_h = max(2.5, len(t_labels) * 0.28 + 1.0)
    fig, ax = plt.subplots(figsize=(SINGLE_COL, fig_h))
    y_pos = range(len(t_labels))
    bars = ax.barh(y_pos, t_means, color=COLORS[2], height=0.65)
    ax.invert_yaxis()
    ax.set_xlabel("Mean Citations")
    ax.set_title("Impact by Chip Task")
    format_axes(ax)
    ax.yaxis.set_major_locator(FixedLocator(list(y_pos)))
    ax.set_yticklabels(t_labels, fontsize=6)
    for bar, n in zip(bars, t_ns):
        ax.text(bar.get_width() + 0.2, bar.get_y() + bar.get_height() / 2,
                f"n={n}", va="center", ha="left", fontsize=5.5, color="gray")
    fig.tight_layout()
    save_figure(fig, "fig_citation_tasks")


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
