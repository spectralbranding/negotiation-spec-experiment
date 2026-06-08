---
title: "Study 2 Rationale — Why a New Preregistered Study, Not a Re-analysis"
status: companion to PREREGISTRATION_STUDY2.md
author: Dmitry Zharnikov
date: 2026-06-06
---

# Study 2 Rationale

## The one-sentence claim

Study 2 is a **new, separately preregistered confirmatory study** motivated by a diagnosed
**value ceiling** in Study 1's scenarios — it is **not** a re-analysis of Study 1's data and
**not** an edit of Study 1's frozen scenarios.

## What Study 1 found

Study 1 (gpt-4o-mini @ temperature .20, 630 dyads, six conditions) returned a **null on its
primary hypothesis** (H3, value created): the specification-first agent `SPEC_NOCOT` tied
with `COT_ONLY`, `WARMTH`, and `NEUTRAL` (~641–650 joint points); `SPEC_NOCOT − NEUTRAL`
was d = .049, p = .683. Two results held robustly and are carried forward as positive
controls: `DOMINANCE` craters deal rate (.51 vs .90, d = −.93) and value created (d = −.41),
replicating the base paper (Vaccaro et al., arXiv 2503.06416); and the H6 manipulation check
confirmed SPEC scores low on both warmth and dominance.

## Why the null is most likely a ceiling, not a refutation

In Study 1's integrative scenarios, the bare-cooperative `NEUTRAL` agent already reached
~641 of ~658 reachable joint points — **about 97% of the Pareto frontier.** The single
logroll in each scenario was easy enough that default cooperative play found it, leaving
almost no headroom for an explicit logrolling specification to add measurable value. When
the surplus is already captured by vibe-cooperation, SPEC and NEUTRAL must converge by
construction. That is a property of the *test scenarios*, not evidence about the
specification lever.

## What Study 2 changes — and what it deliberately does not

**Changes (exactly one design factor):** the scenario set. Study 2 introduces three new
self-contained scenarios engineered so a naive cooperative agent does **not** automatically
reach the Pareto frontier:

- `merger` — 5 issues, naive joint 772 vs Pareto 1120 (**31% headroom**).
- `supplier` — 4 issues incl. a compatible issue and a distractor, naive joint 520 vs
  Pareto 960 (**46% headroom**).
- `salvage` — distributive, narrow ZOPA (width $15) so claiming-without-impasse is hard.

The headroom levers (compatible issue, distractor issue, strong non-obvious weight
asymmetry, tight reservation values, narrow ZOPA) are documented and arithmetically
verified in `scenarios_study2/README.md`.

**Does not change:** the six conditions (`NEUTRAL`/`WARMTH`/`DOMINANCE`/`COT_ONLY`/
`SPEC_NOCOT`/`SPEC_COT`), the frozen prompt bodies in `prompts/`, the outcome definitions,
the analysis model and contrasts, the scoring rubrics (including the v2.1 dominance rubric
adopted in Study 1), and the stopping-rule gates. Study 1's frozen artifacts
(`PREREGISTRATION.md`, `EXPERIMENT_DESIGN.md`, `scenarios/`, `prompts/`) are untouched;
Study 2 is additive files only.

## Why this is not p-hacking the Study 1 null

1. **Preregistered before any Study 2 run.** The hypotheses, scenarios, sample size, and
   analysis are frozen (`PREREGISTRATION_STUDY2.md`) before the first Study 2 paid call.
2. **A single, mechanistic, a-priori reason** for the one design change (the ceiling), with
   the headroom gap quantified analytically **in advance** and a **pre-specified pilot
   check** that the gap is real (NEUTRAL value-created/Pareto materially below Study 1's
   ~97%; target < ~85%). If the new scenarios fail to create headroom, the remedy
   (more asymmetry / more issues) is applied in a logged amendment **before** the main run,
   never after seeing SPEC results.
3. **New data, same analysis.** Study 2 collects fresh transcripts under the same
   conditions and the identical analysis plan. No Study 1 transcript is re-scored,
   re-segmented, or re-modeled to manufacture a positive result. There is no forking-path
   search over Study 1's data.
4. **Both outcomes published.** If `SPEC_NOCOT` still fails to beat `NEUTRAL` and
   `COT_ONLY` on value created *given a confirmed headroom gap*, that is a **stronger**
   negative result than Study 1's — it cannot be blamed on a ceiling — and it is reported
   in full (no file-drawer). The Study 1 null, the DOMINANCE replication, and the H6
   success are all reported alongside Study 2 regardless of how Study 2 lands.

## How Study 1 and Study 2 are reported together

Any write-up reports Study 1 first (null on H3, with the ceiling diagnosis and the
DOMINANCE/H6 positive controls), then Study 2 as the headroom-restored confirmatory test.
The pre-specified Study 1 ↔ Study 2 comparison — the NEUTRAL value-created-as-fraction-of-
Pareto in each study — is itself a reported result, because it operationalizes the ceiling
diagnosis and licenses the interpretation of whatever Study 2 finds.
