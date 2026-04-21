"""Shared plotting module for AI4Chips SLR publication-quality figures.

Provides:
  - Matplotlib rcParams (serif fonts, 9pt, no top/right spines, tight layout)
  - Colorblind-safe palette with fixed domain assignments
  - Data loaders (CSV, JSON, JSONL) — centralized, no duplication
  - Classification helpers (analog/digital, commercial area, survey detection)
  - Trend labeling, venue normalization, shared constants
"""

import csv
import json
import math
import os
from collections import Counter, defaultdict

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator

# ── Paths ────────────────────────────────────────────────────────────────────

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(SCRIPT_DIR, "scopus_out7")
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

# ── Colorblind-safe palette (Wong 2011 + extensions) ────────────────────────

COLORS = [
    "#0072B2",  # blue
    "#D55E00",  # vermillion
    "#009E73",  # bluish green
    "#CC79A7",  # reddish purple
    "#E69F00",  # orange
    "#56B4E9",  # sky blue
    "#F0E442",  # yellow
    "#000000",  # black
    "#8C564B",  # brown
    "#7F7F7F",  # gray
    "#17BECF",  # cyan
    "#BCBD22",  # olive
]

COLOR_OTHER = "#AAAAAA"  # gray for "Other" category

# ── Style setup ──────────────────────────────────────────────────────────────

def apply_style():
    """Apply publication-quality rcParams."""
    plt.rcParams.update({
        "font.family": "serif",
        "font.serif": ["Times New Roman", "DejaVu Serif", "serif"],
        "font.size": 9,
        "axes.titlesize": 10,
        "axes.labelsize": 9,
        "xtick.labelsize": 8,
        "ytick.labelsize": 8,
        "legend.fontsize": 7.5,
        "legend.frameon": False,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.linewidth": 0.6,
        "xtick.major.width": 0.6,
        "ytick.major.width": 0.6,
        "lines.linewidth": 1.2,
        "lines.markersize": 4,
        "figure.dpi": 150,
        "savefig.dpi": 300,
        "savefig.bbox": "tight",
        "savefig.pad_inches": 0.05,
        "pdf.fonttype": 42,       # TrueType in PDF (editable text)
        "ps.fonttype": 42,
    })


def save_figure(fig, name):
    """Save figure as PDF and PNG to the figures directory."""
    os.makedirs(FIG_DIR, exist_ok=True)
    pdf_path = os.path.join(FIG_DIR, name + ".pdf")
    png_path = os.path.join(FIG_DIR, name + ".png")
    fig.savefig(pdf_path)
    fig.savefig(png_path, dpi=300)
    plt.close(fig)
    print(f"  Saved {pdf_path}")
    print(f"  Saved {png_path}")


def format_axes(ax):
    """Remove top/right spines, integer y-ticks."""
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.yaxis.set_major_locator(MaxNLocator(integer=True))


def add_bar_labels(ax, bars, fmt="{:.0f}", fontsize=7, offset=0.5):
    """Add value labels to bars."""
    for bar in bars:
        val = bar.get_width() if bar.get_width() != 0 else bar.get_height()
        if val == 0:
            continue
        if bar.get_width() > bar.get_height():
            # horizontal bar
            ax.text(bar.get_width() + offset, bar.get_y() + bar.get_height() / 2,
                    fmt.format(val), va="center", ha="left", fontsize=fontsize)
        else:
            # vertical bar
            ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + offset,
                    fmt.format(val), va="bottom", ha="center", fontsize=fontsize)


# ── Shared constants ─────────────────────────────────────────────────────────

TASK_KEYS = {
    "placement", "routing", "timing_analysis", "logic_synthesis",
    "power_analysis", "design_space_exploration", "analog_circuit_design",
    "verification", "calibration", "lithography_optimization",
    "hotspot_detection", "defect_detection", "yield_prediction",
    "wafer_map_analysis", "process_optimization", "test_generation",
    "fault_diagnosis", "reliability_analysis", "thermal_management",
    "security_analysis",
}

TASK_LABEL = {
    "placement": "Placement",
    "routing": "Routing",
    "timing_analysis": "Timing Analysis",
    "logic_synthesis": "Logic Synthesis",
    "power_analysis": "Power Analysis",
    "design_space_exploration": "Design Space Expl.",
    "analog_circuit_design": "Analog Circuit",
    "verification": "Verification",
    "calibration": "Calibration",
    "lithography_optimization": "Lithography Opt.",
    "hotspot_detection": "Hotspot Detection",
    "defect_detection": "Defect Detection",
    "yield_prediction": "Yield Prediction",
    "wafer_map_analysis": "Wafer Map Analysis",
    "process_optimization": "Process Opt.",
    "test_generation": "Test Generation",
    "fault_diagnosis": "Fault Diagnosis",
    "reliability_analysis": "Reliability",
    "thermal_management": "Thermal Mgmt",
    "security_analysis": "Security",
}

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

SURVEY_KW = ["survey", "review", "overview", "tutorial", "taxonomy"]


def is_survey(title):
    t = title.lower()
    return any(kw in t for kw in SURVEY_KW)


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

def load_csv_papers():
    """Load ai4chips CSV → list of dicts with method_tags and chip_tasks.

    Returns list of {doc_id, stage, year, title, source, classification,
    confidence, method_tags: [str], chip_tasks: [str]}. Papers with year >
    DISPLAY_YEAR_MAX are dropped.
    """
    papers = []
    with open(CSV_PATH, "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        next(reader)  # skip header
        for row in reader:
            doc_id = row[0].strip()
            if not doc_id:
                continue
            yr = int(row[2])
            if yr > DISPLAY_YEAR_MAX:
                continue
            mtags = []
            ctasks = []
            for val in row[8:]:
                v = val.strip()
                if not v:
                    continue
                if ":" in v:
                    key = v.split(":")[0].strip()
                    if key in TASK_KEYS:
                        ctasks.append(key)
                else:
                    mtags.append(v)
            papers.append({
                "doc_id": doc_id,
                "stage": row[1].strip(),
                "year": yr,
                "title": row[3],
                "source": VENUE_ALIASES.get(row[4].strip(), row[4].strip()),
                "classification": row[5].strip(),
                "confidence": row[6].strip(),
                "method_tags": mtags,
                "chip_tasks": list(dict.fromkeys(ctasks)),
            })
    return papers


def load_json_papers():
    """Load ai4chips JSON → list of dicts with cited_by_count + affiliations.
    Papers with year > DISPLAY_YEAR_MAX are dropped.
    """
    with open(JSON_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    return [p for p in data if int(p.get("year", 0)) <= DISPLAY_YEAR_MAX]


def load_jsonl_papers():
    """Load full corpus JSONL → list of dicts. Records with year >
    DISPLAY_YEAR_MAX are dropped.
    """
    papers = []
    with open(JSONL_PATH, "r", encoding="utf-8") as f:
        for line in f:
            rec = json.loads(line)
            yr = rec.get("year")
            try:
                if yr is not None and int(yr) > DISPLAY_YEAR_MAX:
                    continue
            except (TypeError, ValueError):
                pass
            papers.append(rec)
    return papers


def merge_csv_json():
    """Merge CSV (methods/tasks) with JSON (citations/affiliations) on doc_id."""
    csv_papers = load_csv_papers()
    json_papers = load_json_papers()
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
