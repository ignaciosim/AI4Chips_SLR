"""Figure: AI method × chip task cross-tabulation heatmap."""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from collections import Counter
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
from plot_style import (apply_style, save_figure, DOUBLE_COL, COLORS,
                        TASK_LABEL, load_csv_papers)

METHOD_LABEL = {
    "deep_learning": "Deep Learning",
    "classical_ml": "Classical ML",
    "graph_neural_networks": "GNN",
    "general_ml_signals": "General ML",
    "bayesian_probabilistic": "Bayesian",
    "reinforcement_learning": "RL",
    "llm_foundation_models": "LLM / Foundation",
    "evolutionary_optimization": "Evolutionary Opt.",
    "symbolic_reasoning": "Symbolic",
    "generative_adversarial": "GAN",
    "transfer_learning": "Transfer Learning",
    "anomaly_detection": "Anomaly Detection",
}


def main():
    apply_style()
    papers = load_csv_papers()

    # Count methods and tasks globally
    method_counts = Counter()
    task_counts = Counter()
    cross = Counter()  # (method, task) → count

    for p in papers:
        for m in p["method_tags"]:
            method_counts[m] += 1
            for t in p["chip_tasks"]:
                cross[(m, t)] += 1
        for t in p["chip_tasks"]:
            task_counts[t] += 1

    # Filter: methods with 5+ papers, tasks with 5+ papers
    methods = sorted([m for m, c in method_counts.items() if c >= 5],
                     key=lambda m: -method_counts[m])
    tasks = sorted([t for t, c in task_counts.items() if c >= 5],
                   key=lambda t: -task_counts[t])

    # Build matrix: rows = methods, cols = tasks, values = paper count
    matrix = np.zeros((len(methods), len(tasks)))
    for i, m in enumerate(methods):
        for j, t in enumerate(tasks):
            matrix[i, j] = cross.get((m, t), 0)

    mlabels = [METHOD_LABEL.get(m, m) for m in methods]
    tlabels = [TASK_LABEL.get(t, t) for t in tasks]

    fig, ax = plt.subplots(figsize=(DOUBLE_COL, DOUBLE_COL * 0.52))

    cmap = LinearSegmentedColormap.from_list("wb", ["#FFFFFF", COLORS[0]])
    im = ax.imshow(matrix, aspect="auto", cmap=cmap, vmin=0)

    ax.set_xticks(range(len(tasks)))
    ax.set_xticklabels(tlabels, rotation=45, ha="right", fontsize=6.5)
    ax.set_yticks(range(len(methods)))
    ax.set_yticklabels(mlabels, fontsize=6.5)

    # Annotate cells
    for i in range(len(methods)):
        for j in range(len(tasks)):
            val = int(matrix[i, j])
            if val > 0:
                color = "white" if val > matrix.max() * 0.55 else "black"
                ax.text(j, i, str(val), ha="center", va="center",
                        fontsize=5.5, color=color)

    cbar = fig.colorbar(im, ax=ax, shrink=0.8, pad=0.02)
    cbar.set_label("Number of Papers", fontsize=7)
    cbar.ax.tick_params(labelsize=6)

    ax.set_title("AI Method × Chip Task (N={})".format(len(papers)))
    fig.tight_layout()
    save_figure(fig, "fig_method_task_heatmap")


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
