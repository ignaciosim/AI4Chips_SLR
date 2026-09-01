#!/usr/bin/env python3
"""fig_country_profile.py — What the leading contributor countries work on.

Two panels over the three largest national contributors:

  (a) Lifecycle-stage composition. The United States and China are almost
      indistinguishable; South Korea is the outlier, with fabrication at
      roughly twice the corpus rate and no transit work at all.

  (b) AI method mix as a heatmap, CONDITIONED on the paper naming a specific
      method family in its title. Cells are annotated, and the colour ranks
      them; there is no colourbar because the numbers are already on the page.

WHY PANEL (b) IS CONDITIONAL. Method tags are derived from titles, so a raw
method share also measures how often a country's titles name their method at
all -- and that differs sharply: 88.3% of China-affiliated papers name a
specific family against 56.5% of US ones (US titles favour the generic phrase
"machine learning", which accounts for 70% of the US classical-ML tag).
Comparing raw shares therefore compares titling conventions as much as research
choices, and manufactures a US/China divergence that is not there. Restricting
to papers that name a family removes that term and is the honest comparison:
every major family then differs by less than the noise (all p > 0.2 by Fisher
exact except Bayesian at p = 0.05, none surviving correction across 8 tests).

Country attribution is any-author: a paper counts for every country appearing
in its affiliations, matching the convention used in the other geography
figures. Only 2 of 660 papers are US-China co-authored, so those two columns
are effectively disjoint samples.

COUNTRY SET. The four largest contributors, plus the whole corpus as a
reference column. The cut is at four because conditioning shrinks the
denominator and the next countries do not survive it: Germany reaches 18
method-naming papers and Taiwan 13, where a single paper moves a cell by 5-8
percentage points. Hong Kong is reported separately from China, as Scopus
codes it; folding the two together would make China the largest cumulative
contributor rather than the United States, so the convention is worth stating
wherever this figure appears.

Usage:
    python3 figures/fig_country_profile.py --datadir scopus_out12
"""
import argparse
import os
import sys
from collections import Counter

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap

import plot_style
from plot_style import (apply_style, save_figure, format_axes, merge_csv_json,
                        display_methods, method_label, DOUBLE_COL, COLORS,
                        COLOR_NEUTRAL, INK_MUTED, stack_colors, STACK_EDGE)

# Lifecycle order, earliest stage first. disposal is empty in this corpus and
# is dropped from the panel rather than drawn as a zero-width band.
STAGES = ["design", "fabrication", "packaging", "transit", "in_field"]
STAGE_LABEL = {"design": "Design", "fabrication": "Fabrication",
               "packaging": "Packaging", "transit": "Transit",
               "in_field": "In-field"}

# Families that name a specific method. A title carrying one of these is
# self-identifying; classical_ml and general_ml_signals are excluded because
# both are dominated by generic phrasing ("machine learning", "data-driven"),
# which is what panel (b) is designed to condition away.
SPECIFIC = ["deep_learning", "bayesian_probabilistic", "graph_neural_networks",
            "llm_foundation_models", "reinforcement_learning",
            "evolutionary_optimization", "generative_adversarial",
            "transfer_learning"]

N_COUNTRIES = 4
CORPUS_LABEL = "All papers"


def load(year_max=None):
    papers = merge_csv_json(year_max=year_max)
    for p in papers:
        p["countries"] = {a.get("affiliation-country")
                          for a in (p.get("affiliations") or [])
                          if a.get("affiliation-country")}
        p["methods"] = set(display_methods(p["method_tags"]))
    return papers


