"""Figure: Publication volume per year with cumulative line and CAGR annotation."""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from collections import Counter
import matplotlib.pyplot as plt
from plot_style import (apply_style, save_figure, format_axes, DOUBLE_COL,
                        COLORS, INK_MUTED, load_csv_papers, cagr, year_axis)


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
    # The axis titles say which series they belong to; colouring the words
    # as well is a dashboard habit that just adds two more hues to the page.
    ax1.set_ylabel("Papers per year")
    format_axes(ax1)
    year_axis(ax1, all_years)

    # Value labels are a lookup aid, not the data: muted, and only on the
    # endpoints and the peak. A number over every bar duplicates what the grid
    # already says and crowds the cumulative line where the two cross.
    mark = {0, len(vals) - 1, max(range(len(vals)), key=lambda i: vals[i])}
    for i, (bar, val) in enumerate(zip(bars, vals)):
        if i in mark and val > 0:
            ax1.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 1.5,
                     str(val), ha="center", va="bottom", fontsize=7,
                     color=INK_MUTED)

    # Cumulative line on secondary axis
    ax2 = ax1.twinx()
    ax2.plot(all_years, cumulative, color=COLORS[1], marker="o",
             markersize=2.8, linewidth=1.1, zorder=4)
    ax2.set_ylabel("Cumulative papers")
    ax2.spines["top"].set_visible(False)

    # CAGR annotation
    if rate is not None:
        ax1.text(0.02, 0.93, f"CAGR {rate:+.0%} ({start_y}\u2013{end_y})",
                 transform=ax1.transAxes, fontsize=8, color=INK_MUTED,
                 ha="left", va="top")

    ax1.set_title("AI-for-Chips publication volume (N = {})".format(len(papers)))
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
