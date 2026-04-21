"""Figure: Growth model fitting — exponential vs logistic for AI4chips."""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

import csv
from collections import Counter
import numpy as np
from scipy.optimize import curve_fit
import matplotlib.pyplot as plt
from matplotlib.ticker import MultipleLocator, MaxNLocator
import plot_style
from plot_style import apply_style, save_figure, format_axes, SINGLE_COL, COLORS

# ── paths ────────────────────────────────────────────────────────────────
from pathlib import Path
DATA = Path(__file__).resolve().parent.parent / "scopus_out10"
plot_style.set_data_dir(str(DATA))


def exp_model(t, a, b):
    return a * np.exp(b * t)


def logistic_model(t, L, k, t0):
    return L / (1 + np.exp(-k * (t - t0)))


def main():
    apply_style()

    # Load ai4chips counts by year
    counts = Counter()
    with open(DATA / "final_ai4chips_high_only.csv") as f:
        reader = csv.reader(f)
        header = next(reader)
        yi = header.index("year")
        for row in reader:
            counts[int(row[yi])] += 1

    years = np.array(range(2015, 2026), dtype=float)
    observed = np.array([counts[int(y)] for y in years], dtype=float)
    t = years - 2015  # normalize

    # Fit models
    popt_e, _ = curve_fit(exp_model, t, observed,
                          p0=[max(observed[0], 1), 0.2], maxfev=10000)
    bounds_l = ([0, 0, -5], [observed.max() * 50, 5, 30])
    popt_l, _ = curve_fit(logistic_model, t, observed,
                          p0=[observed.max() * 5, 0.3, 8],
                          bounds=bounds_l, maxfev=10000)

    # R² and AIC
    ss_tot = np.sum((observed - observed.mean()) ** 2)
    n = len(observed)

    pred_e = exp_model(t, *popt_e)
    ss_e = np.sum((observed - pred_e) ** 2)
    r2_e = 1 - ss_e / ss_tot
    aic_e = n * np.log(ss_e / n) + 2 * 2

    pred_l = logistic_model(t, *popt_l)
    ss_l = np.sum((observed - pred_l) ** 2)
    r2_l = 1 - ss_l / ss_tot
    aic_l = n * np.log(ss_l / n) + 2 * 3

    cagr = 100 * (np.exp(popt_e[1]) - 1)
    ceiling = popt_l[0]
    inflection_yr = 2015 + popt_l[2]

    print(f"  Exponential: CAGR={cagr:.1f}%, R²={r2_e:.3f}, AIC={aic_e:.1f}")
    print(f"  Logistic:    L={ceiling:.0f}, inflection={inflection_yr:.0f}, "
          f"R²={r2_l:.3f}, AIC={aic_l:.1f}")

    # Projection range
    t_proj = np.linspace(0, 15, 200)  # 2015–2030
    years_proj = 2015 + t_proj

    fig, ax = plt.subplots(figsize=(SINGLE_COL, 2.8))

    # Observed
    ax.bar(years, observed, width=0.6, color=COLORS[0], alpha=0.6,
           label="observed", zorder=2)

    # Exponential fit + projection
    ax.plot(years_proj, exp_model(t_proj, *popt_e), color=COLORS[1],
            linewidth=1.4, linestyle="-",
            label=f"exponential (R²={r2_e:.2f})", zorder=3)

    # Logistic fit + projection
    ax.plot(years_proj, logistic_model(t_proj, *popt_l), color=COLORS[2],
            linewidth=1.4, linestyle="--",
            label=f"logistic (R²={r2_l:.2f})", zorder=3)

    # Ceiling line
    ax.axhline(ceiling, color=COLORS[2], linewidth=0.7, linestyle=":",
               alpha=0.5)
    ax.annotate(f"ceiling ≈ {ceiling:.0f}",
                xy=(2028.5, ceiling), fontsize=6, color=COLORS[2],
                ha="center", va="bottom")

    # Vertical line at data boundary
    ax.axvline(2025.5, color="grey", linewidth=0.6, linestyle=":", alpha=0.5)
    ax.annotate("projected", xy=(2027, observed.max() * 0.2), fontsize=6,
                color="grey", ha="center", style="italic")

    ax.set_xlabel("Year")
    ax.set_ylabel("Papers per Year")
    ax.set_title("AI for Chips Growth Model (N={})".format(int(observed.sum())))
    ax.legend(fontsize=5.5, loc="upper left")
    ax.xaxis.set_major_locator(MultipleLocator(5))
    ax.set_xlim(2014.5, 2030.5)
    ax.yaxis.set_major_locator(MaxNLocator(integer=True))
    format_axes(ax)
    fig.tight_layout()
    save_figure(fig, "fig_growth_model")


if __name__ == "__main__":
    main()
