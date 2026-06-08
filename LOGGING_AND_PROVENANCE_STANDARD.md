---
title: "Logging and Provenance Standard — Negotiation Spec Experiment"
status: ACTIVE — working checklist + gap analysis
author: Dmitry Zharnikov
date: 2026-06-06
applies_to: research/negotiation_spec_experiment/
precedent_repo: research/meaning-meaningfulness-empirical/ (Paper B 2026ap)
---

# Logging and Provenance Standard

This document defines the full logging and provenance standard for a top-tier LLM-run
experiment in this research program, then audits the current negotiation experiment
against it.

---

## Part A — THE STANDARD

Numbered checklist of every artifact and documentation section required. Each item
carries a one-line rationale and a pointer to the precedent file that defines it.
Grouped into nine domains.

---

### Domain 1 — Per-Call JSONL Logging

**1. Every negotiation-turn LLM call logged in JSONL.**
*Why*: transcripts are the SSOT; without per-call logs, a reviewer cannot
distinguish prompt-injection runs from standard runs or verify that the same prompt
was used for all replicates.
*Precedent*: `research/code/llm_call_logger.py` schema v1.2; `research/meaning-meaningfulness-empirical/logs/README.md` §Schema.

Required fields per row: `log_format_version`, `phase`, `operation`, `operator`,
`operator_role`, `model_version`, `timestamp_utc`, `system_prompt`, `user_prompt`,
`parameters` (model + temperature + max_tokens + seed if fixed), `request_id`,
`endpoint`, `sdk_version`, `response`, `response_metadata`, `tokens` (input +
output), `latency_seconds`, `cost_usd_est`, `errors`, `retries`, `git_sha_caller`,
`python_env_hash`, `human_in_loop`, `reconstructed_post_hoc`.

**2. Every scorer call (warmth/dominance + SVI) logged in JSONL — both scorer models.**
*Why*: inter-scorer ICC(2,1) is a pre-registered gate (§5 of PREREGISTRATION.md);
reviewers must be able to recompute it from the logs.
*Precedent*: `feedback_llm_call_professional_logging.md`; Paper B phase-3.5b logs
include every extractor-and-preservation-judge call as a separate JSONL file.

**3. Scorer response MUST include full natural-language reasoning, not only the JSON score.**
*Why*: a bare `{"warmth_score": 55, "dominance_score": 25}` with 16 output tokens
gives no audit trail for rubric fidelity. Rubric fidelity is reviewable only when
the scorer explains the score. Enables post-hoc spot-check of the 30-transcript
hand-check mandated in PREREGISTRATION §5.
*Precedent*: `research/meaning-meaningfulness-empirical/code/cross_operator_extraction.py`
captures the full structured-extraction response (not just the metric); the analogous
rule for this experiment requires `{"warmth_score": ..., "dominance_score": ..., "reasoning": "..."}`
or a CoT-style response before the JSON, logged in full.
*Status note*: current scorer prompt (`scoring_llm.py::WARMTH_DOMINANCE_SYSTEM`,
`::SVI_SYSTEM`) uses `Return ONLY valid JSON` — this suppresses reasoning. Revising
to `Return your reasoning in one paragraph, then a line break, then ONLY valid JSON`
satisfies this item without breaking the regex parser.

**4. REDACTION verification grep run after every phase before public-mirror push.**
*Why*: API keys embedded in prompts/responses are a security and publication blocker.
*Precedent*: `research/meaning-meaningfulness-empirical/logs/README.md` §Redaction audit.
Run command:
```bash
grep -iE "(sk-ant-|sk-proj-|AQVN|Bearer [A-Za-z0-9])" logs/*.jsonl  # must return empty
grep -iE "PENDING_UPDATES|SESSION_[A-Z]_(COMPLETION|HANDOFF)|TRIAGE_MEMO" logs/*.jsonl  # must return empty
```

