---
title: "Spec-Agent vs Styled-Agent in AI–AI Negotiation — Preregistration"
status: FROZEN PRE-RUN (v1.0.0) — OSF public project https://osf.io/gmhj7/ (uploaded 2026-06-06); canonical freeze = git commit 2ed95ffd
author: Dmitry Zharnikov
date: 2026-06-06
base_paper: Vaccaro, Caosun, Ju, Aral & Curhan (2026), arXiv 2503.06416 (PNAS published version; PUBLIC REF = arXiv 2503.06416)
design_doc: EXPERIMENT_DESIGN.md (same directory)
---

# Preregistration

This document freezes the hypotheses, conditions, sampling, and analysis **before any
negotiation is run or any paid API call is made**. The canonical pre-run freeze is git
commit `2ed95ffd` (2026-06-06, before the first paid call). A public OSF project mirrors
this frozen prereg + design + pilot-gate audit + prompt hashes at **https://osf.io/gmhj7/**
(uploaded 2026-06-06; author Dmitry Zharnikov, OSF id 3zvrp). An immutable OSF Registration
was deliberately NOT minted: the run had already begun, so a pre-data-collection registration
schema would misstate timing; the git commit is the authoritative timestamp. No change to §2–§6 is
permitted after the OSF registration timestamp except as a logged, dated amendment in §8.

## 0. Research question

The MIT competition (base paper) collected negotiation-agent prompts written in the
**usual human idiom** — persona + behavioral style. We test whether a **specification-first**
agent — declaring objective, reservation/walkaway value, ranked issue weights, an explicit
concession rule, and a stop rule — is a distinct and superior design axis, holding
chain-of-thought (CoT) constant. The base paper's top integrative value-creator bundled
structure with CoT and never isolated structure itself; that isolation is our contribution.

## 1. Locked decisions (the experimenter's degrees of freedom, fixed)

