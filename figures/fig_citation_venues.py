"""Figure: Citation impact by venue — horizontal bar with N annotation."""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from collections import defaultdict
import matplotlib.pyplot as plt
from plot_style import (apply_style, save_figure, format_axes, DOUBLE_COL,
                        COLORS, SHORT_VENUE, VENUE_ALIASES,
                        merge_csv_json, is_survey)


def main():
    apply_style()
    papers = merge_csv_json()

    venue_cites = defaultdict(list)
    for p in papers:
        if is_survey(p["title"]):
            continue
        venue = p["source"]
        venue_cites[venue].append(p["cited_by_count"])

    # Sort by mean citations
    venue_sorted = sorted(venue_cites.items(),
                          key=lambda x: -(sum(x[1]) / len(x[1])))

    labels = [SHORT_VENUE.get(v, v[:25]) for v, _ in venue_sorted]
    means = [sum(c) / len(c) for _, c in venue_sorted]
    ns = [len(c) for _, c in venue_sorted]

    fig, ax = plt.subplots(figsize=(DOUBLE_COL * 0.55, 3.0))

    y_pos = range(len(labels))
    bars = ax.barh(y_pos, means, color=COLORS[0], height=0.65)
    ax.set_yticks(y_pos)
    ax.set_yticklabels(labels, fontsize=7)
    ax.invert_yaxis()
    ax.set_xlabel("Mean Citations per Paper")
    ax.set_title("Citation Impact by Venue (surveys excluded)")
    format_axes(ax)

    # Add N annotation
    for bar, n in zip(bars, ns):
        ax.text(bar.get_width() + 0.2, bar.get_y() + bar.get_height() / 2,
                f"N={n}", va="center", ha="left", fontsize=6.5, color="gray")

    fig.tight_layout()
    save_figure(fig, "fig_citation_venues")


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
