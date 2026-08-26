#!/usr/bin/env python3
"""Per-stage shortlist of exemplar AI-for-Chips papers, for paper writing.

Output is a markdown file with one table per lifecycle stage. Each paper is
tagged with one of three roles:
  - Anchor   : top-cited papers (canonical/methodology-defining)
  - Exemplar : highest-cited paper for an otherwise-uncovered (method, task) pair
  - Recent   : high cites/year, published 2023+, not yet selected

Usage:
    python3 analysis/generate_stage_shortlist.py --datadir scopus_out10 \\
        --out scopus_out10/stage_shortlists.md
"""
import re as _re_survey
import argparse
import json
from collections import defaultdict
from pathlib import Path

YEAR_MAX = 2026  # shortlist is a curation aid, not a public figure
CURRENT_YEAR = 2026  # for cites/year normalization

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


# ── Analog / digital classification (mirrored from plot_style.py to avoid the
#    matplotlib import). Used for the Design stage balance rule.
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


def classify_analog_digital(paper):
    """Return one of: analog, digital, both, domain-agnostic."""
    tasks = set(parse_tasks(paper))
    t = (paper.get("title") or "").lower()
    has_analog = bool(tasks & ANALOG_TASKS) or any(kw in t for kw in ANALOG_TITLE_KW)
    has_digital = bool(tasks & DIGITAL_TASKS) or any(kw in t for kw in DIGITAL_TITLE_KW)
    if has_analog and has_digital:
        return "both"
    if has_analog:
        return "analog"
    if has_digital:
        return "digital"
    return "domain-agnostic"

# Manually curated false positives — papers that the automated pipeline
# classifies as ai_for_chips but are actually chips-for-AI or off-topic.
# Keyed by DOI (lowercase).
EXCLUDE_DOIS = {
    # Du Z. 2015: accelerators designed for running NNs, not AI applied to
    # chip design. Mis-tagged via "neural network" + "aging" keywords.
    "10.1109/tcad.2015.2419628",
    # Shi L. 2016: NAND flash write performance paper, no ML content; nonsensical
    # llm_foundation_models tag.
    "10.1109/tvlsi.2015.2393299",
    # Liu Y. 2025: chiplet platform for intelligent radar/sonar — chips-for-AI.
    "10.1109/tvlsi.2025.3529699",
    # Cheng J. 2026: multi-core near-DRAM compute architecture — chips-for-AI.
    "10.1016/j.mejo.2026.107063",
    # Zhan J. 2022: fault-tolerant DNN inference on hardware — chips-for-AI.
    "10.1109/tcad.2021.3129114",
    # Cheng S. 2016: lithium thionyl chloride battery lifetime — off-topic
    # (batteries, not chips); got in via keyword collision.
    "10.1016/j.microrel.2016.07.152",
    # Wang J. 2015: VLSI hardware to run SVM speaker verification — chips-for-AI.
    "10.1109/tvlsi.2014.2335112",
    # Burnham S.D. 2017: traditional GaN material reliability paper; survived the
    # GaN-material FP filter because the title uses "GaN Technology" generically.
    "10.1109/tsm.2017.2748921",
    # Pomeranz I. 2026: traditional algorithmic test-methodology paper; no ML
    # content, LLM tag is a keyword artifact.
    "10.1145/3786348",
    # Pandey S. 2022 NeuroMap: abstract-confirmed chips-for-AI. The paper
    # manages DNN execution on HBM via algorithmic task mapping + DVFS — no
    # learned ML. "Deep learning" in the title refers to the workload being
    # managed, not the method used.
    "10.1109/tcad.2022.3197698",
    # Bahador A. 2026 MRAM PUF: circuit-design paper; ML (LR/SVM/MLP/CNN/DNN/RL)
    # appears only as the attacker in the security evaluation. AI is not
    # applied to chip design.
    "10.1109/tcad.2026.3667088",
    # Roy K. 2026 (IET Energy Systems Integration): power-grid frequency
    # regulation, not chip-related. Got in via "data-driven" + "aging" +
    # "rag" keyword collisions. Venue should really have been filtered.
    "10.1049/esi2.70039",
    # Ma X. 2023: circuit-design paper where ML is the attacker (modeling
    # attacks on PUF); same ML-as-attacker pattern as Bahador 2026. Not AI
    # applied to chip design.
    "10.1016/j.mejo.2023.105977",
    # Ye X. 2018: subject matter is aerospace electromechanical relays
    # (shelf-storage degradation), not semiconductor ICs. Triggered by the
    # word "storage" and its venue (Microelectronics Reliability, which
    # covers relays under a broad definition).
    "10.1016/j.microrel.2018.06.085",
    # Ma C. 2025: axial piston hydraulic pumps — completely off-topic. Got
    # in via Digital Twin + fault diagnosis + ML keywords in J. Industrial
    # Information Integration, which also publishes semiconductor work.
    "10.1016/j.jii.2025.100966",
    # All remaining Pomeranz papers follow the same false-positive pattern:
    # classical LBIST / test-methodology work, no ML content. They slip the
    # filter because of a substring collision — the ontology's "ilt" surface
    # form (for lithography_optimization) matches "bu-ilt" in "Built-In
    # Self-Test". The llm_foundation_models tag is similarly spurious.
    "10.1109/tcad.2025.3536384",     # 2025, subvector rearrangement in LBIST
    "10.1145/3643810",               # 2024, On-chip seed storage for BIST
    "10.1109/tcad.2022.3233737",     # 2023, Storage-Based LBIST with cyclic tests
    "10.1109/tvlsi.2023.3285691",    # 2023, Storage-Based LBIST with partitioned deterministic tests
}