**5. `logs/README.md` — schema reference + scope table + cost summary.**
*Why*: without a README, a reviewer opening the logs directory faces 947+ JSONL
files with no entry point. The README defines the public/internal scope boundary,
the schema, the per-phase table, and the redaction audit commands.
*Precedent*: `research/meaning-meaningfulness-empirical/logs/README.md` (full
template; copy and adapt).
Required sections: (a) Scope: experiments vs drafting; (b) Per-phase JSONL file
table (file | calls | operator | what it covers); (c) Schema JSON block; (d)
Reconstructed-post-hoc disclosure if any; (e) Redaction audit commands; (f) Cost
summary table.

---

### Domain 2 — Transcripts and Outcome Data

**6. DATA_MANIFEST.yaml — machine-readable inventory of all data files.**
*Why*: Paper B uses per-phase `multi_llm_manifest.json` files (see
`phase_3_5b_runs/multi_llm_manifest.json`, `phase_3_5c_runs/multi_llm_manifest.json`)
as the authoritative index of what data exists and what each file contains. The
negotiation experiment needs an equivalent for its transcript corpus.
*Precedent*: `research/meaning-meaningfulness-empirical/phase_3_5b_runs/multi_llm_manifest.json`.

Minimum fields for DATA_MANIFEST.yaml:
```yaml
created_at: "YYYY-MM-DDThh:mm:ssZ"
git_sha: "<SHA at time of manifest creation>"
model_primary: "gpt-4o-mini-2024-07-18"
temperature: 0.20
scenarios: [chair, rental, offer]
conditions: [NEUTRAL, WARMTH, DOMINANCE, COT_ONLY, SPEC_NOCOT, SPEC_COT]
replicates_per_cell: 5
total_dyads_target: <N>
total_dyads_completed: <N>
transcript_dir: data/transcripts/
outcomes_file: data/outcomes.csv
logs_dir: logs/
prompt_hashes_file: prompts/PROMPT_HASHES.txt
scoring_models:
  warmth_dominance: [gpt-4o-2024-08-06, claude-haiku-4-5-20251001]
  svi: [gpt-4o-2024-08-06, claude-haiku-4-5-20251001]
budget_stop_usd: 38
total_cost_usd_est: <float>
```

**7. `data/transcripts/` — one JSON per dyad, atomic writes, never overwritten.**
*Why*: transcripts are the raw data; they must be the SSOT for all downstream
analysis (outcomes.csv, scorer calls, ICC computation). Atomic tmp-then-replace
writes prevent corruption.
*Status*: already implemented in `negotiation_runner.py`.

**8. `data/outcomes.csv` — one row per dyad with all computed outcome fields.**
*Why*: the analysis model (`outcome ~ agent_type + scenario + role_order + (1|opponent_id) + (1|dyad_id)`)
requires a clean, one-row-per-dyad CSV with every outcome variable. This is the
primary analysis input.
*Status*: already implemented.

---

### Domain 3 — Prompts and Hashes

**9. All six condition-body prompt texts published as standalone `.txt` files in `prompts/`.**
*Why*: per `PROMPT_PURITY_PROTOCOL.md` §Prompt publication discipline (HARD RULE 2026-05-28),
every prompt used as an experimental treatment must be published as an inspectable
standalone file. Reviewer verifies byte-for-byte identity with what the experiment used.
*Status*: DONE — `NEUTRAL.txt`, `WARMTH.txt`, `DOMINANCE.txt`, `COT_ONLY.txt`,
`SPEC_NOCOT.txt`, `SPEC_COT.txt`, `harness_preface.txt` all present.

**10. `prompts/PROMPT_HASHES.txt` — SHA-256 of each prompt file.**
*Why*: the hash is the tamper-evidence record registered on OSF. PREREGISTRATION §2
states "hash is recorded at OSF registration."
*Status*: DONE — `hash_prompts.py` generates `PROMPT_HASHES.txt`.

