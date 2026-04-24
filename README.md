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

## Runbook (one-command pipeline)

From a fresh clone, the whole Scopus pipeline is a `make` away. The
Makefile encodes the stage order, tracks output timestamps (so re-runs
skip fresh stages), and scopes all outputs to a per-run data directory.

```bash
# 0. Install pinned dependencies into a virtualenv.
make setup
source .venv/bin/activate

# 1. Verify credentials and dependencies before spending hours on fetch.
make preflight

# 2. Run the whole Scopus pipeline end-to-end into a new data directory.
make all DATADIR=scopus_out11

# 3. Optional companion analyses.
make analysis DATADIR=scopus_out11          # text-output analyses
make patents  DATADIR=scopus_out11          # patent-landscape (BigQuery)
```

`make all` runs `fetch → merge → classify → final → shortlist → figures`
in order. Outputs accumulate inside `scopus_out11/`; the master figures
land in `scopus_out11/figures/`. Running `make all` a second time is a
no-op (the Makefile tracks output file timestamps), so you can safely
re-run to check status.

### Prerequisites

The `make setup` step installs every Python dependency; you only need
two external credentials:

| Credential | Needed for | How to provide |
|---|---|---|
| Scopus API key | `make fetch`, `make all` | `../config.json` with `{"scopus_api_key": "..."}` (override path with `CONFIG=`) |
| Google Cloud auth | `make patents` (optional) | `gcloud auth application-default login` — sets up BigQuery client |

The `make preflight` target sanity-checks both before running anything.

### Overridable Makefile variables

| Variable | Default | Purpose |
|---|---|---|
| `DATADIR` | `scopus_out10` | Per-run data / output directory |
| `CONFIG` | `../config.json` | Scopus API config |
| `VENUES` | `../venues_eda.txt` | Venue allow-list |
| `START_YEAR` | `2015` | Retrieval window start |
| `END_YEAR` | `2026` | Retrieval window end |
| `MAX_PAGES` | `80` | Scopus pagination cap per phase |
| `GCP_PROJECT` | *(auto-detect)* | GCP project for BigQuery |

All are passed on the command line, e.g.:
`make all DATADIR=scopus_out11 START_YEAR=2018 END_YEAR=2025`.

### Housekeeping

`make clean DATADIR=scopus_out11` removes derived outputs but preserves the
raw Scopus fetch (which is expensive to regenerate). `make nuke` removes
the entire per-run directory. `make -n all` prints the command chain as a
dry run without executing.

### Known failure modes

| Symptom | Cause | Fix |
|---|---|---|
| `fetch_scopus.py` stalls at ~25 records | Scopus API rate limit | Re-run; the script resumes from the next page. Reduce `--max_pages` if needed. |
| `analysis/patent_analysis.py` raises `DefaultCredentialsError` | BigQuery auth missing | `gcloud auth application-default login`, then re-run `make patents`. |
| Figures missing citation counts | OpenAlex cache empty or stale | First run `python3 figures/fig_linguistic_terms.py` to warm the cache (standalone; not in `make all`). |

## Usage (individual scripts — low-level)

### Prerequisites

```bash
pip install -r requirements.txt
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
