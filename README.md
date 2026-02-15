# SLR Pipeline — Ontology-Driven Refactor

Systematic Literature Review pipeline for AI applications in chip design.
All domain vocabulary is defined **once** in `slr_ontology.py` and consumed
by every downstream script.

## Architecture

```
slr_ontology.py              ← single source of truth (vocabulary, taxonomy, query builders)
    │
    ├── fetch_scopus.py       ← step 1: Scopus API retrieval
    │       │
    │       ▼
    │   raw_scopus_<phase>.jsonl + .csv
    │       │
    │   merge_scopus.py       ← step 2: deduplicate + flatten (no domain knowledge)
    │       │
    │       ▼
    │   raw_scopus_all.csv
    │       │
    └── classify_scopus.py    ← step 3: entity extraction + directionality + method tagging
            │
            ▼
        classified_scopus.csv
        ai_methods_long.csv
        pivot_ai_methods_counts.csv
        pivot_ai_methods_share.csv
        pivot_ai_methods_by_stage.csv
        pivot_ai_methods_counts_ai4chips_only.csv
        classification_summary.txt
```

## What changed (old → new)

| Old script                         | New script            | What happened                                                    |
|------------------------------------|-----------------------|------------------------------------------------------------------|
| `fetch_scopus_lifecycle_rest.py`   | `fetch_scopus.py`     | STAGES, CHIP_ANCHOR, AI_UMBRELLA moved to `slr_ontology.py`     |
| `merge_raw_scopus.py`             | `merge_scopus.py`     | Renamed. No logic change (pure plumbing).                        |
| `post_process_ai_methods.py`      | *(deleted)*           | AI_METHODS taxonomy → `slr_ontology.py`. Pivot logic → `classify_scopus.py` |
| `ontology_classifier.py`          | `classify_scopus.py`  | Now also handles method tagging + pivot tables. Reads vocabulary from ontology. |
| *(new)*                            | `slr_ontology.py`     | Single source of truth for all domain knowledge.                 |

### Why the old pipeline had redundancy

1. **`fetch_scopus_lifecycle_rest.py`** had `STAGES`, `CHIP_ANCHOR`, `AI_UMBRELLA` — these are ontological statements about which terms belong to which lifecycle phase and domain.
2. **`post_process_ai_methods.py`** had `AI_METHODS` — a method taxonomy with surface forms. This duplicated the `AIMethod` class from the ontology classifier.
3. **`ontology_classifier.py`** had `ONTOLOGY_LEXICON` — which re-encoded all of the above plus HW artifacts and AI workloads.

All three maintained parallel copies of overlapping vocabulary. If you added a new AI method or chip design task, you had to update 2–3 files.

### What the refactor solves

`slr_ontology.py` defines every term exactly once. The fetcher reads its query vocabulary from the ontology. The classifier reads its entity lexicon from the ontology. If you add "diffusion model" as an AI method, you add it in one place and it propagates to both Scopus queries and paper classification.

## Usage

### Prerequisites

```bash
pip install requests pandas
```

### Step 1: Fetch from Scopus

```bash
# Basic (all phases, 2016–last full year)
python fetch_scopus.py --config config.json --ai_focus

# With venue filter and full pagination
python fetch_scopus.py --config config.json --ai_focus \
    --venues_file venues_eda.txt --max_pages 20

# Specific year range
python fetch_scopus.py --config config.json --ai_focus \
    --start_year 2019 --end_year 2025
```

Output: `scopus_out/raw_scopus_{design,fabrication,packaging,in_field}.jsonl`

### Step 2: Merge and deduplicate

```bash
python merge_scopus.py scopus_out
```

Output: `scopus_out/raw_scopus_all.csv`

### Step 3: Classify + tag methods

```bash
# From merged CSV (title-only classification)
python classify_scopus.py scopus_out/raw_scopus_all.csv

# From JSONL directory (title + abstract — more accurate if abstracts available)
python classify_scopus.py scopus_out/ --from_jsonl

# Keep deep_learning tag when LLM is also detected
python classify_scopus.py scopus_out/raw_scopus_all.csv --keep_dl_with_llm
```

### Optional: Export OWL ontology

```bash
python slr_ontology.py
# → silicon_lifecycle_ontology.owl (importable in Protégé)
```

## Output files

| File                                       | Description                                                   |
|--------------------------------------------|---------------------------------------------------------------|
| `classified_scopus.csv`                    | Per-paper: classification, confidence, method tags, entity matches |
| `ai_methods_long.csv`                      | Long-form: one row per (paper, method) pair                   |
| `pivot_ai_methods_counts.csv`              | Method × year counts (all papers)                             |
| `pivot_ai_methods_share.csv`               | Method × year normalized shares                               |
| `pivot_ai_methods_by_stage.csv`            | Method × stage × year                                         |
| `pivot_ai_methods_counts_ai4chips_only.csv`| Method × year counts (only ai_for_chips + both)               |
| `classification_summary.txt`               | Human-readable summary with precision estimate                |

## Classification labels

| Label          | Meaning                                             | Ontology pattern                        |
|----------------|-----------------------------------------------------|-----------------------------------------|
| `ai_for_chips` | AI/ML used as a **tool** for chip design            | `methodAppliedToTask(AIMethod, Task)`   |
| `chips_for_ai` | Chip designed as a **product** for AI workloads     | `artifactForWorkload(Artifact, Workload)` |
| `both`         | Paper addresses both directions                     | Method + Task + Artifact detected       |
| `ambiguous`    | AI method detected but no clear target              | Method only, no task or artifact        |
| `unclassified` | No ontology pattern matched                         | Needs manual screening                  |

## Extending the ontology

All vocabulary lives in `slr_ontology.py`. To add a new concept:

```python
# Add a new AI method
AI_METHODS["diffusion_models"] = OntologyClass(
    key="diffusion_models",
    label="Diffusion Models",
    surface_forms=[
        "diffusion model", "denoising diffusion", "score-based",
        "stable diffusion", "ddpm",
    ],
)

# Add a new chip design task
CHIP_DESIGN_TASKS["emi_analysis"] = OntologyClass(
    key="emi_analysis",
    label="EMI Analysis",
    surface_forms=[
        "electromagnetic interference", "emi analysis",
        "emi simulation", "radiated emission",
    ],
)
```

Changes propagate to all scripts automatically on next run.