def is_survey(paper):
    title = (paper.get("title") or "").lower()
    return is_survey_title(title)


def is_excluded(paper):
    doi = (paper.get("doi") or "").lower()
    return doi in EXCLUDE_DOIS


# Manual stage reassignments where the automated classification placed a paper
# in the wrong lifecycle phase (typically because of vocabulary leakage across
# phase queries). Keyed by DOI (lowercase).
STAGE_OVERRIDES = {
    # Narwariya 2025: detecting recycled ICs re-entering the supply chain is
    # a transit / supply-chain integrity problem (cousin of counterfeit
    # detection), not an end-of-life disposal concern.
    # "10.1109/tvlsi.2025.3590317": "transit",  # retired: paper no longer
    #   satisfies the inclusion criteria after the matcher correction
    # Lee H. 2026 DRAM sense-amp UQ: this is chip *design* (BLSA circuit
    # sizing under process variation), not fabrication. Classified into
    # fabrication by a "process variation" keyword match.
    "10.1109/tcad.2025.3603112": "design",
    # Zhang W. 2021 optical NoC routing: thermal-aware routing of a silicon-
    # photonic NoC is a design-phase topic, not packaging. Vocabulary leaked
    # via "thermal management".
    "10.1109/tcad.2020.2987775": "design",
    # Zhao Y. 2025 PDNNet: dynamic IR drop prediction is classically a
    # design / sign-off task, not packaging.
    "10.1109/tcad.2024.3509796": "design",
    # Kao S.X. 2023 wire-bonding fault diagnosis: IC assembly equipment PHM;
    # packaging, not in-field operation. Classified via "fault diagnosis".
    "10.1109/tsm.2023.3243775": "packaging",
    # Gai T. 2022 hotspot detection: lithography-DFM hotspot detection is a
    # fabrication task. Classified into in-field via "reliability enhancement".
    "10.1109/tcad.2021.3135786": "fabrication",
}


def effective_stage(paper):
    doi = (paper.get("doi") or "").lower()
    return STAGE_OVERRIDES.get(doi, paper["stage"])


