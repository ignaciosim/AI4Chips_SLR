"""Figure: Venue prevalence — separate single-column plots for totals and trends."""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from collections import Counter, defaultdict
import matplotlib.pyplot as plt
from matplotlib.ticker import FixedLocator
from plot_style import (apply_style, save_figure, format_axes, SINGLE_COL,
                        COLORS, SHORT_VENUE, load_csv_papers)


def main():
    apply_style()
    papers = load_csv_papers()

    venue_counts = Counter()
    papers_by_year = Counter()
    venue_year = defaultdict(Counter)
    for p in papers:
        papers_by_year[p["year"]] += 1
        venue = p["source"]
        venue_counts[venue] += 1
        venue_year[venue][p["year"]] += 1

    all_years = sorted(papers_by_year)
    ranked = venue_counts.most_common()
    top5 = [v for v, _ in ranked[:5]]

    # ── Horizontal bar ─────────────────────────────────────────────────────
    venues = [v for v, _ in ranked]
    fig_h = max(2.5, len(venues) * 0.28 + 1.0)
    fig, ax = plt.subplots(figsize=(SINGLE_COL, fig_h))
    labels = [SHORT_VENUE.get(v, v[:25]) for v in venues]
    values = [c for _, c in ranked]
    y_pos = range(len(venues))

    bars = ax.barh(y_pos, values, color=COLORS[0], height=0.7)
    ax.invert_yaxis()
    ax.set_xlabel("Number of Papers")
    ax.set_title("Venue Totals")
    format_axes(ax)
    ax.yaxis.set_major_locator(FixedLocator(list(y_pos)))
    ax.set_yticklabels(labels, fontsize=6.5)
    for bar, val in zip(bars, values):
        ax.text(bar.get_width() + 0.3, bar.get_y() + bar.get_height() / 2,
                str(val), va="center", ha="left", fontsize=6.5)
    fig.tight_layout()
    save_figure(fig, "fig_venues_totals")

    # ── Multi-line top 5 ───────────────────────────────────────────────────
    fig, ax = plt.subplots(figsize=(SINGLE_COL, 3.2))
    for i, v in enumerate(top5):
        counts = [venue_year[v].get(y, 0) for y in all_years]
        ax.plot(all_years, counts, marker="o", color=COLORS[i],
                label=SHORT_VENUE.get(v, v[:20]), linewidth=1.2, markersize=3)

    ax.set_xlabel("Year")
    ax.set_ylabel("Number of Papers")
    ax.set_title("Top 5 Venues Over Time")
    ax.legend(loc="upper left", fontsize=6)
    ax.set_xticks(all_years)
    ax.set_xticklabels([str(y) for y in all_years], rotation=45, ha="right")
    format_axes(ax)
    fig.tight_layout()
    save_figure(fig, "fig_venues_trends")


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
