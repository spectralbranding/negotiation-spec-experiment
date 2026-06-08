# Headroom Scenarios — Graded Headroom Series (retuned 2026-06-08)

Five variants of the `supplier` scenario (`scenarios_study2/supplier.yaml`) graded to span
realized value-creation headroom from ~10% to ~50%. Used in Component 3 of the extension
(EXTENSION_DESIGN.md §3): the continuous-headroom dose-response test.

**SSOT for every payoff number here is `code/gen_headroom_variants.py`** — it emits these
YAMLs and asserts all invariants. Regenerate with:

    uv run python research/negotiation_spec_experiment/code/gen_headroom_variants.py

The runner loads them via `--scenarios-dir scenarios_headroom --scenario-ids
supplier_h10,supplier_h20,supplier_h30,supplier_h40,supplier_h50`.

---

## Why this is a RETUNE (logged amendment)

The original series (`supplier_h05..h50`) set headroom analytically at the **naive** bundle
(vol=100, warranty=3) to 5/15/25/40/50%. That ladder is monotone by construction, but it
**FAILED the realized-monotonicity pre-run gate** (PILOT_GATE_AUDIT.md, Extension Gate,
2026-06-07): a NEUTRAL pair does **not** land at the naive bundle — it lands nearer mid-grid —
so the *realized* NEUTRAL headroom clustered ~.40 across h15..h50 (.108/.429/.375/.417/.372,
non-monotone, N=6 noisy).

The retune (2026-06-08) fixes the diagnosis directly:

1. **Target the mid-grid proxy bundle** (vol=150, warranty=3 — NEUTRAL's typical landing),
   not the naive bundle, so the design lever is aligned with where naive pairs actually settle.
2. **Even, wide spacing**: mid-grid joint = 960·(1−h) for h ∈ {.10,.20,.30,.40,.50}, i.e.
   860/770/670/570/480 — realized headroom ~.10/.20/.30/.40/.50.
3. **Monotone at every sub-Pareto level** (naive, mid-grid, and the approach to Pareto), so the
   ordering survives NEUTRAL landing-point variability.
4. **Labels denote target *realized* headroom** (h10..h50). The dose-response x-axis is the
   **measured** realized headroom per variant from the 30-dyad/variant re-pilot, used as a
   continuous covariate — the labels are only bins.

This follows the design rule "never retune after seeing SPEC results": the retune is driven
solely by the NEUTRAL realized-headroom gate, before any SPEC/treatment data is collected.

---

## What is headroom?

headroom = (Pareto_joint − bundle_joint) / Pareto_joint,  with Pareto_joint = 960 (all variants).

Value is created on two issues a naive pair misses:
- **volume_commit_kunits** (COMPATIBLE — both want HIGH; a naive haggler settles it LOW).
- **warranty_years** (LOGROLL — supplier wants 1y, buyer ~indifferent; naive splits to 3y).

`unit_price_usd` is zero-sum (joint constant 160) and `payment_terms_days` is a near-flat
distractor (joint 40 band) — both **identical** to the base supplier across all variants.

---

## Per-variant arithmetic (emitted + asserted by the generator)

| Variant | Target realized h | Naive joint (vol100/warr3) | Naive h | Mid-grid joint (vol150/warr3) | Mid-grid h | Pareto joint |
|---------|------------------:|---------------------------:|--------:|------------------------------:|-----------:|-------------:|
| h10     | .10               | 790                        | .177    | 860                           | .104       | 960          |
| h20     | .20               | 700                        | .271    | 770                           | .198       | 960          |
| h30     | .30               | 600                        | .375    | 670                           | .302       | 960          |
| h40     | .40               | 500                        | .479    | 570                           | .406       | 960          |
| h50     | .50               | 410                        | .573    | 480                           | .500       | 960          |

Monotone at both the naive and mid-grid levels. Per-issue joint ladders (also asserted
monotone — volume increasing for both roles; warranty supplier-decreasing, buyer-increasing):

| Variant | vol_joint(100) | vol_joint(150) | vol_joint(200) | warr_joint(1) | warr_joint(3) |
|---------|---------------:|---------------:|---------------:|--------------:|--------------:|
| h10     | 330            | 400            | 460            | 300           | 260           |
| h20     | 280            | 350            | 460            | 300           | 220           |
| h30     | 220            | 290            | 460            | 300           | 180           |
| h40     | 160            | 230            | 460            | 300           | 140           |
| h50     | 110            | 180            | 460            | 300           | 100           |

---

## BATNA feasibility

BATNA = 180 both roles, all variants. Both parties clear BATNA at the Pareto AND mid-grid
bundles in every variant (asserted in the generator), so cooperative deals remain feasible and
the deal rate is expected to stay in the [.3, .95] band. Confirmed empirically by the 30-dyad/
variant re-pilot (deal rate + realized headroom recorded in PILOT_GATE_AUDIT.md).

---

## Pre-run gate (per EXTENSION_DESIGN §3.4)

Before the main dose-response run, a 30-dyad/variant NEUTRAL pilot must show realized NEUTRAL
headroom tracking the target order monotonically (h10 < h20 < h30 < h40 < h50) and deal rate in
band. If a variant inverts the order, retune its volume/warranty ladders in the generator (a
logged amendment) before the main run — never after seeing SPEC results.
