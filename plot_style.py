"""Shared plotting module for AI4Chips SLR publication-quality figures.

Provides:
  - Matplotlib rcParams (serif fonts, 9pt, no top/right spines, tight layout)
  - Colorblind-safe palette with fixed domain assignments
  - Data loaders (CSV, JSON, JSONL) — centralized, no duplication
  - Classification helpers (analog/digital, commercial area, survey detection)
  - Trend labeling, venue normalization, shared constants
"""

import re as _re_survey
import csv
import json
import math
import os
from collections import Counter, defaultdict

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
from matplotlib.collections import QuadMesh
from matplotlib.patches import Rectangle
from matplotlib.ticker import MaxNLocator

# ── Paths ────────────────────────────────────────────────────────────────────

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
# Fallback only. Every entry point should pass --datadir (the Makefile does),
# and set_data_dir() below is the override hook. "corpus" is the directory
# name used by the published dataset repository, so a bare run against a
# fresh clone resolves rather than silently reading a stale local run.
DATA_DIR = os.path.join(SCRIPT_DIR, os.environ.get("SLR_DATADIR", "corpus"))
BASE_DIR = DATA_DIR  # compatibility alias
CSV_PATH = os.path.join(DATA_DIR, "final_ai4chips_high_only.csv")
JSON_PATH = os.path.join(DATA_DIR, "final_ai4chips_high_only.json")
JSONL_PATH = os.path.join(DATA_DIR, "raw_scopus_all.jsonl")
FIG_DIR = os.path.join(DATA_DIR, "figures")

# Cap displayed year for trend figures. Data files may include later years
# (partial/in-progress indexing), but figures should not show them.
DISPLAY_YEAR_MAX = 2025


def set_data_dir(path):
    """Override the default data directory."""
    global DATA_DIR, BASE_DIR, CSV_PATH, JSON_PATH, JSONL_PATH, FIG_DIR
    DATA_DIR = os.path.abspath(path)
    BASE_DIR = DATA_DIR
    CSV_PATH = os.path.join(DATA_DIR, "final_ai4chips_high_only.csv")
    JSON_PATH = os.path.join(DATA_DIR, "final_ai4chips_high_only.json")
    JSONL_PATH = os.path.join(DATA_DIR, "raw_scopus_all.jsonl")
    FIG_DIR = os.path.join(DATA_DIR, "figures")


# ── Figure dimensions ────────────────────────────────────────────────────────

SINGLE_COL = 3.5   # inches — single-column journal width
DOUBLE_COL = 7.0   # inches — double-column journal width

# ── Colorblind-safe palette (Okabe & Ito 2011, two substitutions) ───────
#
# The hue angles are Wong's, kept deliberately: of the qualitative sets in
# common academic use, his is the only one that survives simulation here.
# ColorBrewer Dark2 puts its green and magenta at OKLab dE 1.7 under
# deuteranopia -- indistinguishable -- and Tol's muted set drops a pair to
# 5.2. Two changes to the published order, both to fix measured defects:
#
#   * slot 4, reddish purple #CC79A7 -> wine #882255. Wong's pink sits at
#     dE 7.6 from the bluish green in slot 3 for a deuteranope, under the
#     dE >= 8 floor. The wine lifts that pair to 18.3 and brings every pair
#     among the first six to >= 8.6 across protan, deutan and tritan.
#   * canary yellow #F0E442 leaves the sequence. At 1.32:1 against white it
#     is invisible as a stroke on paper. Neutrals take the tail slots, where
#     a seventh series is a fallback rather than a design.
#
# Checked with a Machado (2009) CVD simulation scored in OKLab. Do not edit a
# hex here without re-running that check -- desaturating the set "to look more
# academic" is exactly what breaks it, because the CVD separation lives in the
# lightness ladder, not the hues.
COLORS = [
    "#0072B2",  # blue
    "#D55E00",  # vermillion
    "#009E73",  # bluish green
    "#882255",  # wine
    "#E69F00",  # orange
    "#56B4E9",  # sky blue
    "#4C4C4C",  # dark grey
    "#8C564B",  # brown
    "#7F7F7F",  # grey
    "#17BECF",  # cyan
    "#BCBD22",  # olive
    "#000000",  # black
]

COLOR_OTHER = "#AAAAAA"    # "Other" / residual category
COLOR_NEUTRAL = "#7F7F7F"  # a baseline series that is context, not a finding
COLOR_DARK = "#4C4C4C"     # a single emphasised series with no hue to spare

# Ask for these by name, never by index. The slots past COLORS[5] are a
# fallback tail and have been reordered once already; a script that reaches
# for COLORS[9] "because it is the grey one" breaks silently when it moves.

# ── Ink ────────────────────────────────────────────────────────────
# Text never wears a series colour: identity belongs to the mark beside the
# label, not to the label. Three weights of neutral is all a journal figure
# needs, and a coloured axis label is the fastest way to make one look like a
# dashboard.
INK       = "#1A1A1A"   # titles, axis labels, tick labels
INK_MUTED = "#5A5A5A"   # annotations, value labels, secondary notes
INK_RULE  = "#4D4D4D"   # spines and tick marks
GRID_COLOR = "#DDDDDD"