TABLE_DOIS = {
    # Pinned per-stage exemplar selection as printed in the manuscript.
    # Selected once from the candidate ranking below (Anchor/Exemplar/
    # Recent/Newest with per-stage quotas) and retained across revisions so
    # that this script reproduces the published tables exactly. Stages here
    # are post-STAGE_OVERRIDES, matching how the script groups papers.
    # Three v1 entries were removed because they no longer satisfy the
    # inclusion criteria after the matcher and deduplication corrections:
    #   10.1145/3626958                 RSMT construction (combinatorial, not ML)
    #   10.1016/j.microrel.2022.114553  BGA drop response (no chip-task term)
    #   10.1109/tvlsi.2025.3590317      IO pad / polynomial regression (no method term)
    "design": [   # 15 entries
        "10.1109/tcad.2022.3193330",                    # [39] A New Compact MOSFET Model Based on Artificial Neural Networ
        "10.1109/tcad.2022.3166637",                    # [37] An Analog Circuit Design and Optimization System With Rule-G
        "10.1109/tcad.2019.2961322",                    # [24] An Artificial Neural Network Assisted Optimization System fo
        "10.1109/tcad.2021.3081405",                    # [25] An Efficient Analog Circuit Sizing Method Based on Machine L
        "10.1109/tcad.2021.3054811",                    # [26] An Efficient Batch-Constrained Bayesian Optimization Approac
        "10.1109/tcad.2025.3582175",                    # [28] AnaCraft: Duel-Play Probabilistic-Model-Based Reinforcement 
        "10.1109/tcad.2025.3573228",                    # [32] Atelier: An Automated Analog Circuit Design Framework via Mu
        "10.1109/tcad.2021.3120547",                    # [27] Automated Design of Analog Circuits Using Reinforcement Lear
        "10.1109/tcad.2024.3383347",                    # [30] ChatEDA: A Large Language Model Powered Autonomous Agent for
        "10.1109/tvlsi.2021.3065639",                   # [36] Complementary-FET (CFET) Standard Cell Synthesis Framework f
        "10.1109/tcad.2020.3003843",                    # [33] DREAMPlace: Deep Learning Toolkit-Enabled GPU Acceleration f
        "10.1109/tcad.2021.3131550",                    # [34] GoodFloorplan: Graph Convolutional Network and Reinforcement
        "10.1109/tcad.2022.3185540",                    # [35] IronMan-Pro: Multiobjective Design Space Exploration in HLS 
        "10.1109/tcad.2025.3529805",                    # [31] LayoutCopilot: An LLM-Powered Multiagent Collaborative Frame
        "10.1145/3643681",                              # [29] VeriGen: A Large Language Model for Verilog Code Generation
    ],
    "fabrication": [   # 11 entries
        "10.1109/tcad.2015.2501307",                    # [47] A SVM surrogate model-based method for parametric yield opti
        "10.1109/tsm.2019.2945482",                     # [46] A wafer map yield prediction based on machine learning for p
        "10.1109/tsm.2021.3118922",                     # [45] Applying Data Augmentation and Mask R-CNN-Based Instance Seg
        "10.1016/j.jii.2025.100879",                    # [48] Deriving optimal atomic layer deposition process conditions 
        "10.1109/tcad.2023.3286262",                    # [43] DevelSet: Deep Neural Level Set for Instant Mask Optimizatio
        "10.1109/tcad.2019.2939329",                    # [41] GAN-OPC: Mask Optimization with Lithography-Guided Generativ
        "10.1109/tcad.2025.3650094",                    # [44] INN-ILT: Inverse Lithography Technique via Invertible Neural
        "10.1016/j.mejo.2022.105641",                   # [50] Linear regression combined KNN algorithm to identify latent 
        "10.1109/tsm.2021.3065405",                     # [49] Machine Learning-Based Detection Method for Wafer Test Induc
        "10.1109/tcad.2021.3109556",                    # [42] Neural-ILT 2.0: Migrating ILT to Domain-Specific and Multita
        "10.1109/tcad.2026.3661446",                    # [40] Understanding and Mitigating Errors of LLM-Generated RTL Cod
    ],
    "packaging": [   # 8 entries
        "10.1109/tcad.2025.3543436",                    # [58] A Lightweight Heterogeneous Graph Embedding Framework for Ho
        "10.1109/tvlsi.2025.3650633",                   # [57] A Physics-Informed Neural Network Surrogate for Runtime PDN 
        "10.1109/tsm.2023.3243775",                     # [51] Deep Learning-Based Positioning Error Fault Diagnosis of Wir
        "10.1016/j.vlsi.2014.06.003",                   # [52] Energy efficient adaptive clustering of on-chip power delive
        "10.1016/j.mejo.2022.105535",                   # [53] Frequency-scaled thermal-aware test scheduling for 3D ICs us
        "10.1145/3588570",                              # [55] GNN-based Multi-bit Flip-flop Clustering and Post-clustering
        "10.1145/3579843",                              # [56] ILP-based Substrate Routing with Mismatched Via Dimension Co
        "10.1109/tcad.2019.2950378",                    # [73] Robust Identification of Thermal Models for In-Production Hi
    ],
    "transit": [   # 7 entries
        "10.1016/j.vlsi.2025.102628",                   # [67] AI-enabled image processing approach for efficient clusterin
        "10.1109/tvlsi.2019.2949733",                   # [64] EMFORCED: EM-Based Fingerprinting Framework for Remarked and
        "10.1109/tcad.2024.3428469",                    # [63] GNN4HT: A Two-Stage GNN-Based Approach for Hardware Trojan M
        "10.1109/tvlsi.2022.3191683",                   # [59] Golden Reference-Free Hardware Trojan Localization Using Gra
        "10.1109/tcad.2022.3178355",                    # [60] Hardware Trojan Detection Using Graph Neural Networks
        "10.1109/tcad.2025.3569492",                    # [61] NetVGE: Netwise Hardware Trojan Detection at RTL Using Varia
        "10.1109/tcad.2024.3383348",                    # [62] Netwise Detection of Hardware Trojans Using Scalable Convolu
    ],
    "in_field": [   # 8 entries
        "10.1145/3567424",                              # [74] A Deep Learning Framework for Solving Stress-based Partial D
        "10.1109/tvlsi.2023.3237885",                   # [71] A Framework for Reliability Analysis of Combinational Circui
        "10.1109/tvlsi.2019.2925807",                   # [72] Hardware Trojan Detection Using Changepoint-Based Anomaly De
        "10.1016/j.mejo.2026.107133",                   # [75] Hybrid junction temperature prediction of IGBTs combining de
        "10.1016/j.microrel.2025.115996",               # [69] Neural network approach to NBTI/HCD coupled failure analysis
        "10.1109/tvlsi.2016.2593902",                   # [70] Postsilicon Trace Signal Selection Using Machine Learning Te
        "10.1016/j.microrel.2025.115797",               # [68] Solder joint reliability predictions using physics-informed 
        "10.1145/3564932",                              # [38] Worst-case Power Integrity Prediction Using Convolutional Ne
    ],
}