**11. Scoring rubric prompts published as standalone files in `prompts/`.**
*Why*: the S19 warmth/dominance rubric and the SVI rubric are experimental treatments
for H6 (manipulation check) and H5 (SVI). Reviewers comparing to the base paper's
SI Fig. S19 need byte-for-byte inspection. The rubric text is currently embedded
only in `code/scoring_llm.py` — it must also exist as standalone files.
*Precedent*: `PROMPT_PURITY_PROTOCOL.md` §File layout (per-phase prompts as standalone
files with YAML front-matter).
*Action*: extract `WARMTH_DOMINANCE_SYSTEM` → `prompts/SCORING_WARMTH_DOMINANCE.txt`
and `SVI_SYSTEM` → `prompts/SCORING_SVI.txt`. YAML front-matter: phase, operator_role,
model(s), source-code reference (`code/scoring_llm.py::WARMTH_DOMINANCE_SYSTEM`),
S19 source citation.

---

### Domain 4 — Preregistration

**12. OSF preregistration node URL recorded in `PREREGISTRATION.md`.**
*Why*: PREREGISTRATION.md says "register on OSF before first paid call" but contains
no OSF node URL or timestamp. The preregistration is only meaningful if the external
timestamp is verifiable. After registration, add the OSF node URL (e.g.,
`osf.io/XXXXX`) and the registration timestamp to the header of PREREGISTRATION.md.
*Precedent*: PREREGISTRATION §1 locked-decisions table row "Hosting" lists this as
required.

**13. Prompt hash at time of OSF registration recorded in the OSF preregistration.**
*Why*: PREREGISTRATION §2 states "hash is recorded at OSF registration." The hash
links the frozen PROMPT_HASHES.txt to the registration timestamp, preventing
post-hoc prompt changes.

---

### Domain 5 — Scoring and Reliability

**14. ICC(2,1) script for inter-scorer reliability between the two scorer models.**
*Why*: PREREGISTRATION §5 gate requires ICC ≥ .70 on warmth and dominance before
scaling from pilot to MVP. analyze.py currently has 0 ICC computations. The pilot
amendment (§8) documents that ICC was computed externally (ICC .863 warmth, .802
dominance), but there is no reproducible script that produces these numbers.
*Action*: add a pingouin-based ICC script (or inline in `analyze.py`) that reads
both scorer JSONL files for the same transcript set and reports ICC(2,1) for
warmth, dominance, and each SVI facet. Fixed seed not needed (ICC is deterministic
given the data), but the script must be idempotent given a transcript set.
*Precedent*: PAPER_QUALITY_STANDARDS §37a-37e; the ICC value is a computed
numerical figure cited in the paper.

**15. 30-transcript hand-check audit documented before scaling.**
*Why*: PREREGISTRATION §5 requires "deal-parsing accuracy >= 95% on a hand-checked
30-transcript audit." This audit result must be recorded as a versioned document
(e.g., `PILOT_GATE_AUDIT.md`) before the main run, not as an informal check.
*Action*: create `PILOT_GATE_AUDIT.md` recording (a) the 30 transcript IDs sampled,
(b) the parsing accuracy count, (c) the ICC values from item 14, (d) the NEUTRAL
deal rate, (e) GO/HOLD/FIX decision with date and git SHA.

---

### Domain 6 — Reproducibility (Script, Seed, Env, reproduce.sh)

**16. `reproduce.sh` covers dry-run + analysis; clearly states what requires live API.**
*Why*: PUBLIC_MIRROR_STANDARD §4 requires a single-command orchestrator that
installs dependencies, runs the pipeline deterministically, and writes outputs to
`output/`.
*Status*: DONE in structure — `reproduce.sh` covers steps 1-4 (hashing, unit tests,
dry-run, dry-run analysis). It correctly states the live run requires API keys.
*Gap*: `reproduce.sh` does not install/check dependencies before running; it passes
`--with` flags per step but has no upfront `uv sync` or equivalent. Minor.

**17. `output/logs/` subdirectory for pipeline run logs.**
*Why*: PUBLIC_MIRROR_STANDARD §5 requires `output/{figures,tables,logs}/` with
`.gitkeep` files. The committed run-log at `output/logs/master_run.log` is the
audit trail for the last published pipeline state.
*Status*: `output/figures/` and `output/tables/` exist; `output/logs/` is missing.
The live run log currently lands at `data/full_primary_run.log` (inside the
gitignored data dir), which means the log is not committed and is not a reproducibility artifact.

