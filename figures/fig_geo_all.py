"""Figure: Geographic analysis of FULL corpus — separate single-column plots
for top 15 countries bar and regional stacked area."""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from collections import Counter, defaultdict
import matplotlib.pyplot as plt
from matplotlib.ticker import FixedLocator
from plot_style import (apply_style, save_figure, format_axes, SINGLE_COL,
                        COLORS, COLOR_OTHER, VENUE_ALIASES,
                        load_jsonl_papers, get_region)


def main():
    apply_style()
    records = load_jsonl_papers()

    papers_by_year = Counter()
    country_counts = Counter()
    region_year = defaultdict(Counter)

    for rec in records:
        entry = rec.get("entry", {})
        year = rec.get("year")
        papers_by_year[year] += 1

        affiliations = entry.get("affiliation") or []
        countries = set()
        for a in affiliations:
            c = a.get("affiliation-country", "")
            if c:
                countries.add(c)

        for c in countries:
            country_counts[c] += 1
            region = get_region(c)
            region_year[region][year] += 1

    all_years = sorted(papers_by_year)
    all_countries = sorted(country_counts, key=lambda c: -country_counts[c])
    top15 = all_countries[:15]

    # ── Horizontal bar: top 15 ─────────────────────────────────────────────
    fig_h = max(2.5, len(top15) * 0.28 + 1.0)
    fig, ax = plt.subplots(figsize=(SINGLE_COL, fig_h))
    labels = top15
    values = [country_counts[c] for c in top15]
    y_pos = range(len(top15))
    bars = ax.barh(y_pos, values, color=COLORS[0], height=0.7)
    ax.invert_yaxis()
    ax.set_xlabel("Number of Papers")
    ax.set_title("Top 15 Countries (N={})".format(len(records)))
    format_axes(ax)
    ax.yaxis.set_major_locator(FixedLocator(list(y_pos)))
    ax.set_yticklabels(labels, fontsize=6)
    for bar, val in zip(bars, values):
        ax.text(bar.get_width() + 5, bar.get_y() + bar.get_height() / 2,
                str(val), va="center", ha="left", fontsize=6)
    fig.tight_layout()
    save_figure(fig, "fig_geo_all_totals")

    # ── Stacked area: regional distribution ────────────────────────────────
    fig, ax = plt.subplots(figsize=(SINGLE_COL, 3.5))
    region_order = sorted(region_year, key=lambda r: -sum(region_year[r].values()))
    top_regions = region_order[:5]
    other_regions = region_order[5:]

    stacks = []
    stack_labels = []
    stack_colors = []
    for i, r in enumerate(top_regions):
        stacks.append([region_year[r].get(y, 0) for y in all_years])
        stack_labels.append(r)
        stack_colors.append(COLORS[i])

    if other_regions:
        other_vals = [sum(region_year[r].get(y, 0) for r in other_regions) for y in all_years]
        stacks.append(other_vals)
        stack_labels.append("Other")
        stack_colors.append(COLOR_OTHER)

    ax.stackplot(all_years, *stacks, labels=stack_labels,
                 colors=stack_colors, alpha=0.85)
    ax.set_xlabel("Year")
    ax.set_ylabel("Number of Papers")
    ax.set_title("Regional Distribution Over Time")
    ax.legend(loc="upper left", fontsize=6)
    ax.set_xticks(all_years[::2])
    format_axes(ax)
    fig.tight_layout()
    save_figure(fig, "fig_geo_all_regions")


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
