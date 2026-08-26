#!/usr/bin/env python3
"""fig_method_stage.py — AI method families across the silicon lifecycle.

The reviewer-requested "lifecycle-stage x AI-method landscape". Distinct from
`fig_method_task.py`, which crosses methods against chip *tasks*; this one
crosses them against lifecycle *stages*, showing which families of AI method
are used where in the silicon lifecycle.

Cells are column-normalised — the share of that stage's papers whose title
names the method — because the stages differ in size by an order of magnitude
(design ~360 papers vs transit ~26) and raw counts would simply restate the
stage distribution. Each column header carries its own N so magnitude is not
lost. This mirrors the treatment in `fig_method_country.py`.

Note the measure is title-derived, consistent with the review's screening:
it is the share of papers whose TITLE names the method, a conservative floor
on actual use.

Usage:
    python3 figures/fig_method_stage.py --datadir scopus_out12
"""
import argparse
import sys
from collections import Counter, defaultdict
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import LinearSegmentedColormap

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import plot_style  # noqa: E402
from plot_style import (apply_style, save_figure, load_csv_papers,  # noqa: E402
                        DOUBLE_COL, COLORS)

STAGES = ["design", "fabrication", "packaging", "transit", "in_field",
          "disposal"]
LABEL = {"design": "Design", "fabrication": "Fabrication",
         "packaging": "Packaging", "transit": "Transit",
         "in_field": "In-field", "disposal": "Disposal"}
MIN_METHOD_COUNT = 5      # drop long-tail methods that would be all-white


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--datadir", default=None)
    args = ap.parse_args()
    if args.datadir:
        plot_style.set_data_dir(args.datadir)

    papers = load_csv_papers(year_max=None)  # aggregate: use the whole corpus
    stage_n = Counter()
    stage_methods = defaultdict(Counter)
    totals = Counter()
    for p in papers:
        st = p.get("stage")
        if st not in STAGES:
            continue
        stage_n[st] += 1
        for m in p["method_tags"]:
            stage_methods[st][m] += 1
            totals[m] += 1

    stages = [s for s in STAGES if stage_n[s] > 0]
    methods = sorted([m for m, c in totals.items() if c >= MIN_METHOD_COUNT],
                     key=lambda m: -totals[m])

    matrix = np.zeros((len(methods), len(stages)))
    for j, s in enumerate(stages):
        n = stage_n[s]
        for i, m in enumerate(methods):
            matrix[i, j] = 100 * stage_methods[s].get(m, 0) / n if n else 0

    apply_style()
    fig, ax = plt.subplots(figsize=(DOUBLE_COL * 0.72, 4.2))
    cmap = LinearSegmentedColormap.from_list("wb", ["#FFFFFF", COLORS[0]])
    im = ax.imshow(matrix, aspect="auto", cmap=cmap, vmin=0)

    ax.set_xticks(range(len(stages)))
    ax.set_xticklabels([f"{LABEL[s]}\n(n={stage_n[s]})" for s in stages],
                       rotation=45, ha="right", fontsize=7)
    ax.set_yticks(range(len(methods)))
    ax.set_yticklabels([m.replace("_", " ") for m in methods], fontsize=7)

    vmax = matrix.max() if matrix.size else 1
    for i in range(len(methods)):
        for j in range(len(stages)):
            v = matrix[i, j]
            if v > 0:
                ax.text(j, i, f"{v:.0f}%", ha="center", va="center",
                        fontsize=5.5,
                        color="white" if v > vmax * 0.55 else "#222222")

    cbar = fig.colorbar(im, ax=ax, shrink=0.8, pad=0.02)
    cbar.set_label("% of stage's papers", fontsize=7)
    cbar.ax.tick_params(labelsize=6)
    cbar.outline.set_visible(False)

    ax.set_title(f"AI Method Family × Lifecycle Stage (N={len(papers)})")
    for sp in ax.spines.values():
        sp.set_visible(False)
    ax.tick_params(length=0)

    fig.tight_layout()
    save_figure(fig, "fig_method_stage")

    print(f"stages: { {s: stage_n[s] for s in stages} }")
    print(f"methods plotted: {len(methods)} (>= {MIN_METHOD_COUNT} papers)")


if __name__ == "__main__":
    main()