**18. Fixed random seed documented for the analysis (not the negotiation calls).**
*Why*: PAPER_QUALITY_STANDARDS §37a requires scripts with a "fixed seed" for
reproducibility. Negotiation calls are stochastic by design (temperature .20); that
is correct and the transcript is the SSOT. But the analysis scripts (`analyze.py`,
any ICC script) must use a fixed seed for any bootstrap or resampling steps.
*Status*: `analyze.py` uses `np.random.seed(42)` — DONE. Verify this is in the
published code and documented in the Companion Computation Script subsection.

---

### Domain 7 — Provenance Prose (Paper.md subsections)

**19. `### LLM-call provenance.` subsection in the paper.**
*Why*: PAPER_QUALITY_STANDARDS §37f + `feedback_llm_call_professional_logging.md`
(HARD RULE): every cited LLM call must be cited by GitHub URL in paper.md. The
subsection names every JSONL file by purpose, states the operator/model/version,
notes the public GitHub URL, and discloses the experiment-vs-drafting scope boundary.
*Precedent*: `research/meaning-meaningfulness-empirical/paper.md` lines 125-131
(verbatim model to adapt). Key elements: GitHub URL for the `logs/` directory;
per-phase file table; redaction discipline note; `reconstructed_post_hoc` disclosure
if any.

**20. `### Companion Computation Script.` subsection in the paper.**
*Why*: PAPER_QUALITY_STANDARDS §37b requires this subsection for every paper with
computed numerical figures. For this experiment the cited figures are: mean outcome
by condition, Cohen's d on each contrast, ICC(2,1) on each scorer pair, deal rates.
The subsection names the public-mirror code path, the run command, and the fixed
seed.
*Precedent*: `research/meaning-meaningfulness-empirical/paper.md` lines 149-151.
Minimum: `"Every numerical figure cited in this paper is reproducible from
<GitHub URL for code/>. Run command: uv run python code/analyze.py --input
data/outcomes.csv. ICC computation: uv run python code/analyze.py --icc. Fixed
seed: SEED = 42."`

---

### Domain 8 — Public-Mirror Packaging (CITATION.cff, licenses, README, output/)

**21. `CITATION.cff` at the experiment root (or at the public mirror root).**
*Why*: PUBLIC_MIRROR_STANDARD §1. GitHub and Zenodo render CITATION.cff for
one-click citation in 12+ formats. Required fields: cff-version, title, authors
(with ORCID 0009-0000-6893-9231), date-released, license, repository-code, doi.
*Status*: MISSING from negotiation_spec_experiment/.

**22. `LICENSE` (MIT for code) + `LICENSE-data` (CC BY 4.0 for data/transcripts).**
*Why*: PUBLIC_MIRROR_STANDARD §2. Both files must be present; verbal declaration
in README is not sufficient.
*Status*: MISSING from negotiation_spec_experiment/.

**23. README with 3-badge header + 7 numbered sections.**
*Why*: PUBLIC_MIRROR_STANDARD §3. Badges: MIT/CC-BY/Last-Updated. Sections:
Getting Started, Project Layout, Quick Start, Dependencies, Script Map, Citation,
Licence. Last line `*Last updated: YYYY-MM-DD*`.
*Status*: README.md exists and is good but does not have badge header, numbered
sections, or last-updated line. The content is excellent; formatting upgrade needed
at publication time.

**24. `output/{figures,tables,logs}/` with `.gitkeep` files committed.**
*Why*: PUBLIC_MIRROR_STANDARD §5. Empty directories are not committed by git
without `.gitkeep`; the structure must be present in the public mirror so the
reproduction path is clear.
*Status*: `output/figures/` and `output/tables/` exist (contents gitignored). Add
`output/logs/` with `.gitkeep`. Commit the `.gitkeep` files.

**25. `pyproject.toml` at experiment root (or reference to project-root anchor).**
*Why*: PUBLIC_MIRROR_STANDARD §6. Relative-path resolution from any subdirectory
requires an anchor. The project-root `pyproject.toml` works if the public mirror
reproduces the full repo structure; if the public mirror is a standalone repo, it
needs its own `pyproject.toml`.
*Status*: a `pyproject.toml` exists at the project root.
For the standalone public mirror, a copy or stub is provided.

