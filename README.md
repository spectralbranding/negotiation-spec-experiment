[![MIT License](https://img.shields.io/badge/Code-MIT-blue.svg)](LICENSE)
[![CC-BY 4.0](https://img.shields.io/badge/Data-CC--BY_4.0-lightgrey.svg)](LICENSE-data)
![Last Updated](https://img.shields.io/badge/updated-2026--06--08-success)

# Value Headroom Moderates Whether Specification Beats Style in LLM Negotiation

> Companion repository for the empirical note of the same title. Concept DOI [`10.5281/zenodo.20595996`](https://doi.org/10.5281/zenodo.20595996).

---

## 1 | Overview

This repository accompanies an independent conceptual test of whether interpersonal *style* (warmth, dominance) or objective *specification* (ranked priorities, a reservation value, an explicit concession rule) matters more when two language-model agents negotiate. It identifies *value headroom* — the joint surplus a naively cooperative pair would leave on the table — as a first-order moderator: specification-first prompting ties style on near-ceiling scenarios but yields strictly higher joint value once headroom is present, with the advantage growing with model capability.

**Reconstruction disclosure.** The scenarios and harness here were authored independently, informed by public materials. This is *not* a one-to-one reproduction of any base study. The base study referenced for motivation is public at arXiv:2503.06416.

---

## 2 | Project Layout

```
.
├── paper.md                         # The empirical note (full text)
├── SPINE.yaml                       # Structured-substrate graph (spine-protocol)
├── PREREGISTRATION.md               # Study 1 preregistration
├── PREREGISTRATION_STUDY2.md        # Study 2 (headroom) preregistration
├── PILOT_GATE_AUDIT.md              # Pilot gate decisions + re-pilot record
├── EXPERIMENT_DESIGN.md             # Study 1 design
├── EXTENSION_DESIGN.md              # Extension arms design (ablation/frontier/paraphrase/headroom)
├── STUDY2_RATIONALE.md              # Why Study 2 (headroom) was run
├── LOGGING_AND_PROVENANCE_STANDARD.md  # LLM-call logging + provenance discipline
├── DATA_MANIFEST.yaml               # Dataset manifest
├── code/                            # Analysis + harness scripts (Python 3.12)
├── prompts/                         # Arm prompts + scorer prompts + prompt hashes
├── scenarios/                       # Study 1 scenarios
├── scenarios_study2/                # Study 2 scenarios
├── scenarios_headroom/              # Graded-headroom scenario family
├── data/outcomes.csv                # Study 1 per-dyad outcomes
├── data_study2/outcomes.csv         # Study 2 per-dyad outcomes
├── data_haiku/outcomes.csv          # Cross-family (Haiku) per-dyad outcomes
├── data_ablation_full/outcomes.csv  # Logrolling-vs-payoff-leak ablation
├── data_frontier/outcomes.csv       # Frontier-model arm per-dyad outcomes
├── data_paraphrase/outcomes.csv     # Prompt-paraphrase robustness arm
├── data_headroom/outcomes.csv       # Graded-headroom dose-response arm
├── output/{figures,tables,logs}/    # Generated artifacts (populated by reproduce.sh)
├── CITATION.cff                     # Machine-readable citation
├── LICENSE                          # MIT (code)
├── LICENSE-data                     # CC BY 4.0 (data, figures, tables)
├── pyproject.toml                   # Python project anchor + dependencies
└── reproduce.sh                     # Single-command pipeline reproduction
```

---

## 3 | Quick Start

Reproduce the per-arm contrasts and the headroom dose-response from the outcomes data:

```bash
./reproduce.sh
```

The script checks dependencies, runs `code/analyze.py` for each arm and `code/compute_headroom.py` for the graded-headroom arm, and tees run output to `output/logs/`.

---

## 4 | Dependencies

### Python ≥ 3.12 (managed with `uv`)

- `pandas`, `scipy`, `numpy`, `statsmodels`

Install with `uv sync`, or let `reproduce.sh` resolve them per-command via `uv run --with ...`.

### Provenance discipline (documented, not required to re-run analysis)

The original dyad-generation pipeline records every LLM/model API call in structured JSONL (operator, model version, full prompts, parameters, response, tokens, latency, cost, git SHA, timestamp), per `LOGGING_AND_PROVENANCE_STANDARD.md`. Those raw call logs and the full transcripts are **not** in this mirror (see section 7). The paper is drafted under the spine protocol; its structured-substrate graph ships here as the `SPINE.yaml` companion artifact.

---

## 5 | Script Map

| Script | Role |
|--------|------|
| `code/run_experiment.py` | Experiment harness — orchestrates dyad runs across arms |
| `code/negotiation_runner.py` | Single-dyad runner (turn loop, transcript capture) |
| `code/outcomes.py` | Per-dyad value/deal outcome computation |
| `code/scoring_llm.py` | Warmth/dominance + SVI scorers (LLM-judged measures) |
| `code/compute_icc.py` | Inter-scorer reliability (ICC) |
| `code/analyze.py` | Per-arm contrasts and effect sizes |
| `code/compute_headroom.py` | Graded-headroom dose-response (spec × headroom slope) |
| `code/gen_headroom_variants.py` | Headroom scenario generator + arithmetic verification |
| `code/backfill_scores.py` | Backfill LLM-judged scores onto existing transcripts |
| `code/rescore_transcripts.py` | Re-score transcripts under a revised scorer |
| `code/make_manifest.py` | Build the dataset manifest |
| `code/provider_errors.py` | Provider-error classification/retry helpers |
| `code/osf_publish.py` | Preregistration/archive publishing helper |
| `code/test_icc.py`, `code/test_outcomes.py`, `code/test_robustness.py` | Unit tests |

---

## 6 | Citation

If you build on this work, please cite:

> Dmitry Zharnikov (2026). "Value Headroom Moderates Whether Specification Beats Style in LLM Negotiation." DOI [`10.5281/zenodo.20595996`](https://doi.org/10.5281/zenodo.20595996).

Machine-readable citation: see [`CITATION.cff`](CITATION.cff). GitHub "Cite this repository", Zotero, Mendeley, and Pandoc read this format natively.

---

## 7 | Data & Transcripts

Per-arm `outcomes.csv` files (one row per dyad, with computed value/deal outcomes and judged measures) live in the `data_*/` directories of this repository and are released under CC BY 4.0.

The **full negotiation transcripts** (4,920 dyads across seven arms, consolidated per-arm JSONL) are archived as a Hugging Face dataset and are **not** included in this repository due to size:

- **Dataset:** https://huggingface.co/datasets/spectralbranding/negotiation-spec-experiment
- **DOI:** [`10.57967/hf/9090`](https://doi.org/10.57967/hf/9090)

---

*Last updated: 2026-06-08*
