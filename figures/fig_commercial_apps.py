"""Figure: Commercial application areas — separate single-column plots for totals and trends."""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from collections import Counter, defaultdict
import matplotlib.pyplot as plt
from matplotlib.ticker import FixedLocator
from plot_style import (apply_style, save_figure, format_axes, SINGLE_COL,
                        COLORS, COLOR_OTHER, CAT_LABEL, COMMERCIAL_CATS,
                        load_csv_papers, classify_commercial)


def main():
    apply_style()
    papers = load_csv_papers()

    cat_counts = Counter()
    papers_by_year = Counter()
    cat_year = defaultdict(Counter)
    for p in papers:
        papers_by_year[p["year"]] += 1
        cat = classify_commercial(p["chip_tasks"], p["title"])
        cat_counts[cat] += 1
        cat_year[cat][p["year"]] += 1

    all_years = sorted(papers_by_year)
    active_cats = sorted([c for c in COMMERCIAL_CATS if cat_counts[c] > 0],
                         key=lambda c: -cat_counts[c])

    # ── Horizontal bar ─────────────────────────────────────────────────────
    fig_h = max(2.5, len(active_cats) * 0.28 + 1.0)
    fig, ax = plt.subplots(figsize=(SINGLE_COL, fig_h))
    labels = [CAT_LABEL[c] for c in active_cats]
    values = [cat_counts[c] for c in active_cats]
    y_pos = range(len(active_cats))

    bars = ax.barh(y_pos, values, color=COLORS[0], height=0.6)
    ax.invert_yaxis()
    ax.set_xlabel("Number of Papers")
    ax.set_title("Application Area Totals")
    format_axes(ax)
    ax.yaxis.set_major_locator(FixedLocator(list(y_pos)))
    ax.set_yticklabels(labels, fontsize=7)
    for bar, val in zip(bars, values):
        ax.text(bar.get_width() + 0.3, bar.get_y() + bar.get_height() / 2,
                str(val), va="center", ha="left", fontsize=6.5)
    fig.tight_layout()
    save_figure(fig, "fig_commercial_apps_totals")

    # ── Stacked area over time ─────────────────────────────────────────────
    fig, ax = plt.subplots(figsize=(SINGLE_COL, 3.2))
    top_cats = active_cats[:6]
    other_cats = active_cats[6:]

    stacks = []
    stack_labels = []
    stack_colors = []
    for i, cat in enumerate(top_cats):
        stacks.append([cat_year[cat].get(y, 0) for y in all_years])
        stack_labels.append(CAT_LABEL[cat])
        stack_colors.append(COLORS[i % len(COLORS)])

    if other_cats:
        other_vals = [sum(cat_year[c].get(y, 0) for c in other_cats) for y in all_years]
        stacks.append(other_vals)
        stack_labels.append("Other")
        stack_colors.append(COLOR_OTHER)

    ax.stackplot(all_years, *stacks, labels=stack_labels,
                 colors=stack_colors, alpha=0.85)
    ax.set_xlabel("Year")
    ax.set_ylabel("Number of Papers")
    ax.set_title("Application Area Over Time")
    ax.legend(loc="upper left", fontsize=6, ncol=1)
    ax.set_xticks(all_years)
    ax.set_xticklabels([str(y) for y in all_years], rotation=45, ha="right")
    format_axes(ax)
    fig.tight_layout()
    save_figure(fig, "fig_commercial_apps_trends")


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