---

### Domain 9 — Dataset Card (HF/Zenodo DOIs)

**26. Zenodo dual-DOI (concept DOI + version DOI) for the dataset.**
*Why*: PUBLIC_MIRROR_STANDARD §Zenodo dual-DOI discipline; PREREGISTRATION §1
locked-decisions table. Concept DOI = canonical reference; version DOI =
reproducibility anchor at paper submission. Mint at submission, not before (version
bumps only at Zenodo upload per `feedback_version_only_at_zenodo`).
*Status*: not yet minted (run in progress; correct — mint at paper-draft stage).

**27. HuggingFace dataset card (`spectralbranding/negotiation-spec-transcripts`).**
*Why*: PUBLIC_MIRROR_STANDARD §HuggingFace dataset publication; PREREGISTRATION §1
"HF dataset (transcripts)." The transcript corpus is the primary data artifact;
permanent HF DOI enables citation independent of GitHub.
Required card sections: provenance, license (CC BY 4.0), DOI, columns schema,
splits (by scenario/condition), citation.
*Status*: not yet created (correct — create at paper-draft stage after full run).

---

## Part B — GAP ANALYSIS

| # | Artifact | Have? | What's missing for negotiation experiment | Priority |
|---|---|---|---|---|
| 1 | Per-turn JSONL logs (negotiation calls) | YES | Already logging via `llm_call_logger.py`; 947+ files live | — |
| 2 | Per-scorer JSONL logs (both models, wd + svi) | YES | `phase_scoring_wd_gpt4o_*`, `phase_scoring_wd_haiku_*`, `phase_scoring_svi_gpt4o_*`, `phase_scoring_svi_haiku_*` all present | — |
| 3 | Scorer captures full reasoning, not just JSON | NO | Current scorer prompts end in `Return ONLY valid JSON` → 16 output tokens, no reasoning trail. Add `"reasoning"` field or free-text preamble before JSON. Blocks rubric-fidelity audit. | P0 |
| 4 | REDACTION grep verified | PARTIAL | Logger applies redaction at write time but no README documents the verification command; no record that it has been run | P1 |
| 5 | `logs/README.md` | NO | Missing entirely. Paper B's `logs/README.md` is the entry point for the 947-file archive; without it a reviewer has no schema, no scope boundary, no cost summary. | P0 |
| 6 | `DATA_MANIFEST.yaml` | NO | No machine-readable index of transcript count, conditions, replicates, cost, git SHA at run end. | P1 |
| 7 | `data/transcripts/` (atomic JSON per dyad) | YES | Present and growing in live run | — |
| 8 | `data/outcomes.csv` | YES | 72 rows so far; live run continuing | — |
| 9 | Condition-body prompts as standalone `.txt` | YES | All 6 conditions + harness_preface.txt present in `prompts/` | — |
| 10 | `prompts/PROMPT_HASHES.txt` | YES | Generated by `hash_prompts.py`; present | — |
| 11 | Scoring rubric prompts as standalone files | NO | `WARMTH_DOMINANCE_SYSTEM` and `SVI_SYSTEM` are embedded in `scoring_llm.py` only. Must also exist as `prompts/SCORING_WARMTH_DOMINANCE.txt` and `prompts/SCORING_SVI.txt`. These are experimental treatments (H6 depends on the scoring rubric used). | P1 |
| 12 | OSF preregistration node URL in PREREGISTRATION.md | NO | PREREGISTRATION.md says "register on OSF before first paid call" — the run has started, so either registration happened (in which case the URL must be recorded) or it was skipped (a gap to close immediately). | P0 |
| 13 | Prompt hash recorded at OSF registration | NO | Follows from item 12 | P0 |
| 14 | ICC(2,1) script for inter-scorer reliability | NO | `analyze.py` has 0 ICC computations. The pilot amendment records ICC .863/.802 as passing, but no reproducible script produces these numbers. Required by PAPER_QUALITY_STANDARDS §37a (computed figures must be reproducible). | P1 |
| 15 | `PILOT_GATE_AUDIT.md` (30-transcript hand-check record) | NO | Pilot gate results are recorded only in PREREGISTRATION §8 prose. The hand-check audit (30 transcripts, parsing accuracy, ICC, NEUTRAL deal rate, GO decision) must be a standalone dated doc for reproducibility. | P1 |
| 16 | `reproduce.sh` functional | YES | Covers dry-run + analysis. Correctly notes live run requires API keys. | — |
| 17 | `output/logs/` subdirectory | NO | `output/figures/` and `output/tables/` exist; `output/logs/` is missing. Live run log lands in gitignored `data/full_primary_run.log` — not committed, not reproducible. | P1 |
| 18 | Fixed seed in analysis scripts | YES | `analyze.py` uses `np.random.seed(42)` | — |
| 19 | `### LLM-call provenance.` subsection in paper | NO | Paper.md does not exist yet (correct — paper drafted after run). Must be written following Paper B's structure (lines 125-131 of Paper B paper.md). | P1 (at draft) |
| 20 | `### Companion Computation Script.` subsection in paper | NO | Same as above — paper not yet drafted. | P1 (at draft) |
| 21 | `CITATION.cff` | NO | Missing entirely from experiment directory. | P2 (at pub) |
| 22 | `LICENSE` + `LICENSE-data` | NO | Missing entirely. | P2 (at pub) |
| 23 | README badge header + numbered sections | PARTIAL | README content is excellent; formatting upgrade (badges, 7 numbered sections, last-updated line) needed for PUBLIC_MIRROR_STANDARD compliance. | P2 (at pub) |
| 24 | `output/logs/` with `.gitkeep` | NO | See item 17. | P1 |
| 25 | `pyproject.toml` at experiment/mirror root | PARTIAL | Exists at project root; standalone public mirror will need own copy. | P2 (at pub) |
| 26 | Zenodo dual-DOI | NO | Not yet minted — CORRECT, mint at paper-draft/submission stage. | P2 (at pub) |
| 27 | HuggingFace dataset card | NO | Not yet created — CORRECT, create after full run. | P2 (at pub) |