# Serif stack. "Times New Roman" is what the journal asks for but is not
# installed on most Linux machines; without the fallbacks below matplotlib
# resolves silently to DejaVu Serif, whose wide, low-contrast letterforms are
# the single clearest tell that a figure came out of a stock matplotlib. Nimbus
# Roman and Liberation Serif are metric-compatible Times clones; STIXGeneral
# ships inside matplotlib itself, so the stack always lands on a Times-like
# face rather than falling through.
SERIF_STACK = ["Times New Roman", "Nimbus Roman", "Liberation Serif",
               "STIXGeneral", "DejaVu Serif", "serif"]

# Bars are drawn as a tint of their own hue with the undiluted colour on the
# rim. A bar flooded with a saturated fill is the loudest object on the page.
BAR_FACE_L = 0.82   # target perceptual lightness (OKLab L) for a bar face
BAR_MAX_TINT = 0.68  # never wash a hue out past this, however dark it started
BAR_EDGE_LW = 0.7


def tint(color, amount):
    """Mix `amount` of white into `color`. amount=0 -> unchanged, 1 -> white."""
    r, g, b = mcolors.to_rgb(color)
    return (r + (1 - r) * amount,
            g + (1 - g) * amount,
            b + (1 - b) * amount)


def _oklab_l(rgb):
    """Perceptual lightness of an sRGB triple (Ottosson's OKLab L)."""
    lin = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
           for c in rgb]
    r, g, b = lin
    l = 0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b
    m = 0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b
    q = 0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b
    l, m, q = (max(v, 0) ** (1 / 3) for v in (l, m, q))
    return 0.2104542553 * l + 0.7936177850 * m - 0.0040720468 * q


def tint_to_lightness(color, target=BAR_FACE_L, max_amount=BAR_MAX_TINT):
    """Mix in only as much white as the hue needs to reach `target` lightness.

    A fixed mix ratio is the wrong instrument here: the palette spans OKLab L
    0.43 (wine) to 0.75 (orange), so a flat 45% white leaves the wine solid and
    bleaches the sky blue to nearly nothing. Aiming at a lightness instead
    gives every bar face the same visual weight across every figure, and the
    undiluted hue stays on the rim to carry the identity.
    """
    rgb = mcolors.to_rgb(color)
    if _oklab_l(rgb) >= target:
        return rgb
    lo, hi = 0.0, max_amount
    for _ in range(20):
        mid = (lo + hi) / 2
        if _oklab_l(tint(rgb, mid)) < target:
            lo = mid
        else:
            hi = mid
    return tint(rgb, hi)


# ── Style setup ───────────────────────────────────────────────────

def stack_colors(colors, amount=0.12):
    """Slightly lift stacked-area fills off full saturation.

    A stacked area is a wall of flat colour -- at full strength six of them
    fight each other and the page. A touch of white keeps the hue identity
    (and the CVD separation, which is measured on the source hues) while
    letting the boundaries do the work of telling the bands apart.
    """
    return [tint(c, amount) for c in colors]


# Pass with stackplot(): a hairline of the page colour between bands, so
# adjacent fills read as separate objects rather than one shape changing hue.
STACK_EDGE = {"edgecolor": "white", "linewidth": 0.6}


def apply_style():
    """Apply publication-quality rcParams."""
    plt.rcParams.update({
        # Type
        "font.family": "serif",
        "font.serif": SERIF_STACK,
        "mathtext.fontset": "stix",
        "font.size": 9,
        "axes.titlesize": 9.5,
        "axes.titleweight": "normal",
        "axes.titlelocation": "left",
        "axes.titlepad": 6.0,
        "axes.labelsize": 9,
        "axes.labelpad": 3.0,
        "xtick.labelsize": 8,
        "ytick.labelsize": 8,
        "legend.fontsize": 7.5,
        "legend.frameon": False,
        "legend.handlelength": 1.6,
        "legend.handletextpad": 0.5,
        "legend.labelspacing": 0.35,
        "legend.columnspacing": 1.1,
        "legend.borderpad": 0.2,
        # Ink
        "text.color": INK,
        "axes.labelcolor": INK,
        "axes.titlecolor": INK,
        "axes.edgecolor": INK_RULE,
        "xtick.color": INK_RULE,
        "ytick.color": INK_RULE,
        "xtick.labelcolor": INK,
        "ytick.labelcolor": INK,
        # Rules: thin, recessive, and behind the data
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.linewidth": 0.5,
        "axes.axisbelow": True,
        "xtick.major.width": 0.5,
        "ytick.major.width": 0.5,
        "xtick.major.size": 2.5,
        "ytick.major.size": 2.5,
        "xtick.major.pad": 2.5,
        "ytick.major.pad": 2.5,
        "xtick.minor.width": 0.4,
        "ytick.minor.width": 0.4,
        "xtick.minor.size": 1.5,
        "ytick.minor.size": 1.5,
        "grid.color": GRID_COLOR,
        "grid.linewidth": 0.5,
        "grid.alpha": 1.0,
        "axes.grid": False,   # finish_axes() enables the one axis that helps
        # Marks
        "lines.linewidth": 1.1,
        "lines.markersize": 3.2,
        "lines.markeredgewidth": 0.0,
        "lines.solid_capstyle": "round",
        "patch.linewidth": 0.6,
        "hatch.linewidth": 0.5,
        # Output
        "figure.facecolor": "white",
        "axes.facecolor": "white",
        "figure.dpi": 150,
        "savefig.dpi": 400,
        "savefig.facecolor": "white",
        "savefig.bbox": "tight",
        "savefig.pad_inches": 0.03,
        "pdf.fonttype": 42,       # TrueType in PDF (editable text)
        "ps.fonttype": 42,
    })


