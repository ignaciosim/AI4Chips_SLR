#!/usr/bin/env python3
"""fig_method_evolution.py — AI method families and their evolution, 2015-2026.

Answers the reviewer request for "a temporal evolution of major AI method
families from 2015-2026". Two panels:

Single panel: the share of papers naming each of the three successively
dominant method families. The dominant family changes twice over the window
(classical ML -> deep learning -> foundation models), so three lines carry the
whole story; adding more would obscure it.

Shannon diversity is still computed and printed to stdout for use in the text,
but is no longer plotted: it rises to ~2.0 by 2020 and is flat thereafter, so a
panel of its own spent width without adding a visual finding.

The series ends at 2025. Scopus indexing for 2026 was still partial at the
time of retrieval, so including it would understate the final year; this
matches plot_style.DISPLAY_YEAR_MAX, which caps the other trend figures.

Usage:
    python3 figures/fig_method_evolution.py --datadir scopus_out12
"""
import argparse
import csv
import math
import sys
from collections import Counter, defaultdict
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.ticker import MultipleLocator, FixedLocator

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import plot_style  # noqa: E402
from plot_style import (apply_style, save_figure, format_axes,  # noqa: E402
                        load_csv_papers, DOUBLE_COL, COLORS)

# The three successively dominant families, in era order.
ERAS = [
    ("classical_ml", "Classical ML", COLORS[0]),
    ("deep_learning", "Deep learning", COLORS[1]),
    ("llm_foundation_models", "Foundation models / LLM", COLORS[2]),
]
# 2026 was only partially indexed at retrieval, so it is EXCLUDED, consistent
# with plot_style.DISPLAY_YEAR_MAX which caps every other trend figure at 2025.
MAX_YEAR = 2025
PARTIAL_YEAR = None
# Years below this size are pooled into a single leading point. 2015-2017 hold
# 11, 20 and 10 papers, so their year-to-year swings are sampling noise rather
# than signal (classical ML reads 45%, 15%, 60% across them). Pooling is applied
# to the whole below-threshold run rather than to individually awkward years.
POOL_BELOW_N = 0        # set to e.g. 25 to pool the undersized leading years


def load(datadir):
    """Group the curated corpus by year. Uses the shared loader so curation
    and the year cap match every other figure and the reported corpus size."""
    rows = defaultdict(list)
    for p in load_csv_papers(year_max=MAX_YEAR):
        rows[p["year"]].append(p["method_tags"])
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--datadir", default=None)
    args = ap.parse_args()
    if args.datadir:
        plot_style.set_data_dir(args.datadir)
    data = load(plot_style.DATA_DIR)

    # Pool the leading run of undersized years into one aggregate point.
    years_raw = sorted(data)
    lead = []
    for y in years_raw:
        if len(data[y]) < POOL_BELOW_N:
            lead.append(y)
        else:
            break
    pooled_label = None
    if len(lead) > 1:
        merged = [tags for y in lead for tags in data[y]]
        for y in lead:
            del data[y]
        anchor = lead[-1]
        data[anchor] = merged
        pooled_label = f"{lead[0]}\u2013{str(lead[-1])[2:]}"

    years = sorted(data)
    share = {k: [] for k, _, _ in ERAS}
    diversity, npapers = [], []
    for y in years:
        papers = data[y]
        n = len(papers)
        npapers.append(n)
        counts = Counter(t for tags in papers for t in tags)
        total = sum(counts.values()) or 1
        diversity.append(
            -sum((v / total) * math.log(v / total) for v in counts.values()))
        for key, _, _ in ERAS:
            share[key].append(
                100.0 * sum(1 for tags in papers if key in tags) / n if n else 0)

    apply_style()
    fig, ax = plt.subplots(figsize=(DOUBLE_COL * 0.78, 3.2))

    def draw(a, xs, ys, color, label=None, lw=2.0):
        """Solid through the last fully-indexed year, dashed into the partial one."""
        cut = len(xs) - 1 if xs[-1] == PARTIAL_YEAR else len(xs)
        a.plot(xs[:cut], ys[:cut], color=color, lw=lw, label=label,
               marker="o", markersize=3.5)
        if cut < len(xs):
            a.plot(xs[cut - 1:], ys[cut - 1:], color=color, lw=lw, ls="--")
            a.plot(xs[-1:], ys[-1:], color=color, marker="o", markersize=3.5,
                   markerfacecolor="white", markeredgewidth=1.2)

    for key, label, color in ERAS:
        draw(ax, years, share[key], color, label)
        ax.annotate(label, xy=(years[-1], share[key][-1]),
                    xytext=(4, 0), textcoords="offset points",
                    fontsize=6.5, color=color, va="center")
    ax.set_xlabel("Publication year")
    ax.set_ylabel("Share of that year's papers (%)")
    ax.set_title("The dominant AI method family changes twice", fontsize=9)
    # right margin sized for the longest direct label, which sits at the
    # final data point; too little and it clips at the canvas edge in PDF
    ax.set_xlim(years[0] - 0.4, years[-1] + 4.6)
    ax.set_ylim(0, max(max(v) for v in share.values()) * 1.22)
    format_axes(ax)
    # integer years; set AFTER format_axes, which installs its own locators
    ax.xaxis.set_major_locator(FixedLocator(list(range(years[0], years[-1] + 1, 2))))
    # The first three years rest on 11, 20 and 10 papers; mark the region so the
    # early swings are not read as trend.
    # The first three years rest on 11, 20 and 10 papers; shade them so the
    # swings there (classical ML reads 45%, 15%, 60%) are not read as trend.
    small = [y for y in years if len(data[y]) < 25]
    if small and not pooled_label:
        ax.axvspan(years[0] - 0.4, max(small) + 0.5,
                   color="#000000", alpha=0.04, lw=0)
        ax.annotate("n < 25/yr", xy=((years[0] + max(small)) / 2,
                                     ax.get_ylim()[1] * 0.95),
                    fontsize=6, color="#888888", ha="center")

    if pooled_label:
        # relabel the aggregate point and mark it as pooled
        ticks = [t for t in range(years[0], years[-1] + 1, 2)]
        if years[0] not in ticks:
            ticks = [years[0]] + ticks
        ax.xaxis.set_major_locator(FixedLocator(ticks))
        ax.set_xticklabels([pooled_label if t == years[0] else str(t)
                            for t in ticks])
        # No "pooled" annotation: the 2015-17 tick label already carries it,
        # and the caption states the rule. An extra note below the axis
        # collides with the axis title.

    fig.tight_layout()
    save_figure(fig, "fig_method_evolution")

    print(f"years {years[0]}-{years[-1]}  n={sum(npapers)}")
    for key, label, _ in ERAS:
        print(f"  {label:26} {share[key][0]:.0f}% -> {share[key][-1]:.0f}%")
    print(f"  Shannon {diversity[0]:.2f} -> {max(diversity):.2f} "
          f"(peak {years[diversity.index(max(diversity))]})")


if __name__ == "__main__":
    main()