**Priority legend**:
- **P0** — blocks publication and/or violates HARD RULES; close NOW while run is in progress
- **P1** — required for any public release / Zenodo upload; close before drafting the paper
- **P2** — required for final public-mirror packaging; close at Zenodo/HF upload time

---

## Part C — DO NOW vs DO AT PUBLICATION

### DO NOW (while live run is in progress — do not require touching code/ or data/)

These gaps can be closed by creating new files in prompts/ or at the experiment root.
None require modifying code/, data/, or logs/.

1. **Record the OSF preregistration URL** in `PREREGISTRATION.md` §8 (or header).
   If OSF registration has not yet been done: register immediately at osf.io using
   the frozen PREREGISTRATION.md and record the node URL + timestamp. This is the
   single most important integrity gap — the run has started and the preregistration
   status is ambiguous.

2. **Create `logs/README.md`** — copy the structure from
   `research/meaning-meaningfulness-empirical/logs/README.md` and adapt:
   - Update scope section (experiments = all negotiation + scoring calls; internal =
     none in this experiment, all calls are experimental evidence)
   - Write the per-phase file table (phase_negotiation_turn_* | negotiation turns |
     gpt-4o-mini | one file per dyad turn; phase_scoring_wd_* | warmth/dominance
     scorer | gpt-4o + haiku | one file per dyad; phase_scoring_svi_* | SVI scorer |
     gpt-4o + haiku | one file per dyad)
   - Include the schema JSON block
   - Include the redaction audit grep commands
   - Note the cost summary (to be filled after run completes)

3. **Add scorer reasoning to the prompt — but ONLY in `rescore_transcripts.py`
   or a new `code/score_with_reasoning.py` script, not in the live `scoring_llm.py`**.
   The live run must not be interrupted. After the run completes, create a
   `rescore_transcripts.py` (already exists) run that adds reasoning to a subset of
   transcripts (the 30-transcript hand-check audit corpus). For the paper, this is
   the audit trail; the primary numeric scores come from the existing logs.

