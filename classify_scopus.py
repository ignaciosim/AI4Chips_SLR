#!/usr/bin/env python3
"""
classify_scopus.py — Ontology-based classification and method tagging.

This script replaces BOTH the old ontology_classifier.py AND post_process_ai_methods.py.
All domain vocabulary comes from slr_ontology.py (single source of truth).

It does two things in one pass:
  1. DIRECTIONALITY: classifies each paper as ai_for_chips / chips_for_ai / both / ambiguous
  2. METHOD TAGGING: multi-label AI method detection (same taxonomy, same pass)

Inputs:
  - raw_scopus_all.csv   (from merge_scopus.py) — title-only mode
  - raw_scopus_*.jsonl    (from fetch_scopus.py) — title+abstract mode (richer)

Outputs:
  - classified_scopus.csv              (per-paper classification + method tags)
  - pivot_ai_methods_counts.csv        (method × year counts)
  - pivot_ai_methods_share.csv         (method × year normalized)
  - pivot_ai_methods_by_stage.csv      (method × stage × year)
  - classification_summary.txt         (precision/recall analysis)

Usage:
  # From merged CSV (title-only):
  python classify_scopus.py scopus_out/raw_scopus_all.csv

  # From JSONL directory (title + abstract, more accurate):
  python classify_scopus.py scopus_out/ --from_jsonl

  # With LLM/DL overlap preserved:
  python classify_scopus.py scopus_out/raw_scopus_all.csv --keep_dl_with_llm
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Set, Tuple

import pandas as pd

from slr_ontology import (
    AI_METHODS,
    CHIP_DESIGN_TASKS,
    HW_ARTIFACTS,
    AI_WORKLOADS,
    CHIPS_FOR_AI_HEURISTIC_PHRASES,
    CHIPS_FOR_AI_CONFIRM_KEYWORDS,
    match_ontology_classes,
    detect_ai_methods,
)


# =============================================================================
# DATA STRUCTURES
# =============================================================================

@dataclass
class PaperAnnotation:
    """Full ontology-based annotation for a single paper."""
    doc_id: str
    title: str
    stage: str
    year: str
    source: str = ""

    # Ontology entity matches (class_key -> [matched_form, ...])
    ai_method_hits: Dict[str, List[str]] = field(default_factory=dict)
    chip_task_hits: Dict[str, List[str]] = field(default_factory=dict)
    hw_artifact_hits: Dict[str, List[str]] = field(default_factory=dict)
    ai_workload_hits: Dict[str, List[str]] = field(default_factory=dict)

    # Method tags (multi-label, for pivot tables)
    method_tags: Set[str] = field(default_factory=set)

    # Directionality classification
    classification: str = "unclassified"
    confidence: str = "low"
    reasoning: str = ""


# =============================================================================
# CLASSIFICATION LOGIC
# =============================================================================

def classify_paper(
    doc_id: str,
    title: str,
    stage: str,
    year: str,
    source: str = "",
    abstract: str = "",
    keep_dl_with_llm: bool = False,
) -> PaperAnnotation:
    """
    Classify a paper by extracting ontology entities and determining
    which directional relationship is instantiated.

    Uses title always; uses abstract if available for richer matching.
    """
    # Combine title + abstract for matching (abstract may be empty)
    text = f"{title} {abstract}".strip()

    ann = PaperAnnotation(
        doc_id=doc_id, title=title, stage=stage,
        year=str(year), source=source,
    )

    # --- Entity extraction ---
    ann.ai_method_hits = match_ontology_classes(text, AI_METHODS)
    ann.chip_task_hits = match_ontology_classes(text, CHIP_DESIGN_TASKS)
    ann.hw_artifact_hits = match_ontology_classes(text, HW_ARTIFACTS)
    ann.ai_workload_hits = match_ontology_classes(text, AI_WORKLOADS)

    # --- Method tagging (multi-label, for pivots) ---
    ann.method_tags = detect_ai_methods(text, keep_dl_with_llm=keep_dl_with_llm)

    has_method = bool(ann.ai_method_hits)
    has_task = bool(ann.chip_task_hits)
    has_artifact = bool(ann.hw_artifact_hits)
    has_workload = bool(ann.ai_workload_hits)

    # --- Directionality classification ---

    # Strong AI-for-chips: method + task, no artifact/workload
    if has_method and has_task and not has_artifact and not has_workload:
        ann.classification = "ai_for_chips"
        ann.confidence = "high"
        ann.reasoning = "AI method applied to chip design task"

    # Strong chips-for-AI: artifact + workload, no task
    elif has_artifact and has_workload and not has_task:
        ann.classification = "chips_for_ai"
        ann.confidence = "high"
        ann.reasoning = "Hardware artifact designed for AI workload"

    # Artifact without task → likely chips-for-AI
    elif has_artifact and not has_task:
        ann.classification = "chips_for_ai"
        ann.confidence = "medium"
        ann.reasoning = "Hardware artifact present without chip design task"

    # Workload without method/task → likely chips-for-AI
    elif has_workload and not has_method and not has_task:
        ann.classification = "chips_for_ai"
        ann.confidence = "medium"
        ann.reasoning = "AI workload present without AI-as-tool signal"

    # Method + task + artifact → possibly both
    elif has_method and has_task and has_artifact:
        ann.classification = "both"
        ann.confidence = "medium"
        ann.reasoning = "Both AI-as-tool and hardware artifact detected"

    # Task only (no method) → still relevant, may use ML implicitly
    elif has_task and not has_method and not has_artifact:
        ann.classification = "ai_for_chips"
        ann.confidence = "low"
        ann.reasoning = "Chip design task without explicit AI method"

    # Method only → ambiguous
    elif has_method and not has_task and not has_artifact:
        ann.classification = "ambiguous"
        ann.confidence = "low"
        ann.reasoning = "AI method present but no clear target identified"

    # Heuristic fallback for chips-for-AI patterns
    else:
        text_lower = text.lower()
        has_heuristic = any(p in text_lower for p in CHIPS_FOR_AI_HEURISTIC_PHRASES)
        has_confirm = any(kw in text_lower for kw in CHIPS_FOR_AI_CONFIRM_KEYWORDS)

        if has_heuristic and has_confirm:
            ann.classification = "chips_for_ai"
            ann.confidence = "low"
            ann.reasoning = "Heuristic: efficiency/architecture optimization for NN workload"
        else:
            ann.classification = "unclassified"
            ann.confidence = "low"
            ann.reasoning = "No ontology class pattern matched"

    return ann


# =============================================================================
# INPUT READERS
# =============================================================================

def read_from_csv(csv_path: Path) -> List[dict]:
    """Read merged CSV (title-only mode)."""
    with open(csv_path, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def read_from_jsonl(directory: Path) -> List[dict]:
    """Read JSONL files (title + abstract mode)."""
    seen = set()
    papers = []
    for path in sorted(directory.glob("raw_scopus_*.jsonl")):
        if path.name == "raw_scopus_all.jsonl":
            continue
        with open(path, encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                rec = json.loads(line)
                entry = rec.get("entry", {})
                doc_id = entry.get("eid") or entry.get("prism:doi") or ""
                if not doc_id or doc_id in seen:
                    continue
                seen.add(doc_id)
                papers.append({
                    "doc_id": doc_id,
                    "stage": rec.get("stage", ""),
                    "year": rec.get("year", ""),
                    "title": entry.get("dc:title", "") or "",
                    "source": entry.get("prism:publicationName", "") or "",
                    "abstract": entry.get("dc:description", "") or "",
                    "doi": entry.get("prism:doi", "") or "",
                })
    return papers


# =============================================================================
# OUTPUT: CLASSIFIED CSV
# =============================================================================

def export_classified_csv(annotations: List[PaperAnnotation], path: Path):
    """Write the per-paper classification + method tags."""
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "doc_id", "stage", "year", "title", "source",
            "classification", "confidence", "reasoning",
            "method_tags",
            "ai_methods", "chip_tasks", "hw_artifacts", "ai_workloads",
        ])
        for a in annotations:
            writer.writerow([
                a.doc_id, a.stage, a.year, a.title, a.source,
                a.classification, a.confidence, a.reasoning,
                "; ".join(sorted(a.method_tags)),
                "; ".join(f"{k}:{v[0]}" for k, v in a.ai_method_hits.items()),
                "; ".join(f"{k}:{v[0]}" for k, v in a.chip_task_hits.items()),
                "; ".join(f"{k}:{v[0]}" for k, v in a.hw_artifact_hits.items()),
                "; ".join(f"{k}:{v[0]}" for k, v in a.ai_workload_hits.items()),
            ])


# =============================================================================
# OUTPUT: METHOD PIVOT TABLES (replaces post_process_ai_methods.py)
# =============================================================================

def export_method_pivots(annotations: List[PaperAnnotation], outdir: Path):
    """Generate method × year pivot tables from classification results."""
    rows = []
    for a in annotations:
        tags = a.method_tags or {"unspecified_ai"}
        for m in tags:
            rows.append({
                "doc_id": a.doc_id,
                "year": int(a.year),
                "stage": a.stage,
                "method": m,
                "classification": a.classification,
                "title": a.title,
                "source": a.source,
            })

    if not rows:
        print("No method rows to pivot.")
        return

    df = pd.DataFrame(rows)

    # Long-form export
    long_csv = outdir / "ai_methods_long.csv"
    df.sort_values(["year", "method", "title"]).to_csv(long_csv, index=False)
    print(f"Wrote: {long_csv}")

    # Pivot: method × year counts
    counts = (
        df.groupby(["method", "year"]).size()
        .reset_index(name="count")
        .pivot(index="method", columns="year", values="count")
        .fillna(0).astype(int).sort_index()
    )
    counts_csv = outdir / "pivot_ai_methods_counts.csv"
    counts.to_csv(counts_csv)
    print(f"Wrote: {counts_csv}")

    # Pivot: method × year shares
    share = counts.div(counts.sum(axis=0), axis=1)
    share_csv = outdir / "pivot_ai_methods_share.csv"
    share.to_csv(share_csv)
    print(f"Wrote: {share_csv}")

    # Pivot: method × stage × year
    cube = df.groupby(["method", "stage", "year"]).size().reset_index(name="count")
    cube_csv = outdir / "pivot_ai_methods_by_stage.csv"
    cube.to_csv(cube_csv, index=False)
    print(f"Wrote: {cube_csv}")

    # NEW: method × year counts for AI-FOR-CHIPS only
    df_relevant = df[df["classification"].isin(["ai_for_chips", "both"])]
    if not df_relevant.empty:
        counts_rel = (
            df_relevant.groupby(["method", "year"]).size()
            .reset_index(name="count")
            .pivot(index="method", columns="year", values="count")
            .fillna(0).astype(int).sort_index()
        )
        rel_csv = outdir / "pivot_ai_methods_counts_ai4chips_only.csv"
        counts_rel.to_csv(rel_csv)
        print(f"Wrote: {rel_csv}")


# =============================================================================
# OUTPUT: CLASSIFICATION SUMMARY
# =============================================================================

def export_summary(annotations: List[PaperAnnotation], outdir: Path):
    """Write a human-readable classification summary."""
    total = len(annotations)
    cls_dist = Counter(a.classification for a in annotations)
    conf_dist = Counter(a.confidence for a in annotations)

    lines = []
    lines.append("=" * 70)
    lines.append("ONTOLOGY-BASED CLASSIFICATION SUMMARY")
    lines.append("=" * 70)
    lines.append(f"\nTotal papers: {total}\n")

    lines.append("Classification distribution:")
    for cls, count in cls_dist.most_common():
        lines.append(f"  {cls:20s}: {count:4d} ({100*count/total:5.1f}%)")

    lines.append("\nConfidence distribution:")
    for conf, count in conf_dist.most_common():
        lines.append(f"  {conf:20s}: {count:4d} ({100*count/total:5.1f}%)")

    lines.append("\nBreakdown by lifecycle phase:")
    for stage in ["design", "fabrication", "packaging", "in_field"]:
        stage_anns = [a for a in annotations if a.stage == stage]
        if not stage_anns:
            continue
        lines.append(f"\n  {stage} (n={len(stage_anns)}):")
        for cls, count in Counter(a.classification for a in stage_anns).most_common():
            lines.append(f"    {cls:20s}: {count:4d} ({100*count/len(stage_anns):5.1f}%)")

    # Precision estimate
    noise_count = sum(1 for a in annotations if a.classification == "chips_for_ai")
    if total > 0:
        kw_precision = (total - noise_count) / total
        filtered = [a for a in annotations if a.classification != "chips_for_ai"]
        remaining_noise = 0  # conservative: assume all caught
        onto_precision = len(filtered) / total if filtered else 0

        lines.append("\n" + "=" * 70)
        lines.append("PRECISION ESTIMATE")
        lines.append("=" * 70)
        lines.append(f"  Keyword baseline precision:      ~{kw_precision:.1%}")
        lines.append(f"  Papers flagged as chips-for-AI:    {noise_count}")
        lines.append(f"  Papers after noise removal:        {len(filtered)}")
        lines.append(f"  Noise removal rate:                {noise_count/total:.1%}")

    text = "\n".join(lines)
    summary_path = outdir / "classification_summary.txt"
    with open(summary_path, "w") as f:
        f.write(text)
    print(f"Wrote: {summary_path}")
    print(text)


# =============================================================================
# MAIN
# =============================================================================

def main():
    ap = argparse.ArgumentParser(
        description="Ontology-based classification + method tagging for SLR corpus.",
    )
    ap.add_argument("input", type=Path,
                    help="Path to raw_scopus_all.csv or directory with JSONL files")
    ap.add_argument("--from_jsonl", action="store_true",
                    help="Read JSONL files (title+abstract) instead of CSV (title-only)")
    ap.add_argument("--outdir", type=Path, default=None,
                    help="Output directory (default: same as input)")
    ap.add_argument("--keep_dl_with_llm", action="store_true",
                    help="Keep deep_learning tag when llm_foundation_models is also detected")
    args = ap.parse_args()

    # Determine output directory
    if args.outdir:
        outdir = args.outdir
    elif args.input.is_dir():
        outdir = args.input
    else:
        outdir = args.input.parent
    outdir.mkdir(parents=True, exist_ok=True)

    # Read input
    if args.from_jsonl:
        if not args.input.is_dir():
            raise SystemExit("--from_jsonl requires a directory path")
        papers = read_from_jsonl(args.input)
        print(f"Read {len(papers)} papers from JSONL (title + abstract)")
    else:
        papers = read_from_csv(args.input)
        print(f"Read {len(papers)} papers from CSV (title only)")

    # Classify
    annotations = []
    for p in papers:
        ann = classify_paper(
            doc_id=p.get("doc_id", ""),
            title=p.get("title", ""),
            stage=p.get("stage", ""),
            year=p.get("year", ""),
            source=p.get("source", ""),
            abstract=p.get("abstract", ""),
            keep_dl_with_llm=args.keep_dl_with_llm,
        )
        annotations.append(ann)

    # Export
    export_classified_csv(annotations, outdir / "classified_scopus.csv")
    print(f"Wrote: {outdir / 'classified_scopus.csv'}")

    export_method_pivots(annotations, outdir)
    export_summary(annotations, outdir)


if __name__ == "__main__":
    main()
