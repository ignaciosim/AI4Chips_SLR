"""Figure: Geographic analysis (ai4chips) — separate single-column plots for
top 10 countries bar, top 5 trends, and period comparison."""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from collections import Counter, defaultdict
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.ticker import FixedLocator
from plot_style import (apply_style, save_figure, format_axes, SINGLE_COL,
                        COLORS, merge_csv_json)


def main():
    apply_style()
    papers = merge_csv_json()

    papers_by_year = Counter()
    country_counts = Counter()
    country_year = defaultdict(Counter)

    for p in papers:
        year = p["year"]
        papers_by_year[year] += 1
        affiliations = p.get("affiliations") or []
        countries = set()
        for a in affiliations:
            c = a.get("affiliation-country", "")
            if c:
                countries.add(c)
        for c in countries:
            country_counts[c] += 1
            country_year[c][year] += 1

    all_years = sorted(papers_by_year)
    all_countries = sorted(country_counts, key=lambda c: -country_counts[c])
    top10 = all_countries[:10]
    top5 = all_countries[:5]

    # ── Horizontal bar: top 10 ─────────────────────────────────────────────
    fig_h = max(2.5, len(top10) * 0.28 + 1.0)
    fig, ax = plt.subplots(figsize=(SINGLE_COL, fig_h))
    labels = top10
    values = [country_counts[c] for c in top10]
    y_pos = range(len(top10))
    bars = ax.barh(y_pos, values, color=COLORS[0], height=0.7)
    ax.invert_yaxis()
    ax.set_xlabel("Papers")
    ax.set_title("Top 10 Countries")
    format_axes(ax)
    ax.yaxis.set_major_locator(FixedLocator(list(y_pos)))
    ax.set_yticklabels(labels, fontsize=6.5)
    for bar, val in zip(bars, values):
        ax.text(bar.get_width() + 0.2, bar.get_y() + bar.get_height() / 2,
                str(val), va="center", ha="left", fontsize=6)
    fig.tight_layout()
    save_figure(fig, "fig_geo_totals")

    # ── Multi-line: top 5 trends ───────────────────────────────────────────
    fig, ax = plt.subplots(figsize=(SINGLE_COL, 3.2))
    for i, c in enumerate(top5):
        counts = [country_year[c].get(y, 0) for y in all_years]
        ax.plot(all_years, counts, marker="o", color=COLORS[i],
                label=c, linewidth=1.2, markersize=3)
    ax.set_xlabel("Year")
    ax.set_ylabel("Papers")
    ax.set_title("Top 5 Country Trends")
    ax.legend(fontsize=6, loc="upper left")
    ax.set_xticks(all_years[::2])
    format_axes(ax)
    fig.tight_layout()
    save_figure(fig, "fig_geo_trends")

    # ── Grouped bar: 2015-2020 vs 2021-2025 ───────────────────────────────
    early_years = [y for y in all_years if y <= 2020]
    late_years = [y for y in all_years if y >= 2021]
    top8 = all_countries[:8]
    fig_h = max(2.5, len(top8) * 0.28 + 1.0)
    fig, ax = plt.subplots(figsize=(SINGLE_COL, fig_h))

    early_raw = [sum(country_year[c].get(y, 0) for y in early_years) for c in top8]
    late_raw = [sum(country_year[c].get(y, 0) for y in late_years) for c in top8]
    early_total = sum(early_raw) or 1
    late_total = sum(late_raw) or 1
    early_pct = [100 * v / early_total for v in early_raw]
    late_pct = [100 * v / late_total for v in late_raw]

    x = np.arange(len(top8))
    w = 0.35
    bars_e = ax.barh(x - w / 2, early_pct, w, label="2015\u20132020", color=COLORS[5])
    bars_l = ax.barh(x + w / 2, late_pct, w, label="2021\u20132025", color=COLORS[1])
    ax.invert_yaxis()
    ax.set_xlabel("Share of Papers (%)")
    ax.set_title("Period Comparison")
    ax.legend(fontsize=6)
    format_axes(ax)
    ax.yaxis.set_major_locator(FixedLocator(list(x)))
    ax.set_yticklabels(top8, fontsize=6.5)
    fig.tight_layout()
    save_figure(fig, "fig_geo_periods")


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
