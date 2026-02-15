"""Figure: AI method prevalence — separate single-column plots for totals and trends."""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from collections import Counter, defaultdict
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.ticker import FixedLocator
from plot_style import (apply_style, save_figure, format_axes, SINGLE_COL,
                        COLORS, COLOR_OTHER, load_csv_papers)


def main():
    apply_style()
    papers = load_csv_papers()

    # Aggregate
    tag_counts = Counter()
    papers_by_year = Counter()
    method_year = defaultdict(Counter)
    for p in papers:
        papers_by_year[p["year"]] += 1
        for t in p["method_tags"]:
            tag_counts[t] += 1
            method_year[t][p["year"]] += 1

    all_years = sorted(papers_by_year)
    ranked = tag_counts.most_common()
    top6 = [m for m, _ in ranked[:6]]

    # ── Horizontal bar: all methods ────────────────────────────────────────
    methods = [m for m, _ in ranked]
    fig_h = max(2.5, len(methods) * 0.28 + 1.0)
    fig, ax = plt.subplots(figsize=(SINGLE_COL, fig_h))
    values = [c for _, c in ranked]
    y_pos = range(len(methods))

    bars = ax.barh(y_pos, values, color=COLORS[0], height=0.7)
    ax.invert_yaxis()
    ax.set_xlabel("Number of Papers")
    ax.set_title("AI Method Totals")
    format_axes(ax)
    ax.yaxis.set_major_locator(FixedLocator(list(y_pos)))
    ax.set_yticklabels(methods, fontsize=7)
    for bar, val in zip(bars, values):
        ax.text(bar.get_width() + 0.3, bar.get_y() + bar.get_height() / 2,
                str(val), va="center", ha="left", fontsize=6.5)
    fig.tight_layout()
    save_figure(fig, "fig_ai_methods_totals")

    # ── Stacked area: top 6 method share% over time ───────────────────────
    fig, ax = plt.subplots(figsize=(SINGLE_COL, 3.2))
    share_data = {}
    for m in top6:
        share_data[m] = [100 * method_year[m].get(y, 0) / papers_by_year[y]
                         if papers_by_year[y] > 0 else 0
                         for y in all_years]
    other_share = []
    for i, y in enumerate(all_years):
        top6_total = sum(method_year[m].get(y, 0) for m in top6)
        all_tagged = sum(method_year[m].get(y, 0) for m in method_year)
        other_share.append(100 * (all_tagged - top6_total) / papers_by_year[y]
                           if papers_by_year[y] > 0 else 0)

    stacks = [share_data[m] for m in top6] + [other_share]
    labels = top6 + ["Other"]
    colors = COLORS[:6] + [COLOR_OTHER]

    ax.stackplot(all_years, *stacks, labels=labels, colors=colors, alpha=0.85)
    ax.set_xlabel("Year")
    ax.set_ylabel("Share of Papers (%)")
    ax.set_title("Top 6 Methods — Share Over Time")
    ax.legend(loc="upper left", fontsize=6, ncol=1)
    ax.set_xticks(all_years)
    ax.set_xticklabels([str(y) for y in all_years], rotation=45, ha="right")
    format_axes(ax)
    fig.tight_layout()
    save_figure(fig, "fig_ai_methods_trends")


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
