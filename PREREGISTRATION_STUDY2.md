---
title: "Spec-Agent vs Styled-Agent in AI–AI Negotiation — Study 2 (High-Headroom) Preregistration"
status: FROZEN PRE-RUN (v1.0.0) — preregistered BEFORE any Study 2 negotiation is run
author: Dmitry Zharnikov
date: 2026-06-06
base_paper: Vaccaro, Caoson, Ju, Aral & Curhan (2026), arXiv 2503.06416 (PNAS published version; PUBLIC REF = arXiv 2503.06416)
study1_prereg: PREREGISTRATION.md (same directory; FROZEN, git commit 2ed95ffd)
study1_result: "null on primary H3 (value created); SPEC_NOCOT − NEUTRAL d = .049, p = .683"
design_doc: EXPERIMENT_DESIGN.md (same directory — conditions, scoring, power logic reused)
rationale_doc: STUDY2_RATIONALE.md (same directory)
scenarios: scenarios_study2/{merger,supplier,salvage}.yaml
---

# Preregistration — Study 2 (High-Headroom Scenarios)

This document freezes the hypotheses, conditions, scenarios, sampling, and analysis for
**Study 2 before any Study 2 negotiation is run or any paid API call for Study 2 is made.**
Study 2 is a **new preregistered confirmatory study**, motivated by a diagnosed scenario
ceiling in Study 1 — **not** a re-analysis or a scenario-edit of Study 1. Study 1's frozen
artifacts (`PREREGISTRATION.md`, `EXPERIMENT_DESIGN.md`, `scenarios/`, `prompts/`) are
unchanged. See `STUDY2_RATIONALE.md` for the explicit new-study-vs-reanalysis statement
and the §9 integrity note below.

The pre-run freeze is the git commit that adds this file on branch
`feature/negotiation-spec-study2` (before the first Study 2 paid call). No change to §2–§7
is permitted after that timestamp except as a logged, dated amendment in §10.

## 0. Motivation — Study 1 null and the value-ceiling diagnosis

Study 1 (gpt-4o-mini @ temperature .20, 630 dyads, six conditions) tested whether a
**specification-first** agent (`SPEC_NOCOT`) beats controls on **value created** (joint
points, integrative scenarios). The primary hypothesis was **not supported**:
`SPEC_NOCOT`, `COT_ONLY`, `WARMTH`, and `NEUTRAL` all tied (~641–650 joint points);
`SPEC_NOCOT − NEUTRAL` was d = .049, p = .683.

The diagnosed cause is a **value ceiling**. In Study 1's integrative scenarios (`rental`,
`offer`), the bare-cooperative `NEUTRAL` agent already captured ~641 of ~658 reachable
joint points (≈97% of the Pareto frontier). The single logroll in each scenario was
discoverable by default cooperative play, so there was almost no headroom for an explicit
logrolling specification to add value. When default cooperation already finds the surplus,
SPEC cannot differentiate — a measurement-floor problem, not necessarily a theory problem.

The Study 1 finding that **did** hold replicated the base paper cleanly: `DOMINANCE`
craters deal rate (.51 vs .90, d = −.93) and value created (d = −.41), and the
manipulation check (H6) confirmed SPEC scores low on both warmth and dominance.

**Study 2's single design change is the scenario set.** It keeps the same six conditions,
the same outcome metrics, and the same analysis plan, but swaps in three scenarios
**engineered so that a naive cooperative agent does NOT automatically reach the Pareto
frontier** — restoring a fair test of the specification lever. The headroom (gap between
the naive-likely outcome and the Pareto optimum) is 31–46% of the frontier on the
integrative scenarios, versus ~3% in Study 1 (see `scenarios_study2/README.md`).

## 1. Locked decisions (experimenter degrees of freedom, fixed)

Identical to Study 1 except the scenario set. Reproduced here for self-containment.

