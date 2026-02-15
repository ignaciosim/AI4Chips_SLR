"""Figure: AI method adoption heatmap across top 8 countries."""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from collections import Counter, defaultdict
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
from plot_style import (apply_style, save_figure, DOUBLE_COL, COLORS,
                        merge_csv_json)


def main():
    apply_style()
    papers = merge_csv_json()

    country_counts = Counter()
    country_methods = defaultdict(Counter)

    for p in papers:
        affiliations = p.get("affiliations") or []
        countries = set()
        for a in affiliations:
            c = a.get("affiliation-country", "")
            if c:
                countries.add(c)
        for c in countries:
            country_counts[c] += 1
            for m in p["method_tags"]:
                country_methods[c][m] += 1

    # Top 8 countries
    top8 = sorted(country_counts, key=lambda c: -country_counts[c])[:8]

    # Methods that appear 3+ times globally
    global_methods = Counter()
    for c in country_counts:
        for m, cnt in country_methods[c].items():
            global_methods[m] += cnt
    methods = sorted([m for m, cnt in global_methods.items() if cnt >= 3],
                     key=lambda m: -global_methods[m])

    # Build matrix (% of country's papers using each method)
    matrix = np.zeros((len(methods), len(top8)))
    for j, c in enumerate(top8):
        n = country_counts[c]
        for i, m in enumerate(methods):
            matrix[i, j] = 100 * country_methods[c].get(m, 0) / n if n > 0 else 0

    fig, ax = plt.subplots(figsize=(DOUBLE_COL * 0.7, 4.0))

    # Custom colormap: white → blue
    cmap = LinearSegmentedColormap.from_list("wb", ["#FFFFFF", COLORS[0]])
    im = ax.imshow(matrix, aspect="auto", cmap=cmap, vmin=0)

    ax.set_xticks(range(len(top8)))
    ax.set_xticklabels(top8, rotation=45, ha="right", fontsize=7)
    ax.set_yticks(range(len(methods)))
    ax.set_yticklabels(methods, fontsize=7)

    # Annotate cells
    for i in range(len(methods)):
        for j in range(len(top8)):
            val = matrix[i, j]
            if val > 0:
                color = "white" if val > 40 else "black"
                ax.text(j, i, f"{val:.0f}%", ha="center", va="center",
                        fontsize=5.5, color=color)

    cbar = fig.colorbar(im, ax=ax, shrink=0.8, pad=0.02)
    cbar.set_label("% of Country's Papers", fontsize=7)
    cbar.ax.tick_params(labelsize=6)

    ax.set_title("AI Method Adoption by Country (%)")
    fig.tight_layout()
    save_figure(fig, "fig_method_country_heatmap")


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