# Output formats for save_figure(). PNG alone is enough while iterating; set
# SLR_FIG_PDF=1 (or add "pdf" here) to also emit vector PDFs, which is what a
# journal will want at submission -- rcParams already sets pdf.fonttype = 42 so
# the text stays selectable and embeddable.
FIGURE_FORMATS = ["png"]
if os.environ.get("SLR_FIG_PDF"):
    FIGURE_FORMATS = ["pdf", "png"]


def save_figure(fig, name, formats=None, finish=True):
    """Save the figure to FIG_DIR in each of FIGURE_FORMATS.

    `finish` runs the whole-figure polish pass (grid on the measure axis, bar
    tinting) over every axes just before writing. It happens here rather than
    in format_axes() because scripts call format_axes() at whatever point suits
    them -- often before the bars exist -- whereas at save time the figure is
    complete and the pass can read what was actually drawn.
    """
    if finish:
        finish_figure(fig)
    os.makedirs(FIG_DIR, exist_ok=True)
    for ext in (formats or FIGURE_FORMATS):
        path = os.path.join(FIG_DIR, f"{name}.{ext}")
        fig.savefig(path, dpi=400 if ext == "png" else None)
        print(f"  Saved {path}")
    plt.close(fig)


def format_axes(ax):
    """Remove top/right spines, integer y-ticks."""
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.yaxis.set_major_locator(MaxNLocator(integer=True))


# ── Finishing pass ────────────────────────────────────────────────

def _bar_patches(ax):
    """Rectangles that came from ax.bar/ax.barh, in data-unit form."""
    return [p for p in ax.patches if isinstance(p, Rectangle) and p.get_label() != "_nolegend_bg"]


def _bar_orientation(ax):
    """'h', 'v', or None. Uses the same width>height test as add_bar_labels."""
    bars = _bar_patches(ax)
    if not bars:
        return None
    horiz = sum(1 for b in bars if b.get_width() > b.get_height())
    return "h" if horiz > len(bars) / 2 else "v"


def _has_raster(ax):
    """True for heatmaps -- an image or mesh would sit on top of a grid."""
    if ax.images:
        return True
    return any(isinstance(c, QuadMesh) for c in ax.collections)


def soften_bars(ax, edge_lw=BAR_EDGE_LW):
    """Repaint solid bars as a tint of their hue with the full colour on the rim.

    The hue still carries identity and the crisp edge gives the eye something
    to measure against, but the fill stops shouting. Patches the script already
    gave an edge colour are left alone -- that is a deliberate choice upstream.
    """
    for p in _bar_patches(ax):
        if getattr(p, "_slr_softened", False):
            continue
        face = p.get_facecolor()
        edge = p.get_edgecolor()
        if face[3] == 0:            # unfilled: nothing to soften
            continue
        if edge[3] > 0 and tuple(edge[:3]) != tuple(face[:3]):
            continue                # script set its own edge; respect it
        base = face[:3]
        p.set_edgecolor(base)
        p.set_linewidth(edge_lw)
        p.set_facecolor(tuple(tint_to_lightness(base)) + (face[3],))
        p._slr_softened = True


def style_boxplot(bp, color=None, median_color=None):
    """Give a patch_artist boxplot the same ink as the rest of the figures.

    matplotlib's stock boxplot draws heavy near-black box, whisker and cap
    lines and a median in its own default orange -- a hue from a palette this
    project does not use, sitting on top of every box. Here the structure goes
    to the thin neutral rule colour and the median carries the series hue,
    which is the one line in a box that is actually a measurement.
    """
    color = color or COLORS[0]
    face = tuple(tint_to_lightness(color))
    for patch in bp.get("boxes", []):
        patch.set_facecolor(face)
        patch.set_edgecolor(INK_RULE)
        patch.set_linewidth(0.6)
        patch.set_alpha(1.0)
    for key in ("whiskers", "caps"):
        for line in bp.get(key, []):
            line.set_color(INK_RULE)
            line.set_linewidth(0.6)
    for line in bp.get("medians", []):
        line.set_color(median_color or color)
        line.set_linewidth(1.1)
    for pt in bp.get("fliers", []):
        pt.set_marker("o")
        pt.set_markersize(2.0)
        pt.set_markerfacecolor("none")
        pt.set_markeredgecolor(INK_MUTED)
        pt.set_markeredgewidth(0.4)
        pt.set_alpha(0.7)
    return bp


