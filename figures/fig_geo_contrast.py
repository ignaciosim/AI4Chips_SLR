"""Figure: country contribution CONTRASTED between the two corpora --
AI-for-Chips (N=660) against all screened chip-research records (N=14,551).

The single-corpus geography figures (fig_geo, fig_geo_all) each answer "who
publishes here". These answer the harder question the manuscript actually
argues: whether a country is over- or under-represented in AI-for-Chips
RELATIVE to its footprint in chip research generally, and whether the two
corpora move together over time.

Shares are per-paper with whole counting: a paper with authors in two
countries counts once for each, so shares sum to more than 100%. Both corpora
use the same convention, which is what makes them comparable.

Outputs:
  fig_geo_share_contrast   grouped barh, share in each corpus (aggregate, incl. 2026)
  fig_geo_specialization   ratio of the two shares, diverging from parity
  fig_geo_trends_contrast  two panels, share of annual output, 2015-2025
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from collections import Counter, defaultdict

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.ticker import FixedLocator

from plot_style import (DISPLAY_YEAR_MAX, apply_style, save_figure, format_axes,
                        SINGLE_COL, DOUBLE_COL, COLORS,
                        merge_csv_json, load_jsonl_papers)

# Countries shown in the trend panels: the union of the top four of each
# corpus. Both panels plot the same set in the same colours -- a shared legend
# is the whole point of a contrast figure.
TREND_COUNTRIES = ["United States", "China", "South Korea",
                   "Hong Kong", "Taiwan", "India"]

TOP_N_BARS = 10

# The trend panels plot SHARES, and a share is meaningless on a denominator of
# ten. The AI-for-Chips corpus holds 10/19/9 papers in 2015/2016/2017, so a
# single US paper moves the line by five to ten points -- the 2015 value would
# read as "the US produced 80% of the field" when it produced eight papers.
# From 2018 the annual denominator is 32 or more. The count-based trend figure
# (fig_geo_trends) shows the full window; this one starts where a percentage
# is a measurement rather than an artefact of a small denominator.
TREND_START = 2018


def _countries(affiliations):
    """Distinct country set for one record; empty when affiliation data is absent."""
    cs = {(a.get("affiliation-country") or "").strip() for a in (affiliations or [])}
    cs.discard("")
    return cs


def collect():
    """Country counts and per-year counts for both corpora.

    Aggregates deliberately include the final, partially indexed year: they are
    totals, not a series. The trend panels drop it further down.
    """
    ai_total = Counter()
    ai_year = defaultdict(Counter)
    ai_papers = merge_csv_json(year_max=None)
    for p in ai_papers:
        for c in _countries(p.get("affiliations")):
            ai_total[c] += 1
            ai_year[c][p["year"]] += 1

    full_total = Counter()
    full_year = defaultdict(Counter)
    full_records = load_jsonl_papers(year_max=None)
    for r in full_records:
        for c in _countries((r.get("entry") or {}).get("affiliation")):
            full_total[c] += 1
            full_year[c][r.get("year")] += 1

    return (ai_total, ai_year, len(ai_papers),
            full_total, full_year, len(full_records))


def fig_share_contrast(ai_total, n_ai, full_total, n_full):
    """Grouped horizontal bar: share of each corpus, top countries by AI-for-Chips."""
    top = [c for c, _ in ai_total.most_common(TOP_N_BARS)]
    ai_pct = [100 * ai_total[c] / n_ai for c in top]
    full_pct = [100 * full_total[c] / n_full for c in top]

    fig_h = max(2.5, len(top) * 0.34 + 1.0)
    fig, ax = plt.subplots(figsize=(SINGLE_COL, fig_h))
    y = np.arange(len(top))
    w = 0.38
    ax.barh(y - w / 2, ai_pct, w, color=COLORS[1],
            label=f"AI-for-Chips (N={n_ai})")
    ax.barh(y + w / 2, full_pct, w, color=COLORS[0],
            label=f"All chip research (N={n_full:,})")
    ax.invert_yaxis()
    ax.set_xlabel("Share of corpus (%)")
    ax.set_title("Country Contribution: AI-for-Chips vs. Field")
    ax.legend(fontsize=6, loc="lower right")
    format_axes(ax)
    ax.yaxis.set_major_locator(FixedLocator(list(y)))
    ax.set_yticklabels(top, fontsize=6.5)
    for i, (a, f) in enumerate(zip(ai_pct, full_pct)):
        ax.text(a + 0.3, i - w / 2, f"{a:.1f}", va="center", ha="left", fontsize=5.5)
        ax.text(f + 0.3, i + w / 2, f"{f:.1f}", va="center", ha="left", fontsize=5.5)
    fig.tight_layout()
    save_figure(fig, "fig_geo_share_contrast")


def fig_specialization(ai_total, n_ai, full_total, n_full):
    """Ratio of the two shares: >1 means a country is concentrated in AI-for-Chips.

    Plotted on a log x-axis so that a 2x over- and a 2x under-representation are
    the same visual distance from parity; on a linear axis under-representation
    is compressed into the 0-1 interval and reads as a smaller effect than it is.
    """
    top = [c for c, _ in ai_total.most_common(TOP_N_BARS)]
    ratio = [(100 * ai_total[c] / n_ai) / (100 * full_total[c] / n_full)
             for c in top]
    order = sorted(range(len(top)), key=lambda i: -ratio[i])
    top = [top[i] for i in order]
    ratio = [ratio[i] for i in order]

    fig_h = max(2.5, len(top) * 0.28 + 1.0)
    fig, ax = plt.subplots(figsize=(SINGLE_COL, fig_h))
    y = np.arange(len(top))
    colors = [COLORS[1] if r >= 1 else COLORS[0] for r in ratio]
    ax.hlines(y, 1.0, ratio, color=colors, linewidth=1.2)
    ax.plot(ratio, y, "o", markersize=4.5, linestyle="none",
            color="none", markerfacecolor="none")
    for yi, r, c in zip(y, ratio, colors):
        ax.plot([r], [yi], "o", markersize=4.5, color=c)
        ax.text(r * (1.06 if r >= 1 else 0.94), yi, f"{r:.2f}",
                va="center", ha="left" if r >= 1 else "right", fontsize=5.5)
    ax.axvline(1.0, color="#666666", linewidth=0.7, linestyle="--")
    ax.set_xscale("log")
    ax.set_xlim(0.3, 5.0)
    ax.set_xticks([0.5, 1.0, 2.0, 4.0])
    ax.set_xticklabels(["0.5x", "parity", "2x", "4x"])
    ax.invert_yaxis()
    ax.set_xlabel("AI-for-Chips share ÷ field share")
    ax.set_title("Specialization in AI-for-Chips")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.yaxis.set_major_locator(FixedLocator(list(y)))
    ax.set_yticklabels(top, fontsize=6.5)
    fig.tight_layout()
    save_figure(fig, "fig_geo_specialization")


def fig_trends_contrast(ai_year, full_year, ai_papers_by_year, full_papers_by_year):
    """Two panels, shared y: share of each year's output, AI-for-Chips vs. field.

    Share rather than counts, because the two corpora differ by a factor of 22 --
    on a count axis the field panel would say nothing except "the field is
    larger". Share makes the two trajectories directly comparable.
    """
    years = [y for y in sorted(full_papers_by_year)
             if TREND_START <= y <= DISPLAY_YEAR_MAX]

    fig, axes = plt.subplots(1, 2, figsize=(DOUBLE_COL, 2.9), sharey=True)
    panels = [
        (axes[0], ai_year, ai_papers_by_year,
         f"AI-for-Chips corpus (N={sum(ai_papers_by_year.values()):,})"),
        (axes[1], full_year, full_papers_by_year,
         f"All chip research (N={sum(full_papers_by_year.values()):,})"),
    ]
    for ax, cy, totals, title in panels:
        for i, c in enumerate(TREND_COUNTRIES):
            shares = [100 * cy[c].get(y, 0) / totals[y] if totals.get(y) else 0
                      for y in years]
            ax.plot(years, shares, marker="o", color=COLORS[i], label=c,
                    linewidth=1.2, markersize=2.8)
        ax.set_xlabel("Year")
        ax.set_title(title, fontsize=8.5)
        ax.set_xticks(years)
        format_axes(ax)
    axes[0].set_ylabel("Share of year's output (%)")
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, fontsize=7, ncol=6, frameon=False,
               loc="lower center", bbox_to_anchor=(0.5, -0.02))
    fig.tight_layout(rect=(0, 0.07, 1, 1))
    save_figure(fig, "fig_geo_trends_contrast")


def main():
    apply_style()
    ai_total, ai_year, n_ai, full_total, full_year, n_full = collect()

    ai_by_year = Counter()
    for p in merge_csv_json(year_max=None):
        ai_by_year[p["year"]] += 1
    full_by_year = Counter()
    for r in load_jsonl_papers(year_max=None):
        full_by_year[r.get("year")] += 1

    fig_share_contrast(ai_total, n_ai, full_total, n_full)
    fig_specialization(ai_total, n_ai, full_total, n_full)
    fig_trends_contrast(ai_year, full_year, ai_by_year, full_by_year)


if __name__ == "__main__":
    import argparse as _ap
    _p = _ap.ArgumentParser()
    _p.add_argument("--datadir", default=None, help="Path to data directory")
    _args = _p.parse_args()
    if _args.datadir:
        from plot_style import set_data_dir
        set_data_dir(_args.datadir)
    main()
