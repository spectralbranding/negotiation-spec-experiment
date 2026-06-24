[![MIT License](https://img.shields.io/badge/Code-MIT-blue.svg)](LICENSE)
[![CC-BY 4.0](https://img.shields.io/badge/Data-CC--BY_4.0-lightgrey.svg)](LICENSE-data)
![Last Updated](https://img.shields.io/badge/updated-2026--06--24-success)

# Value Headroom Moderates Whether Specification Beats Style in LLM Negotiation

When two language-model agents negotiate, does it matter more how they are *styled*
(warm, dominant) or how their objective is *specified* (ranked priorities, a
reservation value, a concession rule)? This repository is the self-contained
artifact for the paper: across seven arms spanning three model families (4,920
dyads), it identifies **value headroom** — the joint surplus a naively cooperative
pair leaves on the table — as a first-order moderator. Style ties specification on
near-ceiling scenarios (a preregistered null) but specification-first prompting
yields strictly higher joint value once headroom is present (Cohen *d* = .314 mid-
capability; *d* = .569 at the frontier), recovering the earlier "style beats
structure" result as the zero-headroom boundary case.

- Paper: [paper.md](paper.md) · Version 1.1.0 · DOI [10.5281/zenodo.20595996](https://doi.org/10.5281/zenodo.20595996)
- Machine-readable bundle: [paper.yaml](paper.yaml) (Paper Spec), [SPINE.yaml](SPINE.yaml), [ONTOLOGY.yaml](ONTOLOGY.yaml), [GLOSSARY.md](GLOSSARY.md)
- New here? [AGENTS.md](AGENTS.md) is a file-by-file guide for any reader (human or AI agent).

*Last updated: 2026-06-24*

## 1 | Getting Started

This repository is the self-contained artifact for the paper above: the `[@key]`
manuscript source, the experiment code, the preregistrations, the per-arm data, and
a one-command analysis pipeline. Clone it and run `./reproduce.sh` to reproduce the
per-arm contrasts and the headroom dose-response from the committed per-arm
`outcomes.csv` files (see [§3](#3--quick-start)). Re-running the live negotiations
(the LLM calls that generate the transcripts) needs model API credentials; the
committed outcomes let you reproduce every reported statistic without them.

## 2 | Project Layout

```
paper.md                      the manuscript ([@key] source; renders with the .bib)
negotiation_spec_2026.bib     bibliography
SPINE.yaml / ONTOLOGY.yaml / GLOSSARY.md   machine-readable claim + term graphs
paper.yaml                    Paper Spec (claims / assumptions / dependencies)
CITATION.cff / CITATIONS.md / AGENTS.md    citation metadata + reader's guide
PREREGISTRATION.md            Study 1 preregistration (the headroom contrast)
PREREGISTRATION_STUDY2.md     Study 2 preregistration (graded dose-response)
EXPERIMENT_DESIGN.md / EXTENSION_DESIGN.md / STUDY2_RATIONALE.md   design docs
PILOT_GATE_AUDIT.md           pilot gate record
LOGGING_AND_PROVENANCE_STANDARD.md   the LLM-call logging discipline
DATA_AVAILABILITY.md / DATA_MANIFEST.yaml / PROVENANCE.yaml / CONTRIBUTORS.yaml
code/                         experiment + analysis scripts (see §5)
prompts/                      the six condition prompts (style vs specification)
scenarios/ scenarios_headroom/ scenarios_study2/   negotiation scenario sets
data/                         main seven-arm outcomes
data_headroom/ data_study2/ data_ablation_full/ data_frontier/ data_haiku/ data_paraphrase/
                              per-arm outcomes (dose-response, ablation, frontier,
                              model-family, paraphrase-robustness)
reproduce.sh                  one-command analysis pipeline
output/                       figures / tables / logs (generated)
```

## 3 | Quick Start

```bash
uv sync                       # install dependencies (numpy, pandas, scipy, pyyaml)
./reproduce.sh                # reproduce every arm's contrast + the headroom dose-response
./reproduce.sh --check-only   # verify dependencies without running the analysis
```

Outputs are written under `output/` and teed to `output/logs/master_run.log`.
Re-running the live negotiations (not required to reproduce the statistics) is
driven by `code/run_experiment.py` over the `scenarios*/` and `prompts/` sets and
needs model API credentials.

## 4 | Dependencies

Python 3.12 with numpy (>= 2.0), pandas (>= 2.2), scipy (>= 1.13), and PyYAML
(>= 6.0) — declared in [pyproject.toml](pyproject.toml). Install with `uv sync`
(or `pip install -e .`). Reproducing the committed statistics needs nothing else;
generating fresh transcripts additionally needs model API credentials.

## 5 | Script Map

| Script | Purpose |
|--------|---------|
| `code/run_experiment.py` | Drives the live negotiations over the scenario × prompt grid. |
| `code/negotiation_runner.py` | The dyad negotiation loop (turn exchange, agreement detection). |
| `code/scoring_llm.py` | LLM scoring of transcripts into structured outcomes. |
| `code/outcomes.py` | Builds the per-arm `outcomes.csv` from scored transcripts. |
| `code/compute_headroom.py` | Computes each scenario's value headroom. |
| `code/analyze.py` | Per-arm contrasts (effect sizes, p-values) + the headroom dose-response. |
| `code/compute_icc.py` | Inter-rater reliability (ICC) for the scoring. |
| `code/rescore_transcripts.py` | Re-scores committed transcripts (audit / robustness). |
| `code/build_hf_dataset.py` / `code/make_manifest.py` | Package the dataset + manifest. |
| `reproduce.sh` | Runs the analysis end-to-end across every arm. |

## 6 | Citation

Cite the paper via its Zenodo DOI (a machine-readable record is in
[CITATION.cff](CITATION.cff)):

> Zharnikov, D. (2026). *Value Headroom Moderates Whether Specification Beats Style
> in LLM Negotiation.* Working Paper v1.1.0. https://doi.org/10.5281/zenodo.20595996

## 7 | License

Code is released under the [MIT License](LICENSE); the paper and data are released
under [CC BY 4.0](LICENSE-data).
