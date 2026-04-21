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
import argparse
import json
from collections import defaultdict
from pathlib import Path

YEAR_MAX = 2026  # shortlist is a curation aid, not a public figure
CURRENT_YEAR = 2026  # for cites/year normalization

SURVEY_KW = ["survey", "review", "overview", "tutorial", "taxonomy"]

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
    return any(k in title for k in SURVEY_KW)


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
    "10.1109/tvlsi.2025.3590317": "transit",
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

        if n < 10:
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
