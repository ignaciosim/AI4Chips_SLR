"""Figure: growth of AI-for-Chips against the field it sits inside.

fig_pub_volume shows the AI-for-Chips corpus growing. On its own that says
little -- a subfield can grow simply because its parent field is growing, or
because indexing coverage improved. This figure supplies the baseline: the
same years for all screened chip-research records.

Both corpora are indexed to 2015 = 100, so a 660-paper series and a
14,551-paper series share one axis and the question becomes "how fast", not
"how many". Growth rates are exponential fits over the whole window rather
than first-to-last ratios: the AI-for-Chips base year holds ten papers, and a
point-to-point CAGR anchored on ten papers is mostly a statement about 2015.

The field's exponential fit is weak -- chip research is close to flat with a
2025 uplift, not exponential -- so 3.3%/yr is the best exponential summary of
a series that is not exponential. It is quoted only as a foil for the 28.0%
that does fit. Cite the two rates as a contrast, not as two models of the
same kind.
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from collections import Counter

import numpy as np
import matplotlib.pyplot as plt

from plot_style import (DISPLAY_YEAR_MAX, apply_style, save_figure, format_axes,
                        DOUBLE_COL, COLORS, load_csv_papers, load_jsonl_papers)


def exp_fit(values):
    """Fit log(y) = a + b*t. Returns CAGR, or None if any y <= 0."""
    y = np.asarray(values, dtype=float)
    if (y <= 0).any() or len(y) < 3:
        return None
    t = np.arange(len(y), dtype=float)
    b, _ = np.polyfit(t, np.log(y), 1)
    return float(np.exp(b) - 1)


def main():
    apply_style()

    ai_counts = Counter(p["year"] for p in load_csv_papers(year_max=None))
    full_counts = Counter(r.get("year") for r in load_jsonl_papers(year_max=None))

    # The legend reports the CORPUS size, matching every other figure and the
    # PRISMA chain. The plotted series stops at DISPLAY_YEAR_MAX because it is
    # a time series and the final year is partially indexed, so the points
    # drawn cover 586 and 13,390 of those papers respectively. N here names
    # the corpus, not the number of plotted observations.
    n_ai = sum(ai_counts.values())
    n_full = sum(full_counts.values())

    years = sorted(y for y in full_counts
                   if y is not None and y <= DISPLAY_YEAR_MAX)
    ai = [ai_counts.get(y, 0) for y in years]
    full = [full_counts.get(y, 0) for y in years]

    ai_cagr = exp_fit(ai)
    full_cagr = exp_fit(full)

    fig, ax = plt.subplots(figsize=(DOUBLE_COL * 0.72, 3.3))

    ai_idx = [100 * v / ai[0] for v in ai]
    full_idx = [100 * v / full[0] for v in full]
    ax.plot(years, ai_idx, marker="o", color=COLORS[1], linewidth=1.6,
            markersize=3.4, label=f"AI-for-Chips (N={n_ai:,})")
    ax.plot(years, full_idx, marker="s", color=COLORS[0], linewidth=1.4,
            markersize=3.2, label=f"All chip research (N={n_full:,})")
    ax.axhline(100, color="#999999", linewidth=0.6, linestyle="--", zorder=1)

    ax.set_xlabel("Year")
    ax.set_ylabel(f"Papers, indexed ({years[0]} = 100)")
    ax.set_title("Growth of AI-for-Chips vs. the Field")
    ax.set_xticks(years)
    format_axes(ax)
    ax.legend(fontsize=7, loc="upper left")
    ax.text(0.03, 0.62,
            f"AI-for-Chips  {100 * ai_cagr:.1f}%/yr\n"
            f"Field         {100 * full_cagr:.1f}%/yr",
            transform=ax.transAxes, fontsize=7, va="top",
            linespacing=1.5, color="#333333")

    fig.tight_layout()
    save_figure(fig, "fig_growth_contrast")


if __name__ == "__main__":
    import argparse as _ap
    _p = _ap.ArgumentParser()
    _p.add_argument("--datadir", default=None, help="Path to data directory")
    _args = _p.parse_args()
    if _args.datadir:
        from plot_style import set_data_dir
        set_data_dir(_args.datadir)
    main()