# Manual editorial promotions — force a paper into the shortlist for topical
# importance even if the citation-based selection would miss it. Use sparingly;
# these are deliberate editorial decisions overriding automated selection.
# Keyed by DOI (lowercase). "role" must be unique enough to appear as a
# Curator-tier row at the bottom of the stage's table.
PROMOTE_DOIS = {
    # Seo J. 2025: the only AI-for-ALD paper in the corpus. Atomic layer
    # deposition is central to advanced-node manufacturing but nearly absent
    # from the AI-for-Chips literature (1 of 321 high-confidence papers).
    # Citation-based selection misses it (4 cites, too new); promoting for
    # topicality.
    "10.1016/j.jii.2025.100879": {
        "stage": "fabrication",
        "role": "Curator",
    },
}


def promoted_for_stage(stage, candidate_papers, chosen_ids):
    """Return list of papers to append as Curator rows for this stage.
    Silently skips entries whose DOI isn't in the stage pool or whose paper
    was already selected by the normal algorithm."""
    out = []
    for doi, meta in PROMOTE_DOIS.items():
        if meta["stage"] != stage:
            continue
        paper = next((p for p in candidate_papers
                      if (p.get("doi") or "").lower() == doi.lower()), None)
        if paper and paper["doc_id"] not in chosen_ids:
            out.append((paper, meta["role"]))
    return out


def load_gists(outdir):
    """Load the curated per-paper gist dict (keyed by lowercased DOI).
    The file is created by reading abstracts manually and editing gists.json.
    Missing entries render as blank in the table."""
    path = Path(outdir, "gists.json")
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text())
    except Exception:
        return {}


def load_stage_summaries(outdir):
    """Per-stage narrative blurbs (keyed by stage key, e.g., 'design').
    Edit stage_summaries.json and regenerate to update."""
    path = Path(outdir, "stage_summaries.json")
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text())
    except Exception:
        return {}


def load_acronyms_block(outdir):
    """Read the acronyms.md glossary (if present) to inline at the top of
    the shortlist output. Users edit acronyms.md directly."""
    path = Path(outdir, "acronyms.md")
    if not path.exists():
        return ""
    return path.read_text().rstrip()

STAGE_ORDER = ["design", "fabrication", "packaging", "transit", "in_field", "disposal"]
STAGE_LABEL = {
    "design": "Design",
    "fabrication": "Fabrication",
    "packaging": "Packaging",
    "transit": "Transit",
    "in_field": "In-Field",
    "disposal": "Disposal",
}


def parse_methods(paper):
    tags = (paper.get("slr_classification") or {}).get("method_tags") or ""
    return [t.strip() for t in tags.split(",") if t.strip()]


def parse_tasks(paper):
    ctasks = (paper.get("slr_classification") or {}).get("chip_tasks") or ""
    keys = []
    for chunk in ctasks.split(";"):
        chunk = chunk.strip()
        if ":" in chunk:
            keys.append(chunk.split(":", 1)[0].strip())
    return keys


