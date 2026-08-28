"""Figure: growth of AI-for-Chips against the field it sits inside.

fig_pub_volume shows the AI-for-Chips corpus growing. On its own that says
little -- a subfield can grow simply because its parent field is growing, or
because indexing coverage improved. This figure supplies the baseline: the
same eleven years for all 14,551 screened chip-research records.

Two panels, because the comparison has two halves that need different axes:

  Left   Both corpora indexed to 2015 = 100, so a 660-paper series and a
         13,390-paper series share one axis and the question becomes "how
         fast", not "how many". Growth rates are exponential fits over all
         eleven years rather than first-to-last ratios: the AI-for-Chips base
         year holds ten papers, and a point-to-point CAGR anchored on ten
         papers is mostly a statement about 2015.

  Right  AI-for-Chips as a percentage of that year's chip research. This is
         the scale-free version of the same finding -- no index, no base year,
         no fitted model -- and it is the panel to quote when the claim is
         that the subfield is growing FASTER than its parent rather than
         merely alongside it.

Caveat carried in the annotation: the field's exponential fit is poor
(R^2 = 0.34). Chip research is not growing exponentially; it is close to flat
with a 2025 uplift. The 3.3%/yr figure is the best exponential summary of a
series that is not exponential, and is quoted only as a foil for the 28.0%
that does fit (R^2 = 0.87).
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from collections import Counter

import numpy as np
import matplotlib.pyplot as plt

from plot_style import (DISPLAY_YEAR_MAX, apply_style, save_figure, format_axes,
                        DOUBLE_COL, COLORS, load_csv_papers, load_jsonl_papers)


def exp_fit(values):
    """Fit log(y) = a + b*t. Returns (CAGR, R^2); (None, None) if any y <= 0."""
    y = np.asarray(values, dtype=float)
    if (y <= 0).any() or len(y) < 3:
        return None, None
    t = np.arange(len(y), dtype=float)
    ly = np.log(y)
    b, a = np.polyfit(t, ly, 1)
    resid = ly - (a + b * t)
    ss_tot = ((ly - ly.mean()) ** 2).sum()
    r2 = 1 - (resid ** 2).sum() / ss_tot if ss_tot else float("nan")
    return float(np.exp(b) - 1), float(r2)


def main():
    apply_style()

    ai_counts = Counter(p["year"] for p in load_csv_papers(year_max=None))
    full_counts = Counter(r.get("year") for r in load_jsonl_papers(year_max=None))

    years = sorted(y for y in full_counts
                   if y is not None and y <= DISPLAY_YEAR_MAX)
    ai = [ai_counts.get(y, 0) for y in years]
    full = [full_counts.get(y, 0) for y in years]

    ai_cagr, ai_r2 = exp_fit(ai)
    full_cagr, full_r2 = exp_fit(full)

    fig, axes = plt.subplots(1, 2, figsize=(DOUBLE_COL, 3.0))

    # ── Left: indexed growth ────────────────────────────────────────────────
    ax = axes[0]
    ai_idx = [100 * v / ai[0] for v in ai]
    full_idx = [100 * v / full[0] for v in full]
    ax.plot(years, ai_idx, marker="o", color=COLORS[1], linewidth=1.6,
            markersize=3.2, label=f"AI-for-Chips (N={sum(ai):,})")
    ax.plot(years, full_idx, marker="s", color=COLORS[0], linewidth=1.4,
            markersize=3.0, label=f"All chip research (N={sum(full):,})")
    ax.axhline(100, color="#999999", linewidth=0.6, linestyle="--", zorder=1)
    ax.set_xlabel("Year")
    ax.set_ylabel("Papers, indexed (2015 = 100)")
    ax.set_title("Indexed Growth", fontsize=9.5)
    ax.set_xticks(years[::2])
    format_axes(ax)
    ax.legend(fontsize=6.5, loc="upper left")
    ax.text(0.03, 0.60,
            f"AI-for-Chips  {100 * ai_cagr:.1f}%/yr  (R²={ai_r2:.2f})\n"
            f"Field         {100 * full_cagr:.1f}%/yr  (R²={full_r2:.2f})",
            transform=ax.transAxes, fontsize=6.3, va="top",
            linespacing=1.5, color="#333333")

    # ── Right: penetration ──────────────────────────────────────────────────
    ax = axes[1]
    pen = [100 * a / f if f else 0 for a, f in zip(ai, full)]
    ax.plot(years, pen, marker="o", color=COLORS[2], linewidth=1.6,
            markersize=3.2)
    ax.fill_between(years, 0, pen, color=COLORS[2], alpha=0.15, linewidth=0)
    ax.set_xlabel("Year")
    ax.set_ylabel("AI-for-Chips share of\nchip research (%)")
    ax.set_title("Penetration of the Field", fontsize=9.5)
    ax.set_xticks(years[::2])
    ax.set_ylim(0, max(pen) * 1.25)
    format_axes(ax)
    # Below the marker: above it collides with the 2016 point.
    ax.annotate(f"{pen[0]:.1f}%", (years[0], pen[0]), textcoords="offset points",
                xytext=(4, -11), fontsize=6.5, color="#333333")
    ax.annotate(f"{pen[-1]:.1f}%", (years[-1], pen[-1]), textcoords="offset points",
                xytext=(-4, 7), fontsize=6.5, ha="right", color="#333333")

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