4. **Create `PILOT_GATE_AUDIT.md`** documenting the pre-MVP gate check that was
   already passed (per PREREGISTRATION §8 amendment): transcript IDs sampled for
   the 30-transcript audit, parsing accuracy, ICC values, NEUTRAL deal rate, GO
   decision with date and git SHA of the run that was checked.

5. **Extract scoring rubric prompts to standalone files**: create
   `prompts/SCORING_WARMTH_DOMINANCE.txt` and `prompts/SCORING_SVI.txt` with YAML
   front-matter. These are byte-identical to the strings in `scoring_llm.py` but
   exist as inspectable files, satisfying the prompt-publication HARD RULE for the
   experimental scoring instrument.

6. **Create `output/logs/` directory** with a `.gitkeep` file (commit it). This
   satisfies PUBLIC_MIRROR_STANDARD §5 and provides the target for the run log at
   publication time.

### DO AT PAPER-DRAFT STAGE (after run completes, before Zenodo upload)

These items require the final data to exist or require writing the paper:

7. **`DATA_MANIFEST.yaml`** — fill in total_dyads_completed, total_cost_usd_est,
   git SHA at run end, and commit. This is the machine-readable chain-of-custody
   record.

8. **ICC(2,1) script** — add `--icc` flag to `analyze.py` (or create
   `code/icc_reliability.py`) that reads both scorer JSONL files and reports
   ICC(2,1) for warmth, dominance, and each SVI facet. This is the reproducible
   script for the cited ICC figures.

9. **`logs/README.md` cost summary** — fill in the final per-phase cost table after
   run completes.

10. **Paper.md `### LLM-call provenance.` subsection** — following the structure
    of Paper B paper.md lines 125-131. Name every phase (negotiation_turn_* |
    scoring_wd_* | scoring_svi_*), both scoring models (gpt-4o-2024-08-06 +
    claude-haiku-4-5-20251001), the GitHub URL for `logs/`, and the
    experiment-vs-drafting scope boundary.

11. **Paper.md `### Companion Computation Script.` subsection** — following Paper B
    paper.md lines 149-151. Name `code/analyze.py`, the run command, and the
    ICC computation command.

### DO AT ZENODO/HF UPLOAD (public-mirror packaging)

12. `CITATION.cff` at mirror root (from `templates/public-mirror-scaffold/CITATION.cff`)
13. `LICENSE` (MIT) + `LICENSE-data` (CC BY 4.0) at mirror root
14. README badge header + 7 numbered sections + last-updated line
15. `pyproject.toml` at mirror root (copy from project root, adjust `[project] name`)
16. Zenodo concept DOI + version DOI minted; both recorded in CITATION.cff + README
17. HuggingFace dataset card `spectralbranding/negotiation-spec-transcripts`

---

## Cross-references

- `research/PUBLIC_MIRROR_STANDARD.md` — source for items 21-27
- `research/code/llm_call_logger.py` — JSONL schema (items 1-5)
- `research/meaning-meaningfulness-empirical/logs/README.md` — template for item 5
- `research/meaning-meaningfulness-empirical/paper.md` lines 125-131 — LLM-call provenance subsection template (item 19)
- `research/meaning-meaningfulness-empirical/paper.md` lines 149-151 — Companion Computation Script subsection template (item 20)
- `research/PAPER_QUALITY_STANDARDS.md` items 37a-37f — computation script + transparency doc rules
- `research/negotiation_spec_experiment/PREREGISTRATION.md` — source for items 12-13, 14-15
- `research/meaning-meaningfulness-empirical/PROMPT_PURITY_PROTOCOL.md` — prompt publication discipline (item 11)
- `memory/feedback_llm_call_professional_logging.md` — HARD RULE source for items 1-5
- `memory/feedback_publish_computation_scripts.md` — HARD RULE source for item 20
- `memory/feedback_transparency_docs_must_be_public.md` — HARD RULE source for item 37f

---

*Last updated: 2026-06-06*