| Decision | Locked value |
|---|---|
| Play model | **PRIMARY `gpt-4o-mini` @ temperature .20** (exact match to Study 1 and the base paper, enabling direct Study 1 ↔ Study 2 comparison). Optional **ROBUSTNESS ARM `claude-haiku-4-5`** at MVP density, as in Study 1. |
| Conditions | **The SAME six agent types as Study 1** — see §2. No prompt-body change. |
| Scorers (warmth/dominance + SVI) | **Two independent**: `gpt-4o` and `claude-haiku-4-5`; report inter-scorer ICC(2,1). Same cross-family discipline and the **revised dominance rubric v2.1** adopted in Study 1 Amendment 8b (explicit 0/25/50/75/100 anchors; scorer temperature 0). Pinned + logged. |
| Scenarios | **NEW, self-contained, high-headroom** (§3): 1 distributive (`salvage`, narrow ZOPA) + 2 integrative (`merger` 5-issue, `supplier` 4-issue). Full payoff matrices published in `scenarios_study2/`. Same YAML schema as Study 1 → same harness, no code change. |
| Sampling | Pilot (~300 Study 2 negotiations) → MVP ~150/cell. Scale to ~400/cell on the primary model only if the MVP shows a directional SPEC effect worth tightening. |
| Budget ceiling | **$40 USD for Study 2** (separate from Study 1; user-approved required before first paid call). Logger sums `cost_usd_est`; runner aborts at $38. |
| Logging | Per-call JSONL via `research/code/llm_call_logger.py` (HARD RULE). Transcripts are the SSOT. Study 2 transcripts land in a `study2/` subtree, never overwriting Study 1 data. |
| Hosting | Same GitHub mirror `negotiation-spec-experiment` + Zenodo dual-DOI + HF dataset (DOI 10.57967/hf/9090). |

## 2. Conditions — the SAME 2×2 (structured-spec × CoT) plus controls

**Unchanged from Study 1.** The frozen prompt bodies in `prompts/` are reused verbatim;
their hashes are recorded at the Study 2 freeze. Only the scenario files differ.

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

(Manipulation check H6 must again confirm SPEC cells score LOW on both S19 axes; the
prompt bodies are identical to Study 1, so the H6 result is expected to replicate.)

## 3. Scenarios — NEW high-headroom set (§3 of the scenarios_study2 README)

Full payoff matrices, analytic Pareto optima, equal-split baselines, and the per-scenario
headroom argument are in `scenarios_study2/README.md`. Summary:

| ID | Type | Roles | Issues | Naive joint | Pareto joint | Headroom gap |
|---|---|---|---|---|---|---|
| `merger` | integrative | acquirer, founder | 5 — cash, equity, integration, brand, esg | 772 | 1120 | **+348 (31% of frontier)** |
| `supplier` | integrative | buyer, supplier | 4 — price, volume, payment, warranty | 520 | 960 | **+440 (46% of frontier)** |
| `salvage` | distributive | payer, claimant | 1 — settlement (ZOPA width $15) | n/a | claiming-only | narrow ZOPA: claiming-without-impasse is hard |