def primary_pair(paper):
    m = (parse_methods(paper) or ["?"])[0]
    t = (parse_tasks(paper) or ["?"])[0]
    return (m, t)


def cites(paper):
    try:
        return int(paper.get("cited_by_count") or 0)
    except (TypeError, ValueError):
        return 0


def cites_per_year(paper):
    age = CURRENT_YEAR - int(paper["year"]) + 0.5
    return cites(paper) / age if age > 0 else 0.0


def title_short(paper, maxlen=70):
    t = (paper.get("title") or "").strip()
    return t if len(t) <= maxlen else t[:maxlen].rstrip() + "…"


def doi_link(paper):
    d = (paper.get("doi") or "").strip()
    return f"[{d}](https://doi.org/{d})" if d else "—"


def format_row(paper, role, gists):
    m = (parse_methods(paper) or ["—"])[0]
    t = (parse_tasks(paper) or ["—"])[0]
    doi = (paper.get("doi") or "").lower()
    gist = gists.get(doi, "").replace("|", "\\|").replace("\n", " ")
    return (
        f"| {role} | {paper['year']} | {paper.get('creator') or '?'} "
        f"| {m} | {t} | {cites(paper)} "
        f"| {title_short(paper)} | {gist} | {doi_link(paper)} |"
    )


def shortlist_for_stage(papers, t_anchors, t_exemplars, t_recent, t_newest,
                        balance_analog_digital=False):
    papers = sorted(papers, key=cites, reverse=True)
    chosen = set()

    anchors = []
    covered_pairs = set()
    for p in papers:
        if len(anchors) >= t_anchors:
            break
        anchors.append(p)
        chosen.add(p["doc_id"])
        covered_pairs.add(primary_pair(p))

    # Best paper for each uncovered (method, task) pair, ranked by cites
    pair_to_best = {}
    for p in papers:
        if p["doc_id"] in chosen:
            continue
        pr = primary_pair(p)
        if pr in covered_pairs:
            continue
        if pr not in pair_to_best or cites(p) > cites(pair_to_best[pr]):
            pair_to_best[pr] = p
    candidates = sorted(pair_to_best.values(), key=cites, reverse=True)

    if balance_analog_digital:
        # Two-pass: first respect analog/digital caps, then fill remainder.
        # Cap: each domain gets at most ceil(t/2) of the t exemplar slots.
        cap = (t_exemplars + 1) // 2
        counts = {"analog": 0, "digital": 0, "both": 0, "domain-agnostic": 0}
        exemplars = []
        used = set()
        for p in candidates:
            if len(exemplars) >= t_exemplars:
                break
            dom = classify_analog_digital(p)
            if dom in ("analog", "digital") and counts[dom] >= cap:
                continue
            exemplars.append(p); counts[dom] += 1; used.add(p["doc_id"])
        for p in candidates:  # fill any unfilled slots, ignore cap
            if len(exemplars) >= t_exemplars:
                break
            if p["doc_id"] not in used:
                exemplars.append(p); used.add(p["doc_id"])
    else:
        exemplars = candidates[:t_exemplars]

    for p in exemplars:
        chosen.add(p["doc_id"])

    recent = [p for p in papers
              if int(p["year"]) >= 2023 and p["doc_id"] not in chosen]
    recent = sorted(recent, key=cites_per_year, reverse=True)[:t_recent]
    for p in recent:
        chosen.add(p["doc_id"])

    newest = [p for p in papers
              if int(p["year"]) == YEAR_MAX and p["doc_id"] not in chosen]
    newest = sorted(newest, key=cites, reverse=True)[:t_newest]
    return anchors, exemplars, recent, newest


# Per-stage overrides for target sizing. Design is expanded + balance-rule'd
# because analog/digital imbalance would otherwise dominate the exemplar slots.
STAGE_TARGETS = {
    "design": (5, 6, 2, 2),  # 15 total, exemplars balanced analog/digital
}

STAGE_BALANCE = {"design"}  # which stages apply analog/digital balance