def panel_stages(ax, papers, countries):
    """100% stacked bars: lifecycle composition per country, plus the corpus."""
    rows = [(c, [p for p in papers if c in p["countries"]]) for c in countries]
    rows.append(("All papers", papers))

    labels = [f"{c}\n(n = {len(sel)})" for c, sel in rows]
    y = np.arange(len(rows))[::-1]          # first country at the top
    colors = stack_colors(
        [COLORS[0], COLORS[1], COLORS[2], COLORS[4], COLORS[5]], amount=0.10)

    left = np.zeros(len(rows))
    for stage, color in zip(STAGES, colors):
        vals = np.array([100 * sum(1 for p in sel if p["stage"] == stage)
                         / max(len(sel), 1) for _, sel in rows])
        ax.barh(y, vals, left=left, height=0.62, color=color,
                label=STAGE_LABEL[stage], **STACK_EDGE)
        for yi, (v, l) in zip(y, zip(vals, left)):
            if v >= 7:                      # only label bands wide enough to read
                ax.text(l + v / 2, yi, f"{v:.0f}", ha="center", va="center",
                        fontsize=6.5, color=INK_MUTED)
        left += vals

    ax.set_yticks(y)
    ax.set_yticklabels(labels, fontsize=7.5)
    ax.set_xlim(0, 100)
    ax.set_xlabel("Share of the country's papers (%)", fontsize=8)
    ax.set_title("(a) Lifecycle stage")
    format_axes(ax)
    ax.set_yticks(y)                        # re-assert: format_axes thins ticks
    ax.set_yticklabels(labels, fontsize=7.5)
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.18), ncol=3,
              frameon=False, fontsize=7, handlelength=1.1, handleheight=0.9,
              columnspacing=1.2)


def panel_methods(ax, papers, countries):
    """Heatmap: method mix among papers that name a specific family."""
    spec = set(SPECIFIC)
    cols = list(countries) + [CORPUS_LABEL]
    sel = {c: [p for p in papers if c in p["countries"] and p["methods"] & spec]
           for c in countries}
    sel[CORPUS_LABEL] = [p for p in papers if p["methods"] & spec]

    order = sorted(SPECIFIC, reverse=True,
                   key=lambda m: sum(1 for p in sel[CORPUS_LABEL]
                                     if m in p["methods"]))
    grid = np.array([[100 * sum(1 for p in sel[c] if m in p["methods"])
                      / max(len(sel[c]), 1) for c in cols] for m in order])

    cmap = LinearSegmentedColormap.from_list("wb", ["#FFFFFF", COLORS[0]])
    im = ax.imshow(grid, aspect="auto", cmap=cmap, vmin=0, vmax=grid.max())

    for i in range(grid.shape[0]):
        for j in range(grid.shape[1]):
            v = grid[i, j]
            ax.text(j, i, f"{v:.0f}", ha="center", va="center", fontsize=7,
                    color="white" if v > 0.62 * grid.max() else INK_MUTED)

    # the reference column is context, not a country: rule it off
    ax.axvline(len(countries) - 0.5, color="white", linewidth=2.4)

    ax.set_xticks(range(len(cols)))
    ax.set_xticklabels([f"{c}\n(n = {len(sel[c])})" for c in cols],
                       fontsize=6.8, linespacing=1.4)
    ax.set_yticks(range(len(order)))
    ax.set_yticklabels([method_label(m, tight=True) for m in order], fontsize=7.5)
    ax.tick_params(length=0)
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.set_title("(b) AI method family")
    ax.text(0.0, -0.30, "Share of each column's method-naming papers (%)",
            transform=ax.transAxes, fontsize=7.5, color=INK_MUTED, va="top")
    return im


def report(papers, countries):
    """Numbers behind the figure, for the caption and the text."""
    spec = set(SPECIFIC)
    print(f"  corpus N = {len(papers)}")
    both = sum(1 for p in papers
               if {"United States", "China"} <= p["countries"])
    print(f"  US-China co-authored: {both}")
    for c in countries:
        sel = [p for p in papers if c in p["countries"]]
        named = sum(1 for p in sel if p["methods"] & spec)
        stages = Counter(p["stage"] for p in sel)
        print(f"  {c}: n={len(sel)}  names a specific family "
              f"{named}/{len(sel)} ({100*named/len(sel):.1f}%)  "
              + " ".join(f"{s}={100*stages[s]/len(sel):.0f}%" for s in STAGES))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--datadir", default=None)
    args = ap.parse_args()
    if args.datadir:
        plot_style.set_data_dir(args.datadir)

    apply_style()
    papers = load(year_max=None)            # aggregate figure: whole corpus

    counts = Counter()
    for p in papers:
        for c in p["countries"]:
            counts[c] += 1
    countries = [c for c, _ in counts.most_common(N_COUNTRIES)]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(DOUBLE_COL, 3.5))
    panel_stages(ax1, papers, countries)
    panel_methods(ax2, papers, countries)
    fig.subplots_adjust(left=0.155, right=0.985, top=0.88,
                        wspace=0.40, bottom=0.28)

    save_figure(fig, "fig_country_profile")
    report(papers, countries)


if __name__ == "__main__":
    main()
