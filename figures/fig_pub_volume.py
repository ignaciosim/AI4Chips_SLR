"""Figure: Publication volume per year with cumulative line and CAGR annotation."""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from collections import Counter
import matplotlib.pyplot as plt
from plot_style import (apply_style, save_figure, format_axes, DOUBLE_COL,
                        COLORS, load_csv_papers, cagr)


def main():
    apply_style()
    papers = load_csv_papers()
    years_list = [p["year"] for p in papers]
    counts = Counter(years_list)
    all_years = sorted(counts)
    vals = [counts[y] for y in all_years]

    # Cumulative
    cumulative = []
    s = 0
    for v in vals:
        s += v
        cumulative.append(s)

    # CAGR
    # Find first year with >0 papers
    start_y = all_years[0]
    end_y = all_years[-1]
    periods = end_y - start_y
    rate = cagr(counts[start_y], counts[end_y], periods)

    fig, ax1 = plt.subplots(figsize=(DOUBLE_COL, 3.0))

    # Bar chart
    bars = ax1.bar(all_years, vals, color=COLORS[0], width=0.7, zorder=3)
    ax1.set_xlabel("Publication Year")
    ax1.set_ylabel("Number of Papers", color=COLORS[0])
    ax1.tick_params(axis="y", labelcolor=COLORS[0])
    format_axes(ax1)
    ax1.set_xticks(all_years)
    ax1.set_xticklabels([str(y) for y in all_years], rotation=45, ha="right")

    # Add count labels on bars
    for bar, val in zip(bars, vals):
        if val > 0:
            ax1.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.5,
                     str(val), ha="center", va="bottom", fontsize=7)

    # Cumulative line on secondary axis
    ax2 = ax1.twinx()
    ax2.plot(all_years, cumulative, color=COLORS[1], marker="o",
             markersize=4, linewidth=1.5, zorder=4)
    ax2.set_ylabel("Cumulative Papers", color=COLORS[1])
    ax2.tick_params(axis="y", labelcolor=COLORS[1])
    ax2.spines["top"].set_visible(False)

    # CAGR annotation
    if rate is not None:
        ax1.annotate(f"CAGR = {rate:+.0%}\n({start_y}\u2013{end_y})",
                     xy=(all_years[-1], vals[-1]),
                     xytext=(-50, 20), textcoords="offset points",
                     fontsize=8, fontstyle="italic",
                     arrowprops=dict(arrowstyle="->", color="gray", lw=0.8))

    ax1.set_title("AI4Chips Publication Volume (N = {})".format(len(papers)))
    fig.tight_layout()
    save_figure(fig, "fig_pub_volume")


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