def finish_axes(ax, grid="auto", bars=True):
    """Recessive grid on the measure axis, softened bar fills.

    grid: "auto" reads the axes' own bars -- horizontal bars want the rule
    running across them (x), everything else wants it behind them (y). Pass
    "x"/"y"/"both"/None to override. Heatmaps are skipped: their image would
    cover the grid anyway.
    """
    if _has_raster(ax):
        return
    if bars:
        soften_bars(ax)
    if grid == "auto":
        grid = "x" if _bar_orientation(ax) == "h" else "y"
    if grid:
        ax.set_axisbelow(True)
        ax.grid(True, axis=grid, color=GRID_COLOR, linewidth=0.5, zorder=0)


def finish_figure(fig, grid="auto"):
    """Run finish_axes() over a figure, once per physical axes position.

    A twinx() pair occupies one position; gridding both draws two sets of rules
    at unrelated y values, which is worse than no grid at all. The first axes
    at a position gets the grid, its twin gets bar softening only.
    """
    seen = set()
    for ax in fig.axes:
        key = tuple(round(v, 4) for v in ax.get_position().bounds)
        first = key not in seen
        seen.add(key)
        finish_axes(ax, grid=grid if first else None)


def add_bar_labels(ax, bars, fmt="{:.0f}", fontsize=6.5, offset=0.5,
                   color=INK_MUTED):
    """Add value labels to bars.

    Muted by default: the bar carries the magnitude, the number is a lookup
    aid. Black numerals at body size compete with the data they annotate.
    """
    for bar in bars:
        val = bar.get_width() if bar.get_width() != 0 else bar.get_height()
        if val == 0:
            continue
        if bar.get_width() > bar.get_height():
            # horizontal bar
            ax.text(bar.get_width() + offset, bar.get_y() + bar.get_height() / 2,
                    fmt.format(val), va="center", ha="left", fontsize=fontsize,
                    color=color)
        else:
            # vertical bar
            ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + offset,
                    fmt.format(val), va="bottom", ha="center", fontsize=fontsize,
                    color=color)



# ── Shared constants ─────────────────────────────────────────────────────────

# Task keys and display labels are DERIVED from the ontology, which is the
# single source of truth for domain vocabulary. Six labels are abbreviated for
# figure axes, where the full ontology name is too long to read at 7pt; every
# other label is the ontology's own. Do not hand-maintain either map -- five
# separate copies had drifted apart before this was centralised (one was
# missing security_analysis entirely, silently dropping the fifth-largest
# task from that analysis).
from slr_ontology import CHIP_DESIGN_TASKS as _CHIP_TASKS  # noqa: E402

TASK_KEYS = set(_CHIP_TASKS)

TASK_LABEL_SHORT = {
    "design_space_exploration": "Design Space Expl.",
    "lithography_optimization": "Lithography Opt.",
    "process_optimization":     "Process Opt.",
    "reliability_analysis":     "Reliability",
    "thermal_management":       "Thermal Mgmt",
    "security_analysis":        "Security",
}

TASK_LABEL = {k: TASK_LABEL_SHORT.get(k, v.label) for k, v in _CHIP_TASKS.items()}

# Method display labels, on the same footing as TASK_LABEL: the ontology key is
# an identifier, not a caption, and "general_ml_signals" printed on an axis is
# the clearest sign a figure is showing its own plumbing. Two registers --
# METHOD_LABEL reads as prose in a legend or a bar label, METHOD_LABEL_TIGHT is
# for a heatmap axis where a long name would have to be rotated to fit.
from slr_ontology import AI_METHODS as _AI_METHODS  # noqa: E402

METHOD_LABEL_OVERRIDE = {
    # The ontology name is right but too long for a figure axis.
    "evolutionary_optimization": "Evolutionary Optimization",
    "generative_adversarial":    "GANs",
}

METHOD_LABEL = {k: METHOD_LABEL_OVERRIDE.get(k, v.label)
                for k, v in _AI_METHODS.items()}

METHOD_LABEL_TIGHT = {
    "deep_learning":             "Deep Learning",
    "classical_ml":              "Classical ML",
    "graph_neural_networks":     "GNN",
    "general_ml_signals":        "General ML",
    "bayesian_probabilistic":    "Bayesian",
    "reinforcement_learning":    "RL",
    "llm_foundation_models":     "LLM / Foundation",
    "evolutionary_optimization": "Evolutionary Opt.",
    "symbolic_reasoning":        "Symbolic",
    "generative_adversarial":    "GAN",
    "transfer_learning":         "Transfer Learning",
    "anomaly_detection":         "Anomaly Detection",
}


def method_label(key, tight=False):
    """Display name for an AI-method key. Falls back to a de-slugged key."""
    table = METHOD_LABEL_TIGHT if tight else METHOD_LABEL
    return table.get(key) or METHOD_LABEL.get(key) or key.replace("_", " ").title()