| Decision | Locked value |
|---|---|
| Play models | **PRIMARY `gpt-4o-mini` @ temperature 0.20** (exact match to base paper, enables direct comparison to their unpublished data). **ROBUSTNESS ARM `claude-haiku-4-5`** (cross-family test of the structure effect — answers the paper's single-model limitation). |
| Conditions (2×2 + controls) | 6 agent types — see §2. |
| Scorers (warmth/dominance + SVI) | **Two independent**: `gpt-4o` and `claude-haiku-4-5`; report inter-scorer ICC. Transcripts produced on `gpt-4o-mini` are NOT scored solely by an OpenAI model (cross-family scorer included) to avoid same-model bias. Scorer model+version pinned + logged. |
| Scenarios | Self-contained (§3 of design doc); **full payoff matrices published** (no confidentiality). 1 distributive (`chair`) + 2 integrative (`rental`, `offer`). |
| Sampling | Pilot ~300 negotiations → MVP ~150/cell → scale to ~400/cell on the primary model; robustness arm at MVP density. |
| Budget ceiling | **$40 USD** (user-approved). Hard stop; logger sums `cost_usd_est` and the runner aborts at $38. |
| Logging | Per-call JSONL via `research/code/llm_call_logger.py` (HARD RULE). Transcripts are the SSOT. |
| Hosting | GitHub mirror `negotiation-spec-experiment` (SSOT) + OSF preregistration & registration + Zenodo dual-DOI (data + code) + HF dataset (transcripts). |
| Author contact | None. Full open release lets the base authors reproduce against their own unpublished data. |

## 2. Conditions — the 2×2 (structured-spec × CoT) plus controls

All bodies are wrapped in the base paper's verbatim harness preface and receive the SAME
private payoff card. Bodies are length-matched (±15%). Only the strategy body varies.

| ID | structured-spec | CoT | Role |
|---|---|---|---|
| `NEUTRAL` | no | no | bare-goal baseline (≈ paper "unprompted") |
| `WARMTH` | no | no (style) | control — paper §2.4 / S19 warmth definition |
| `DOMINANCE` | no | no (style) | control — paper §2.4 / S19 dominance definition |
| `COT_ONLY` | no | yes | "just reasoning", no spec |
| `SPEC_NOCOT` | yes | no | **KEY CELL — structure alone** |
| `SPEC_COT` | yes | yes | NegoMate-like (structure + reasoning) |

The clean test of *structured specification holding CoT constant* is `SPEC_NOCOT` vs
`COT_ONLY` and `SPEC_NOCOT` vs `NEUTRAL`. The structure×CoT interaction is
(`SPEC_COT` − `COT_ONLY`) − (`SPEC_NOCOT` − `NEUTRAL`).

Exact prompt texts are frozen in `prompts/` and hashed; the hash is recorded at OSF
registration. (Manipulation check H6 must confirm SPEC cells score LOW on both S19 axes.)

## 3. Primary and secondary outcomes

Primary outcome: **H3 — value created (joint points) on integrative scenarios**.
Secondary: H1 deal rate; H2 value claimed (distributive, with the H1×H2 impasse-penalty
interaction); H4 value claimed (integrative); H5 counterpart subjective value (SVI 4-facet);
H6 manipulation check (S19 warmth/dominance of each agent). Directional predictions are in
EXPERIMENT_DESIGN.md §5 and are incorporated here by reference (frozen).

## 4. Analysis plan

- Primary model: `outcome ~ agent_type + scenario + role_order + (1 | opponent_id) + (1 | dyad_id)`
  (linear mixed model for continuous outcomes; logistic mixed model for deal rate).
- Pre-specified contrasts: SPEC_NOCOT − NEUTRAL; SPEC_NOCOT − COT_ONLY; SPEC_NOCOT − WARMTH;
  SPEC_NOCOT − DOMINANCE; the structure×CoT interaction (§2).
- Report effect sizes (raw point deltas + Cohen's d) with exact p (3 decimals; `p < .001`
  floor) per PAPER_QUALITY_STANDARDS. No significance stars. No leading zero on decimals.
- Robustness arm (`claude-haiku-4-5`): re-estimate the primary contrasts; the structure
  effect is declared model-agnostic only if SPEC_NOCOT − NEUTRAL holds sign + significance
  in both families.
- Inter-scorer reliability: ICC(2,1) between the two scorers on warmth, dominance, SVI;
  report; treat H6 as within-set relative.

## 5. Stopping rule

Run the pilot (~300). Proceed to MVP only if: (a) deal-parsing accuracy ≥ 95% on a
hand-checked 30-transcript audit; (b) the two scorers reach ICC ≥ .70 on warmth & dominance;
(c) NEUTRAL deal rate is in a sane (.3–.95) range (scenarios not degenerate). Otherwise fix
scenarios/parsers and re-pilot. Hard budget stop at $38 cumulative `cost_usd_est`.

## 6. What would falsify the thesis

If `SPEC_NOCOT` does NOT exceed `NEUTRAL` and `COT_ONLY` on value created (H3) at the MVP
sample, the "structure is a distinct lever" claim is not supported and the note reports a
null — published either way (no file-drawer). An honest predicted SPEC *weakness* (lower SVI,
H5) is pre-registered, not hidden.

## 7. Integrity guards (project HARD RULES carried in)

- Verify-on-disk; never trust a wrapper exit code. Subagents must NEVER commit dry-run /
  synthetic transcripts into the live data dir (prior incident). Dry-run output lives under
  `*/dryrun/` and is git-ignored.
- Every paid call logged before the next is issued; redaction at write time.
- No SBT vocabulary bolted onto a negotiation paper; we cite the base paper, not vice versa.
- A pre-draft critical-review gate fires at the drafting stage, not before the run.

## 8. Amendments (append-only, dated)

- **2026-06-06 — Harness-correctness fixes during piloting (no hypothesis change).**
  (a) Integrative scenarios were 0/10-2/10 deals because agents never emitted ACCEPT; fixed by
  injecting each role's full numeric payoff card + reservation value, a standalone-ACCEPT trigger
  with a reservation-value accept rule, round cap K 8->14, and a final-round forcing notice. The 6
  frozen condition body texts in `prompts/` were NOT changed (accept mechanics live at the
  harness/turn level). Post-fix live deal rates: chair .81 / rental .53 / offer .59 (within the §5
  .3-.95 band).
  (b) **Dominance scoring rubric revised (v2.1)** before the main run: the original rubric gave
  inter-scorer ICC .472 (< the §5 .70 gate) because raters split on mid-range firmness vs. refusal.
  Revised with explicit 0/25/50/75/100 behavioral anchors and an "outcome is not dominance"
  disambiguation; scorer temperature set to 0; the haiku fenced-JSON parser hardened. Re-scoring
  the SAME 20 pilot transcripts (no replay) gave WARMTH ICC .863, DOMINANCE ICC .802 (both PASS),
  with H6 ordering intact (DOMINANCE highest, SPEC lowest). The warmth and SVI rubrics were unchanged.
  This is a measurement-instrument refinement logged here for transparency; it does not alter any
  hypothesis, condition, scenario, or analysis plan.
  (c) Git-hygiene note: a concurrent fleet-sync session checked out `main` mid-build, so harness
  commits 57fa5fb3 + 8b03966c landed on `main` while prereg commit 2ed95ffd stayed on
  `feature/negotiation-spec-experiment`. No work lost; consolidated 2026-06-06. Pre-run gates all
  PASS (deal-parsing, warmth ICC, dominance ICC) — cleared to scale to the full run.
