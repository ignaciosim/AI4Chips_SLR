"""Figure: Chip task co-occurrence heatmap."""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from collections import Counter
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
from plot_style import (apply_style, save_figure, DOUBLE_COL, COLORS,
                        TASK_LABEL, load_csv_papers)


def main():
    apply_style()
    papers = load_csv_papers()

    # Count co-occurrences of chip tasks
    task_counts = Counter()
    cooccur = Counter()
    for p in papers:
        tasks = p["chip_tasks"]
        for t in tasks:
            task_counts[t] += 1
        if len(tasks) >= 2:
            for i in range(len(tasks)):
                for j in range(i + 1, len(tasks)):
                    pair = tuple(sorted([tasks[i], tasks[j]]))
                    cooccur[pair] += 1

    # Filter to tasks with 5+ papers
    active_tasks = sorted([t for t, c in task_counts.items() if c >= 5],
                          key=lambda t: -task_counts[t])

    if len(active_tasks) < 2:
        print("Not enough tasks with 5+ papers for co-occurrence heatmap")
        return

    n = len(active_tasks)
    matrix = np.zeros((n, n))
    for i in range(n):
        for j in range(n):
            if i == j:
                matrix[i, j] = task_counts[active_tasks[i]]
            else:
                pair = tuple(sorted([active_tasks[i], active_tasks[j]]))
                matrix[i, j] = cooccur.get(pair, 0)

    labels = [TASK_LABEL.get(t, t) for t in active_tasks]

    fig, ax = plt.subplots(figsize=(DOUBLE_COL * 0.65, DOUBLE_COL * 0.55))

    # Custom colormap
    cmap = LinearSegmentedColormap.from_list("wb", ["#FFFFFF", COLORS[2]])
    im = ax.imshow(matrix, aspect="auto", cmap=cmap, vmin=0)

    ax.set_xticks(range(n))
    ax.set_xticklabels(labels, rotation=45, ha="right", fontsize=6.5)
    ax.set_yticks(range(n))
    ax.set_yticklabels(labels, fontsize=6.5)

    # Annotate cells
    for i in range(n):
        for j in range(n):
            val = int(matrix[i, j])
            if val > 0:
                color = "white" if val > matrix.max() * 0.6 else "black"
                ax.text(j, i, str(val), ha="center", va="center",
                        fontsize=6, color=color)

    cbar = fig.colorbar(im, ax=ax, shrink=0.8, pad=0.02)
    cbar.set_label("Co-occurrence Count", fontsize=7)
    cbar.ax.tick_params(labelsize=6)

    ax.set_title("Chip Task Co-occurrence (diagonal = total)")
    fig.tight_layout()
    save_figure(fig, "fig_task_combinations")


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