def targets_for_size(n, stage=None):
    if stage and stage in STAGE_TARGETS:
        return STAGE_TARGETS[stage]
    # Uniform floor: any stage with n >= 10 gets up to 10 slots. Algorithm
    # returns fewer when recent/newest/exemplar candidates run out.
    if n >= 10:
        return (3, 3, 2, 2)
    return (0, 0, 0, 0)  # stages with n<10: list all


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--datadir", default="scopus_out10")
    ap.add_argument("--show-candidates", action="store_true",
                    help="Emit the algorithmic candidate ranking instead of "
                         "the pinned manuscript selection.")
    ap.add_argument("--out", default=None,
                    help="Markdown output path. If omitted, prints to stdout.")
    args = ap.parse_args()

    data = json.loads(Path(args.datadir, "final_ai4chips_high_only.json").read_text())
    papers = [p for p in data
              if int(p["year"]) <= YEAR_MAX
              and not is_survey(p)
              and not is_excluded(p)]
    n_surveys = sum(1 for p in data if is_survey(p) and int(p["year"]) <= YEAR_MAX)
    n_excluded = sum(1 for p in data if is_excluded(p) and int(p["year"]) <= YEAR_MAX)
    gists = load_gists(args.datadir)
    summaries = load_stage_summaries(args.datadir)
    acronyms_block = load_acronyms_block(args.datadir)
    by_stage = defaultdict(list)
    for p in papers:
        by_stage[effective_stage(p)].append(p)

    lines = [
        f"# Stage shortlists — AI for Chips (N={len(papers)}, 2015–{YEAR_MAX})",
        "",
        f"Surveys excluded: {n_surveys} (kw: survey/review/overview/tutorial/taxonomy). "
        f"Manual false-positive exclusions: {n_excluded}. "
        f"Stage overrides applied: {len(STAGE_OVERRIDES)}. "
        f"Curated gists loaded: {len(gists)}.",
        "Roles: **Anchor** = top-cited; **Exemplar** = best paper in an otherwise-uncovered "
        f"(method, task) pair; **Recent** = high cites/year from 2023+; **Newest** = {YEAR_MAX} "
        "papers surfaced regardless of citation count (too new to rank); **Curator** = "
        "editorial pick for topical importance where citation-based selection would miss it.",
        "Stages with fewer than 10 papers are listed in full.",
        "",
    ]
    if acronyms_block:
        lines.append(acronyms_block)
        lines.append("")

    for stage in STAGE_ORDER:
        ps = by_stage.get(stage, [])
        if not ps:
            continue
        n = len(ps)
        t_a, t_e, t_r, t_n = targets_for_size(n, stage=stage)
        balance = stage in STAGE_BALANCE
        lines.append(f"## {STAGE_LABEL[stage]} (n={n})")
        lines.append("")
        summary = summaries.get(stage)
        if summary:
            lines.append(summary)
            lines.append("")
        lines.append("| Role | Year | 1st author | Method | Task | Cites | Title | Gist | DOI |")
        lines.append("|---|---|---|---|---|---|---|---|---|")

        pinned = [] if args.show_candidates else (TABLE_DOIS.get(stage) or [])
        if pinned:
            # Emit the pinned manuscript selection. The algorithmic ranking is
            # still what the selection was drawn from and remains available via
            # --show-candidates; pinning keeps this script an exact record of
            # the published tables rather than a generator of a different set.
            index = {(p.get("doi") or "").lower(): p for p in ps}
            missing = [d for d in pinned if d not in index]
            for d in pinned:
                p = index.get(d)
                if p is not None:
                    lines.append(format_row(p, "Table", gists))
            if missing:
                print(f"  WARNING [{stage}]: {len(missing)} pinned DOI(s) not in "
                      f"the corpus for this stage: {missing}")
        elif n < 10:
            for p in sorted(ps, key=cites, reverse=True):
                lines.append(format_row(p, "All", gists))
        else:
            anchors, exemplars, recent, newest = shortlist_for_stage(
                ps, t_a, t_e, t_r, t_n, balance_analog_digital=balance)
            for p in anchors:
                lines.append(format_row(p, "Anchor", gists))
            for p in exemplars:
                lines.append(format_row(p, "Exemplar", gists))
            for p in recent:
                lines.append(format_row(p, "Recent", gists))
            for p in newest:
                lines.append(format_row(p, "Newest", gists))
            # Editorial curator picks appended at the end of the stage table
            chosen_ids = {p["doc_id"] for p in anchors + exemplars + recent + newest}
            for paper, role in promoted_for_stage(stage, ps, chosen_ids):
                lines.append(format_row(paper, role, gists))
        lines.append("")

    output = "\n".join(lines)
    if args.out:
        Path(args.out).write_text(output)
        print(f"Wrote: {args.out}  ({sum(1 for L in lines if L.startswith('|') and not L.startswith('|---')) - sum(1 for L in lines if L.startswith('| Role'))} paper rows)")
    else:
        print(output)


if __name__ == "__main__":
    main()