Headroom levers (vs Study 1's ~3% gap): a **compatible** issue both parties want but will
not find without exploring (`merger.esg`, `supplier.volume`); a **distractor** issue that
absorbs naive bargaining (`supplier.payment_terms`); **strong, non-obvious weight
asymmetry** on the true logroll issues so split-the-difference loses most of the surplus
(`merger.integration` 300 vs 60, `merger.brand` 320 vs 60, `supplier.warranty` 300 vs 60);
**tight reservation values** and a **narrow-ZOPA** distributive case (`salvage`). All three
verified to load + build prompts + score via the unchanged `negotiation_runner.py` and
`outcomes.py`.

## 4. Primary and secondary outcomes

Identical definitions to Study 1 (so Study 1 ↔ Study 2 numbers are comparable).

- **Primary: H3 — value created (joint points) on the integrative scenarios
  (`merger` + `supplier`).** With headroom restored, the directional prediction is
  `SPEC_NOCOT > NEUTRAL` AND `SPEC_NOCOT > COT_ONLY`.
- Secondary: H1 deal rate; H2 value claimed (distributive `salvage`, with the H1×H2
  impasse-penalty interaction — does SPEC claim narrow-ZOPA surplus without the DOMINANCE
  deal-rate penalty?); H4 value claimed (integrative); H5 counterpart subjective value
  (SVI 4-facet); H6 manipulation check (S19 warmth/dominance of each agent).
- Directional predictions for H1–H6 are those in `EXPERIMENT_DESIGN.md` §5, incorporated
  by reference and unchanged. The only substantive update is the **expectation that H3 now
  separates** because the scenarios provide headroom; Study 1's null is attributed to the
  ceiling, not to the absence of a structure effect.

## 5. Analysis plan

**Identical contrasts and model to Study 1.**

- Primary model: `outcome ~ agent_type + scenario + role_order + (1 | opponent_id) + (1 | dyad_id)`
  (linear mixed model for continuous outcomes; logistic mixed model for deal rate).
- Pre-specified contrasts: `SPEC_NOCOT − NEUTRAL`; `SPEC_NOCOT − COT_ONLY`;
  `SPEC_NOCOT − WARMTH`; `SPEC_NOCOT − DOMINANCE`; the structure×CoT interaction (§2).
- Report effect sizes (raw point deltas + Cohen's d) with exact p (three decimals;
  `p < .001` floor) per `research/PAPER_QUALITY_STANDARDS.md`. No significance stars. No
  leading zero on decimals (e.g., `d = .31`, `p = .047`).
- Robustness arm (`claude-haiku-4-5`): re-estimate the primary contrasts; the structure
  effect is declared model-agnostic only if `SPEC_NOCOT − NEUTRAL` holds sign +
  significance in both families.
- Inter-scorer reliability: ICC(2,1) between the two scorers on warmth, dominance, SVI;
  report; treat H6 as within-set relative.
- **Pre-specified Study 1 ↔ Study 2 comparison (the headroom claim, made testable):**
  report the naive/`NEUTRAL` value-created-as-fraction-of-Pareto in each study. The
  diagnosis predicts NEUTRAL captures ≈97% of the frontier in Study 1 but materially less
  in Study 2 (target < ~85%), which is the condition under which a SPEC effect can appear.

## 6. Sample size, power, cost

- **MVP target: ~150 dyads per (agent × scenario) cell** — the same density that gave
  Study 1 the power to detect the DOMINANCE effects (d ≈ −.4 to −.9) and to bound the SPEC
  null tightly. A between-agent Cohen's d ≈ .3–.4 on value created needs ~120–175/cell at
  80% power, two-sided alpha .05; the engineered headroom (31–46% of the frontier) makes a
  *true* SPEC effect, if it exists, larger than that floor.
- Six conditions × three scenarios at ~150/cell, counterbalanced across the two role
  orders, is on the order of Study 1's ~630-dyad MVP scope per study phase.
- Cost (gpt-4o-mini): `merger`/`supplier` transcripts run longer than Study 1's 3-issue
  scenarios (5 and 4 issues, K = 14), so budget the integrative blend a little above
  Study 1's ~$1.55/1k; the distributive `salvage` is cheap. The whole Study 2 MVP is well
  under the **$40** ceiling (Study 1's full scope landed under $40). Cost is not the
  binding constraint; scenario validity (the §7 gates) is.

## 7. Stopping-rule gates (reused from Study 1 §5)

Run the Study 2 pilot (~300). Proceed to MVP only if:
- (a) deal-parsing accuracy ≥ 95% on a hand-checked 30-transcript audit;
- (b) the two scorers reach ICC ≥ .70 on warmth & dominance (rubric v2.1);
- (c) **NEUTRAL deal rate is in the sane [.3, .95] range on every scenario** — the
  scenarios must not be degenerate. The narrow `salvage` ZOPA is the watch item: if
  NEUTRAL impasses too often (deal rate < .3), widen the ZOPA in a logged §10 amendment
  (analogous to Study 1 Amendment 8a) and re-pilot. Hypotheses, conditions, and the
  integrative scenarios are unchanged by any such fix.

Additional Study-2-specific pilot sanity check (does not gate, but is logged): confirm the
realized `NEUTRAL` value-created/Pareto fraction on `merger` + `supplier` is materially
below Study 1's ~97% (target < ~85%). If NEUTRAL still saturates the frontier, the
scenarios failed to create headroom and the planned remedy is to increase weight asymmetry
/ add issues in a logged amendment **before** the main run — never after seeing SPEC
results.

Hard budget stop at $38 cumulative `cost_usd_est`.

## 8. What would falsify the thesis

If `SPEC_NOCOT` does NOT exceed `NEUTRAL` and `COT_ONLY` on value created (H3) at the
Study 2 MVP — **given a confirmed headroom gap** (NEUTRAL well below the Pareto frontier
per the §7 sanity check) — then the "structured specification is a distinct, value-creating
lever" claim is genuinely not supported, and the note reports a *second* null. That is a
much stronger negative result than Study 1's, because it cannot be attributed to a ceiling.
Both outcomes are published (no file-drawer). The honest predicted SPEC weakness (lower
SVI, H5) remains preregistered, not hidden.

## 9. Integrity note — this is a NEW preregistered study, not p-hacking the Study 1 null

This study is preregistered **before any Study 2 run**, specifically to avoid
post-hoc rationalization of the Study 1 null:

- Study 1's artifacts (`PREREGISTRATION.md`, `EXPERIMENT_DESIGN.md`, `scenarios/`,
  `prompts/`) are **frozen and unmodified**. Study 2 adds files only.
- Study 2 changes **exactly one design factor — the scenario set** — for a **stated,
  mechanistic, pre-registered reason** (the value ceiling), with the headroom gap
  quantified analytically *in advance* (`scenarios_study2/README.md`) and a pre-specified
  pilot check that the gap is real (§7). This is a confirmatory follow-up with an a-priori
  prediction, not a garden of forking paths over Study 1's data.
- The Study 1 null is reported **honestly and in full** wherever Study 2 is reported; the
  DOMINANCE replication and the H6 manipulation-check success from Study 1 are carried
  forward as positive controls.
- No Study 1 transcripts are re-scored, re-segmented, or re-analyzed to manufacture a
  positive result. Study 2 collects new data under the same conditions and the same
  analysis plan.

See `STUDY2_RATIONALE.md` for the standalone statement of this position.

## 10. Amendments (append-only, dated)

**2026-06-07 — Extension amendment (robustness suite, 4 components).** Adds four robustness
arms to the Study-2 design. The Study-2 hypotheses, conditions, scenarios, and analysis plan
(§2–§7) are **unchanged**; this amendment adds arms only and does not re-analyze prior data.
Design SSOT: `EXTENSION_DESIGN.md`; gate record: `PILOT_GATE_AUDIT.md` (Extension Gate).

| Component | Status | What is added | Confirmatory? |
|---|---|---|---|
| 1 — Logrolling ablation | **Confirmatory (directional, pre-specified)** | New condition `SPEC_NOLOGROLL` (SPEC_NOCOT minus the single logrolling sentence; byte-diff logged EXTENSION_DESIGN §1.2). Prediction: `SPEC_NOLOGROLL` ≈ NEUTRAL/COT_ONLY < `SPEC_NOCOT` on value created (merger+supplier). Falsifies the "leaked-matrix" rival. | Yes |
| 2 — Paraphrase envelope | Exploratory (robustness) | K=4 paraphrases × {SPEC_NOCOT, COT_ONLY, WARMTH, NEUTRAL}, focal-vs-pinned-NEUTRAL; report min/max value-created envelope. Manipulation purity gated by H6 pre-run. | No |
| 3 — Continuous headroom | **Confirmatory (interaction, pre-specified)** | Graded `supplier_hXX` variants (payoff-only retune; headroom arithmetic + realized-order gated pre-run). Prediction: positive `spec × realized_headroom` interaction on value created. | Yes |
| 4 — Frontier model | Exploratory (capability scaling) | Re-run Study-2 grid on a frontier model (`grok-4.3`). Re-estimate H1–H6; compare SPEC effects to gpt-4o-mini + haiku. | No |

Harness changes (correctness only, no hypothesis change; mirror Study-1 Amendment 8a): added
`--conditions` (condition-subset selector) and `--opponent` (focal-vs-fixed-opponent) flags to
`run_experiment.py`, unit-tested in `test_robustness.py`; default behavior unchanged. All arms
isolate via `--data-dir`/`--logs-dir`. Components 1, 2, 4 ran 2026-06-08 (clean — see
RESULTS_SUMMARY.md); Component 3 (headroom) deferred at the pre-run gate (below).

**2026-06-08 — Component-3 headroom retune (pre-results, gate-driven).** The original graded
series (`supplier_h05..h50`, headroom set analytically at the *naive* bundle) FAILED the
realized-monotonicity pre-run gate (NEUTRAL pilot 2026-06-07, N=6: realized headroom
.108/.429/.375/.417/.372 — clustered ~.40 across h15..h50, non-monotone; analytic naive-bundle
headroom does not map to a realized NEUTRAL gradient). Per the design rule "retune before seeing
SPEC results, never after," the variants were retuned **using only the NEUTRAL realized-headroom
diagnostic** (no treatment/SPEC data examined): the retuned series (`supplier_h10..h50`,
generated + arithmetic-asserted by `code/gen_headroom_variants.py`) targets the **mid-grid proxy
bundle** (vol=150, warranty=3 — NEUTRAL's typical landing) so realized headroom grades evenly
~.10/.20/.30/.40/.50 and is monotone at every sub-Pareto level. Pareto joint stays fixed at 960;
the dose-response x-axis is the **measured** realized NEUTRAL headroom per variant (continuous
covariate), with the labels as bins. Re-piloted at 30 dyads/variant before the main run; gate
result logged in `PILOT_GATE_AUDIT.md`. The pre-specified prediction (positive `spec ×
realized_headroom` interaction) is unchanged.
