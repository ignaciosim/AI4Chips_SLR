#!/usr/bin/env python3
"""fig_geo_stage_periods.py — Who leads each lifecycle stage, P1 vs P2.

One panel per lifecycle stage, comparing the United States and China across
the two periods used elsewhere in the paper: P1 = 2015-2020, P2 = 2021-2025.
2026 is excluded throughout, being partially indexed at retrieval.

WHY ONLY TWO COUNTRIES. They are the only two that lead any stage in either
period, so the figure answers "who leads" without implying that the rest of
the field is absent. South Korea is the notable third party -- 12% of P1
fabrication and 14% of P2 -- and is reported in the text rather than drawn
here, where a third bar group would halve the width of the other two.

WHY THE ERROR BARS. The stages differ in size by more than an order of
magnitude, and the two smallest carry the figure's only surprise: the United
States retains a nominal lead in packaging and transit while losing the other
three. Those cells rest on 5 to 22 papers, where one paper moves a share by
4-20 points. Wilson 95% intervals are drawn so that the reader sees the two
US-leading panels are not separable from their China bars, rather than having
to find that caveat in the caption. Wilson rather than normal-approximation
because several cells sit near 0 and the normal interval would run negative.

Not part of the manuscript set: this is the stage-resolved companion to
fig_geo_periods, kept for the discussion rather than the results.

Usage:
    python3 figures/fig_geo_stage_periods.py --datadir scopus_out12
"""
import argparse
import math
import os
import sys
from collections import Counter

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

import numpy as np
import matplotlib.pyplot as plt

import plot_style
from plot_style import (apply_style, save_figure, format_axes, merge_csv_json,
                        DOUBLE_COL, COLORS, INK_MUTED)

STAGES = ["design", "fabrication", "in_field", "packaging", "transit"]
STAGE_LABEL = {"design": "Design", "fabrication": "Fabrication",
               "in_field": "In-field", "packaging": "Packaging",
               "transit": "Transit"}

COUNTRIES = ["United States", "China"]
SHORT = {"United States": "US", "China": "China"}

P1 = (2015, 2020)
P2 = (2021, 2025)
PERIODS = [(f"{P1[0]}–{P1[1]}", P1, COLORS[0]),
           (f"{P2[0]}–{P2[1]}", P2, COLORS[1])]

# Below this many papers a panel is annotated as too thin to read as a result.
THIN_N = 25


def wilson(k, n, z=1.96):
    """95% Wilson score interval for a binomial proportion, as percentages."""
    if n == 0:
        return 0.0, 0.0
    p = k / n
    d = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / d
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return 100 * max(centre - half, 0.0), 100 * min(centre + half, 1.0)


def main(datadir=None):
    # No argv parsing here: generate_all_figures.py imports this module and
    # calls main() directly.
    if datadir:
        plot_style.set_data_dir(datadir)

    apply_style()
    papers = merge_csv_json(year_max=None)
    for p in papers:
        p["c"] = {a.get("affiliation-country")
                  for a in (p.get("affiliations") or [])
                  if a.get("affiliation-country")}

    fig, axes = plt.subplots(1, len(STAGES), figsize=(DOUBLE_COL, 2.9),
                             sharey=True)
    x = np.arange(len(COUNTRIES))
    w = 0.36

    for ax, stage in zip(axes, STAGES):
        ns = []
        for j, (plabel, (y0, y1), color) in enumerate(PERIODS):
            sel = [p for p in papers
                   if p["stage"] == stage and y0 <= p["year"] <= y1]
            n = len(sel)
            ns.append(n)
            vals, los, his = [], [], []
            for c in COUNTRIES:
                k = sum(1 for p in sel if c in p["c"])
                lo, hi = wilson(k, n)
                vals.append(100 * k / n if n else 0.0)
                los.append(vals[-1] - lo)
                his.append(hi - vals[-1])
            pos = x + (j - 0.5) * w
            ax.bar(pos, vals, w, color=color,
                   label=plabel if stage == STAGES[0] else None)
            ax.errorbar(pos, vals, yerr=[los, his], fmt="none",
                        ecolor=INK_MUTED, elinewidth=0.7, capsize=1.6,
                        capthick=0.7, zorder=5)

        ax.set_xticks(x)
        ax.set_xticklabels([SHORT[c] for c in COUNTRIES], fontsize=7.5)
        # The thin-sample warning goes in the title, not inside the panel:
        # the panels that need it are exactly the ones whose error bars span
        # most of the axis, so there is no free space left to put it in.
        thin = "  · thin sample" if min(ns) < THIN_N else ""
        ax.set_title(f"{STAGE_LABEL[stage]}\nn = {ns[0]} → {ns[1]}{thin}",
                     fontsize=8, loc="center")
        ax.set_xlim(-0.6, len(COUNTRIES) - 0.4)
        format_axes(ax)

    axes[0].set_ylabel("Share of the stage's papers (%)")
    axes[0].set_ylim(0, 72)
    fig.legend(loc="lower center", ncol=2, frameon=False, fontsize=7.5,
               bbox_to_anchor=(0.5, -0.02))
    fig.subplots_adjust(left=0.085, right=0.99, top=0.80, bottom=0.22,
                        wspace=0.18)

    save_figure(fig, "fig_geo_stage_periods")

    for stage in STAGES:
        line = f"  {STAGE_LABEL[stage]:<12}"
        for plabel, (y0, y1), _ in PERIODS:
            sel = [p for p in papers
                   if p["stage"] == stage and y0 <= p["year"] <= y1]
            cnt = Counter()
            for p in sel:
                for c in p["c"]:
                    cnt[c] += 1
            lead = cnt.most_common(1)
            line += (f"  {plabel}: n={len(sel):<4} "
                     f"{lead[0][0] if lead else '-'} "
                     f"{lead[0][1] if lead else 0}")
        print(line)


if __name__ == "__main__":
    _ap = argparse.ArgumentParser()
    _ap.add_argument("--datadir", default=None)
    main(_ap.parse_args().datadir)
