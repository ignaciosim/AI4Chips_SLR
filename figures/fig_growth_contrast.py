"""Figure: growth of AI-for-Chips against the field it sits inside.

fig_pub_volume shows the AI-for-Chips corpus growing. On its own that says
little -- a subfield can grow simply because its parent field is growing, or
because indexing coverage improved. This figure supplies the baseline: the
same years for all screened chip-research records.

Left panel. Both corpora are indexed to 2015 = 100, so a 660-paper series and
a 14,551-paper series share one axis and the question becomes "how fast", not
"how many". The y axis is therefore an INDEX, not a count -- the 2025 counts
are annotated on the endpoints so the index stays anchored to real numbers.
Growth rates are exponential fits over the whole window rather than
first-to-last ratios: the AI-for-Chips base year holds ten papers, and a
point-to-point CAGR anchored on ten papers is mostly a statement about 2015.
The field's exponential fit is weak -- chip research is close to flat with a
2025 uplift, not exponential -- so 3.3%/yr is the best exponential summary of
a series that is not exponential, quoted as a foil for the 28.0% that fits.

Right panel. AI-for-Chips as a percentage of that year's screened corpus:
same numerator and denominator, same eighteen queries, same index, same year.
Anything that inflates both -- broader journal coverage, the 2025 retrieval
uplift -- cancels, which is what the indexed panel on its own cannot rule
out. Note that the denominator is the SCREENED CORPUS, not world
semiconductor output, and the numerator is high-confidence papers only, so
the percentage is a floor rather than an estimate.
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
    # a time series and the final year is partially indexed. N here names the
    # corpus, not the number of plotted observations.
    n_ai = sum(ai_counts.values())
    n_full = sum(full_counts.values())

    years = sorted(y for y in full_counts
                   if y is not None and y <= DISPLAY_YEAR_MAX)
    ai = [ai_counts.get(y, 0) for y in years]
    full = [full_counts.get(y, 0) for y in years]

    fig, axes = plt.subplots(1, 2, figsize=(DOUBLE_COL, 3.1))

    # ── Left: indexed growth ────────────────────────────────────────────────
    ax = axes[0]
    ai_idx = [100 * v / ai[0] for v in ai]
    full_idx = [100 * v / full[0] for v in full]
    ax.plot(years, ai_idx, marker="o", color=COLORS[1], linewidth=1.6,
            markersize=3.2, label=f"AI-for-Chips (N={n_ai:,})")
    ax.plot(years, full_idx, marker="s", color=COLORS[0], linewidth=1.4,
            markersize=3.0, label=f"All chip research (N={n_full:,})")
    ax.axhline(100, color="#999999", linewidth=0.6, linestyle="--", zorder=1)

    # The index is unitless, so anchor both ends in actual papers. Without
    # this the reader has no way to tell whether "1480" is many papers or few.
    ax.annotate(f"{ai[-1]} papers", (years[-1], ai_idx[-1]),
                textcoords="offset points", xytext=(-4, -10), ha="right",
                fontsize=6.3, color=COLORS[1])
    ax.annotate(f"{full[-1]:,} papers", (years[-1], full_idx[-1]),
                textcoords="offset points", xytext=(-4, 7), ha="right",
                fontsize=6.3, color=COLORS[0])
    # In axes coordinates, not anchored to the 2015 point: both series sit at
    # 100 there, a few percent up the axis, so a data-anchored label lands on
    # the tick labels.
    ax.text(0.04, 0.20, f"{years[0]} base: {ai[0]} and {full[0]:,} papers",
            transform=ax.transAxes, fontsize=6.3, color="#666666")

    ax.set_xlabel("Year")
    ax.set_ylabel("Growth index")
    ax.set_title("Growth Relative to 2015", fontsize=9.5)
    ax.set_xticks(years[::2])
    format_axes(ax)
    ax.legend(fontsize=6.5, loc="upper left")
    ax.text(0.04, 0.62,
            f"AI-for-Chips  {100 * exp_fit(ai):.1f}%/yr\n"
            f"Field         {100 * exp_fit(full):.1f}%/yr",
            transform=ax.transAxes, fontsize=6.5, va="top",
            linespacing=1.5, color="#333333")

    # ── Right: presence ─────────────────────────────────────────────────────
    ax = axes[1]
    presence = [100 * a / f if f else 0 for a, f in zip(ai, full)]
    ax.plot(years, presence, marker="o", color=COLORS[2], linewidth=1.6,
            markersize=3.2)
    ax.fill_between(years, 0, presence, color=COLORS[2], alpha=0.15, linewidth=0)
    ax.set_xlabel("Year")
    ax.set_ylabel("AI-for-Chips share of that\nyear's screened corpus (%)")
    ax.set_title("AI-for-Chips Presence in the Field", fontsize=9.5)
    ax.set_xticks(years[::2])
    ax.set_ylim(0, max(presence) * 1.25)
    format_axes(ax)
    ax.annotate(f"{presence[0]:.1f}%", (years[0], presence[0]),
                textcoords="offset points", xytext=(4, -11), fontsize=6.5,
                color="#333333")
    ax.annotate(f"{presence[-1]:.1f}%", (years[-1], presence[-1]),
                textcoords="offset points", xytext=(-4, 7), fontsize=6.5,
                ha="right", color="#333333")

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