def year_axis(ax, years, positions=None, max_labels=7, fontsize=None):
    """Label a year axis horizontally, thinning rather than rotating.

    A rotated year label is a symptom, not a style -- four digits only collide
    because every single year is being labelled. Label every k-th year, keep
    the rest as minor ticks so the reader still sees the full grid, and always
    keep the last year, which anchors how a trend gets read.

    `positions` is for axes where x is an index rather than the year itself
    (grouped bars, box plots): pass the same sequence handed to set_xticks().
    """
    years = list(years)
    if not years:
        return
    pos = list(positions) if positions is not None else list(years)
    step = max(1, -(-len(years) // max_labels))
    keep = list(range(0, len(years), step))
    if keep[-1] != len(years) - 1:
        # the final year always earns a label; absorb it into the last slot
        # rather than appending a tick a fraction of a step away from it
        if len(years) - 1 - keep[-1] < step and len(keep) > 1:
            keep[-1] = len(years) - 1
        else:
            keep.append(len(years) - 1)
    ax.set_xticks([pos[i] for i in keep])
    ax.set_xticklabels([str(years[i]) for i in keep], rotation=0, ha="center",
                       **({"fontsize": fontsize} if fontsize else {}))
    if step > 1:
        ax.set_xticks(pos, minor=True)


# Method-axis display filter. anomaly_detection is an AI_METHODS class, so it
# participates in the M predicate that admits papers to the corpus, but unlike
# every other class it names a problem formulation rather than a method family
# -- anomaly/outlier/changepoint detection is something you do WITH deep
# learning or classical ML, not an alternative to them. It is excluded from
# figures that plot a method dimension, and left in the ontology so that the
# corpus is unchanged. Reclassifying it as a chip task is the real fix, but
# that moves the corpus and belongs to a future run.
DISPLAY_EXCLUDE_METHODS = {"anomaly_detection"}


def display_methods(tags):
    """Method tags minus the classes that are not method families."""
    return [t for t in tags if t not in DISPLAY_EXCLUDE_METHODS]



VENUE_ALIASES = {"Integration the VLSI Journal": "Integration"}

SHORT_VENUE = {
    "IEEE Transactions on Computer Aided Design of Integrated Circuits and Systems":
        "IEEE TCAD",
    "ACM Transactions on Design Automation of Electronic Systems":
        "ACM TODAES",
    "IEEE Transactions on Semiconductor Manufacturing":
        "IEEE TSM",
    "Microelectronics Reliability":
        "Microelec. Reliability",
    "Microelectronics Journal":
        "Microelec. Journal",
    "IEEE Transactions on Very Large Scale Integration VLSI Systems":
        "IEEE TVLSI",
    "Integration":
        "Integration",
    "Journal of Industrial Information Integration":
        "J. Ind. Info. Integ.",
}

# Region sets
ESTABLISHED_LEADERS = {"China", "United States"}
EUROPE = {
    "Germany", "France", "United Kingdom", "Netherlands", "Belgium",
    "Switzerland", "Austria", "Italy", "Denmark", "Greece", "Portugal",
    "Sweden", "Finland", "Spain", "Norway", "Ireland", "Poland",
    "Czech Republic", "Hungary", "Romania", "Croatia", "Serbia",
    "Bulgaria", "Slovenia", "Lithuania", "Latvia", "Estonia",
    "Luxembourg", "Slovakia", "Cyprus", "Malta",
}
EAST_ASIA_TIGERS = {"South Korea", "Taiwan", "Japan", "Singapore", "Hong Kong"}


def get_region(country):
    if country in ESTABLISHED_LEADERS:
        return country
    if country in EUROPE:
        return "Europe"
    if country in EAST_ASIA_TIGERS:
        return "East Asia (excl. China)"
    if country == "Canada":
        return "Canada"
    return "Emerging & Other"


# ── Analog / Digital classification ──────────────────────────────────────────

ANALOG_TASKS = {"analog_circuit_design", "calibration"}
DIGITAL_TASKS = {
    "placement", "routing", "timing_analysis", "logic_synthesis",
    "test_generation", "verification", "hotspot_detection",
}
ANALOG_TITLE_KW = [
    "analog", "mixed-signal", "mixed signal", "adc", "dac",
    "pll", "phase-locked", "phase locked",
    "op-amp", "opamp", "operational amplifier",
    "amplifier design", "amplifier circuit",
    "ota", "lna", "vco", "mixer",
    "rf circuit", "rf design", "rf ic", "rfic",
    "transistor sizing", "analog ic", "analog layout",
    "comparator", "bandgap", "ldo", "voltage regulator",
    "oscillator design", "ring oscillator",
]
DIGITAL_TITLE_KW = [
    "digital", "fpga", "rtl", "verilog", "vhdl", "systemverilog",
    "netlist", "gate-level", "gate level",
    "flip-flop", "flip flop", "flop",
    "asic", "standard cell", "cell library",
    "soc ", "system-on-chip", "system on chip",
    "microprocessor", "processor design",
    "noc", "network-on-chip", "network on chip",
    "cache", "boolean", "logic circuit", "logic gate",
]


def classify_analog_digital(chip_tasks, title):
    """Return one of: analog, digital, both, domain-agnostic."""
    tasks = set(chip_tasks)
    t = title.lower()
    has_analog = bool(tasks & ANALOG_TASKS) or any(kw in t for kw in ANALOG_TITLE_KW)
    has_digital = bool(tasks & DIGITAL_TASKS) or any(kw in t for kw in DIGITAL_TITLE_KW)
    if has_analog and has_digital:
        return "both"
    elif has_analog:
        return "analog"
    elif has_digital:
        return "digital"
    return "domain-agnostic"


# ── Commercial application classification ────────────────────────────────────

TASK_TO_CAT = {
    "placement": "eda", "routing": "eda", "timing_analysis": "eda",
    "logic_synthesis": "eda", "design_space_exploration": "eda",
    "power_analysis": "eda", "hotspot_detection": "eda",
    "analog_circuit_design": "analog_ms",
    "lithography_optimization": "manufacturing", "process_optimization": "manufacturing",
    "yield_prediction": "manufacturing", "wafer_map_analysis": "manufacturing",
    "defect_detection": "manufacturing",
    "calibration": "modeling_sim",
    "test_generation": "test_diag", "fault_diagnosis": "test_diag",
    "verification": "test_diag",
    "reliability_analysis": "reliability", "thermal_management": "reliability",
    "security_analysis": "security",
}

TITLE_KW_CAT = [
    ("eda", ["placement", "routing", "floor plan", "floorplan",
             "timing closure", "timing analysis", "static timing",
             "logic synthesis", "high-level synthesis", "hls",
             "power grid", "ir drop", "power delivery",
             "design space exploration", "dse", "standard cell", "cell library"]),
    ("analog_ms", ["analog", "mixed-signal", "mixed signal",
                   "adc", "dac", "pll", "op-amp", "opamp", "ota", "lna", "vco",
                   "amplifier design", "transistor sizing", "analog ic",
                   "rf circuit", "rf design", "rfic"]),
    ("manufacturing", ["lithography", "opc", "mask optimization", "inverse lithography",
                       "yield prediction", "yield enhancement", "yield optimization",
                       "wafer map", "wafer bin", "wafer-level",
                       "defect detection", "defect classification",
                       "process control", "process optimization",
                       "etch", "cmp", "deposition", "metrology", "virtual metrology"]),
    ("modeling_sim", ["compact model", "spice model", "device model",
                      "parameter extraction", "model extraction",
                      "circuit modeling", "device characterization",
                      "surrogate model", "metamodel", "simulation acceleration"]),
    ("test_diag", ["test generation", "atpg", "test pattern",
                   "fault diagnosis", "fault localization",
                   "verification", "formal verification",
                   "coverage prediction", "debug"]),
    ("reliability", ["reliability", "aging", "degradation", "electromigration",
                     "bti", "nbti", "hci", "tddb", "wear-out",
                     "soft error", "seu", "single event upset",
                     "fault injection", "fault tolerance",
                     "failure rate", "lifetime prediction",
                     "thermal management", "thermal-aware"]),
    ("security", ["hardware trojan", "trojan detection",
                  "counterfeit", "puf", "physically unclonable",
                  "side-channel", "side channel"]),
]

CAT_LABEL = {
    "eda": "EDA",
    "analog_ms": "Analog/Mixed-Signal",
    "manufacturing": "Manufacturing",
    "modeling_sim": "Modeling & Simulation",
    "test_diag": "Test & Diagnosis",
    "reliability": "Reliability",
    "security": "Security",
    "other": "Other",
}

COMMERCIAL_CATS = ["eda", "reliability", "manufacturing", "analog_ms",
                   "test_diag", "security", "modeling_sim", "other"]


def classify_commercial(chip_tasks, title):
    """Return commercial application category."""
    cat_votes = Counter()
    for t in chip_tasks:
        cat = TASK_TO_CAT.get(t)
        if cat:
            cat_votes[cat] += 1
    if cat_votes:
        priority = ["eda", "analog_ms", "manufacturing", "modeling_sim",
                     "test_diag", "reliability", "security"]
        top_count = cat_votes.most_common(1)[0][1]
        for cat in priority:
            if cat_votes.get(cat, 0) == top_count:
                return cat
    title_lower = title.lower()
    for cat, keywords in TITLE_KW_CAT:
        if any(kw in title_lower for kw in keywords):
            return cat
    return "other"


# ── Survey detection ─────────────────────────────────────────────────────────

# Survey / review detection.
#
# Plain substring matching on ["survey", "review", ...] produced false
# positives on titles where the word is part of a method or instrument name --
# "Review-SEM" (a defect-review scanning electron microscope) and "A
# Self-Review Bayesian Optimization Method" were both classified as surveys.
# Word boundaries alone do not help, because the hyphen is itself a boundary.
# We therefore match the PHRASES in which a genuine survey announces itself.
SURVEY_QUALIFIER = (r"(?:comprehensive|systematic|brief|short|critical|recent|"
                    r"literature|extensive|concise)\s+")
SURVEY_PATTERNS = [
    rf"\ba\s+(?:{SURVEY_QUALIFIER})?survey\b",
    r"\bsurvey\s+(?:of|on|for)\b",
    rf"\ba\s+(?:{SURVEY_QUALIFIER})?review\b",
    r"\breview\s+(?:of|on)\b",
    r"\ban?\s+overview\s+(?:of|on)\b",
    r"\boverview\s+(?:of|on)\b",
    r"\ba\s+tutorial\b|\btutorial\s+(?:on|for)\b",
    r"\ba\s+taxonomy\b|\btaxonomy\s+(?:of|for)\b",
    r"\bstate[- ]of[- ]the[- ]art\s+(?:review|survey)\b",
    r"\bsystematic\s+literature\s+review\b",
]
_SURVEY_RX = [_re_survey.compile(p, _re_survey.I) for p in SURVEY_PATTERNS]
# Retained for reference; no longer used for matching.
SURVEY_KW = ["survey", "review", "overview", "tutorial", "taxonomy"]


def is_survey_title(title):
    """True when the title announces itself as a survey/review/tutorial."""
    t = title or ""
    return any(rx.search(t) for rx in _SURVEY_RX)



def is_survey(title):
    return is_survey_title(title)


# ── Soft error / deposition topic matching ───────────────────────────────────

SOFT_ERROR_KW = [
    "soft error", "soft-error", "seu", "single event upset", "single-event upset",
    "silent data", "sdc", "transient fault", "fault injection", "fault tolerance",
    "radiation effect", "cosmic ray", "alpha particle", "critical flip-flop",
]
SOFT_ERROR_EXCLUDE = [
    "multi-bit flip-flop", "pseudo approximation", "failure rate estimation",
    "failure rates in pulsed", "yield analysis",
]
DEPOSITION_KW = [
    "atomic layer deposition", "ald", "chemical vapor deposition", "cvd",
    "pecvd", "mocvd", "lpcvd", "physical vapor deposition", "pvd",
    "sputtering", "thin film", "thin-film", "film deposition", "film thickness",
    "deposition process", "deposition control", "deposition condition",
    "epitaxy", "epitaxial", "virtual metrology", "deposition",
]


def matches_topic(title_lower, keywords, exclude=None):
    if exclude:
        for ex in exclude:
            if ex in title_lower:
                return False
    return any(kw in title_lower for kw in keywords)


# ── Trend labeling ───────────────────────────────────────────────────────────

def trend_label(counts_by_year, all_years):
    """Classify trajectory based on year-by-year counts."""
    years_present = sorted(y for y in all_years if counts_by_year.get(y, 0) > 0)
    if not years_present:
        return "inactive"
    values = [counts_by_year.get(y, 0) for y in all_years]
    peak_year = max(all_years, key=lambda y: counts_by_year.get(y, 0))
    peak_val = counts_by_year[peak_year]
    total = sum(values)
    recent_years = all_years[-3:]
    recent_sum = sum(counts_by_year.get(y, 0) for y in recent_years)
    recent_share = recent_sum / total if total > 0 else 0
    last_val = counts_by_year.get(all_years[-1], 0)
    second_last_val = counts_by_year.get(all_years[-2], 0)
    if total <= 3:
        return "too few data points"
    if peak_year in all_years[-2:] and recent_share >= 0.5:
        return f"RISING (peak {peak_year})"
    elif peak_year == all_years[-1]:
        return f"RISING (peak {peak_year})"
    elif last_val >= peak_val * 0.8 and recent_share >= 0.4:
        return f"RISING (near peak, peak {peak_year})"
    elif peak_year in all_years[-3:] and last_val >= peak_val * 0.5:
        return f"STABLE-HIGH (peak {peak_year})"
    elif last_val < peak_val * 0.5 and peak_year not in all_years[-3:]:
        return f"DECLINING (peaked {peak_year})"
    elif last_val == 0 and second_last_val == 0:
        return f"FADED (peaked {peak_year})"
    elif peak_year in all_years[len(all_years) // 2:]:
        return f"STABLE (peak {peak_year})"
    else:
        return f"MIXED (peak {peak_year})"


# ── Statistics helpers ───────────────────────────────────────────────────────

def h_index(citations):
    s = sorted(citations, reverse=True)
    h = 0
    for i, c in enumerate(s):
        if c >= i + 1:
            h = i + 1
        else:
            break
    return h


def percentile(values, p):
    if not values:
        return 0
    k = (len(values) - 1) * p / 100
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return values[int(k)]
    return values[f] * (c - k) + values[c] * (k - f)


# ── Data loaders ─────────────────────────────────────────────────────────────

def _curation_sets():
    """DOIs excluded by manual curation, plus the doc_id -> doi map needed to
    apply them (the CSV carries no DOI column).

    EXCLUDE_DOIS lives in analysis/generate_stage_shortlist.py, which is the
    record of every curation decision. Imported lazily and defensively so a
    missing analysis/ directory degrades to "no exclusions" rather than
    breaking every figure.
    """
    import os as _os
    import sys as _sys
    excl = set()
    try:
        _sys.path.insert(0, _os.path.join(SCRIPT_DIR, "analysis"))
        from generate_stage_shortlist import EXCLUDE_DOIS as _E
        excl = {d.lower() for d in _E}
    except Exception:
        pass
    doi_by_doc = {}
    try:
        with open(JSON_PATH, encoding="utf-8") as f:
            for rec in json.load(f):
                doi_by_doc[rec["doc_id"]] = (rec.get("doi") or "").lower()
    except Exception:
        pass
    return excl, doi_by_doc


def load_csv_papers(year_max=-1, curated=True):
    """Load ai4chips CSV → list of dicts with method_tags and chip_tasks.

    Returns list of {doc_id, stage, year, title, source, classification,
    confidence, method_tags: [str], chip_tasks: [str]}.

    year_max caps the publication year. It defaults to DISPLAY_YEAR_MAX, which
    excludes the partially-indexed final year — correct for TIME-SERIES
    figures, where a partial year would read as a downturn. AGGREGATE figures
    (cross-tabulations, totals, heatmaps) should pass year_max=None to use the
    whole corpus; there is no reason to discard papers from a cross-tab, and
    doing so silently makes figure Ns disagree with the reported corpus size.
    """
    if year_max == -1:
        year_max = DISPLAY_YEAR_MAX
    # curated=True applies the same manual curation the manuscript reports --
    # survey/review removal and the manually identified false positives -- so
    # that figure Ns match the corpus size stated in the text. Pass False to
    # see the raw high-confidence corpus.
    excl, doi_by_doc = _curation_sets() if curated else (set(), {})
    papers = []
    with open(CSV_PATH, "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        next(reader)  # skip header
        for row in reader:
            doc_id = row[0].strip()
            if not doc_id:
                continue
            yr = int(row[2])
            if year_max is not None and yr > year_max:
                continue
            mtags = []
            ctasks = []
            # Columns 8+ hold MULTI-VALUE fields joined by "; " — method_tags
            # (bare keys) then ai_methods / chip_tasks (key:surface_form).
            # They must be split on ";" first: without it a paper tagged
            # "deep_learning; graph_neural_networks" was counted as a single
            # distinct category rather than under each method, and only the
            # FIRST chip task of each paper survived.
            for val in row[8:]:
                for part in val.split(";"):
                    v = part.strip()
                    if not v:
                        continue
                    if ":" in v:
                        key = v.split(":")[0].strip()
                        if key in TASK_KEYS:
                            ctasks.append(key)
                    else:
                        mtags.append(v)
            if curated:
                if is_survey_title(row[3]):
                    continue
                if doi_by_doc.get(doc_id, "") in excl:
                    continue
            papers.append({
                "doc_id": doc_id,
                "stage": row[1].strip(),
                "year": yr,
                "title": row[3],
                "source": VENUE_ALIASES.get(row[4].strip(), row[4].strip()),
                "classification": row[5].strip(),
                "confidence": row[6].strip(),
                "method_tags": list(dict.fromkeys(mtags)),
                "chip_tasks": list(dict.fromkeys(ctasks)),
            })
    return papers


def load_json_papers(year_max=-1):
    """Load ai4chips JSON → list of dicts with cited_by_count + affiliations.

    year_max follows the same convention as load_csv_papers(): it defaults to
    DISPLAY_YEAR_MAX (drop the partial final year, correct for time series);
    pass None to keep the whole corpus. AGGREGATE figures must pass None here
    as well as to load_csv_papers() -- otherwise the CSV side keeps the final
    year but the JSON side drops it, and those papers silently arrive with
    empty affiliations and zero citations.
    """
    if year_max == -1:
        year_max = DISPLAY_YEAR_MAX
    with open(JSON_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    if year_max is None:
        return data
    return [p for p in data if int(p.get("year", 0)) <= year_max]


def load_jsonl_papers(year_max=-1):
    """Load full corpus JSONL → list of dicts.

    year_max follows the same convention as load_csv_papers(): defaults to
    DISPLAY_YEAR_MAX, pass None to keep all 14,551 screened records.
    """
    if year_max == -1:
        year_max = DISPLAY_YEAR_MAX
    papers = []
    with open(JSONL_PATH, "r", encoding="utf-8") as f:
        for line in f:
            rec = json.loads(line)
            yr = rec.get("year")
            try:
                if year_max is not None and yr is not None and int(yr) > year_max:
                    continue
            except (TypeError, ValueError):
                pass
            papers.append(rec)
    return papers


def merge_csv_json(year_max=-1, curated=True):
    """Merge CSV (methods/tasks) with JSON (citations/affiliations) on doc_id.

    year_max is forwarded to BOTH loaders; pass None for aggregate figures
    that should use the whole corpus. See load_csv_papers().
    """
    csv_papers = load_csv_papers(year_max=year_max, curated=curated)
    json_papers = load_json_papers(year_max=year_max)
    json_lookup = {p["doc_id"]: p for p in json_papers}
    merged = []
    for cp in csv_papers:
        jp = json_lookup.get(cp["doc_id"], {})
        merged.append({
            **cp,
            "cited_by_count": int(jp.get("cited_by_count") or 0),
            "affiliations": jp.get("affiliations") or [],
            "publication": jp.get("publication", cp["source"]),
        })
    return merged


def cagr(start_val, end_val, periods):
    """Compound annual growth rate."""
    if start_val <= 0 or periods <= 0:
        return None
    return (end_val / start_val) ** (1 / periods) - 1
