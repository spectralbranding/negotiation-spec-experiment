#!/usr/bin/env python3
"""Generate the graded-headroom supplier variants for the dose-response stage.

REPRODUCIBILITY: this script is the SSOT for every payoff number in
scenarios_headroom/supplier_h10..h50.yaml. Run it to regenerate the YAMLs and the
README arithmetic table. No API calls; pure arithmetic + file emission.

    uv run python code/gen_headroom_variants.py

WHY A RETUNE (2026-06-08): the original analytic ladder (supplier_h05..h50, headroom
5/15/25/40/50% by construction at the *naive* bundle) FAILED the realized-monotonicity
gate — a NEUTRAL pair does not land at the naive bundle; it lands nearer mid-grid, so
the realized headroom clustered ~.40 across h15..h50 (PILOT_GATE_AUDIT, Extension Gate).
This retune targets the MID-GRID proxy bundle (vol=150, warranty=3) so the realized
NEUTRAL gradient is evenly spaced (~.10/.20/.30/.40/.50) and monotone at EVERY
sub-Pareto level, widening the separation. Labels now denote target *realized* headroom
(h10..h50), measured per-variant in the re-pilot and used as the continuous x-axis.

DESIGN INVARIANTS (asserted below):
  - Pareto bundle (price=12, vol=200, payment=45, warranty=1) joint = 960 for ALL variants.
  - unit_price zero-sum (joint 160 at any price); payment near-flat (joint 40 band) — both
    identical to base scenarios_study2/supplier.yaml.
  - volume = COMPATIBLE (both payoff ladders increasing in volume).
  - warranty = LOGROLL (supplier ladder strictly decreasing in years; buyer increasing).
  - mid-grid proxy joint = 960*(1-h_target) within +/-1 pt; monotone across variants at the
    naive (vol100/warr3), mid-grid (vol150/warr3) AND Pareto-approach levels.
  - both roles clear BATNA (180) at the Pareto and mid-grid bundles in every variant.
"""

from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT_DIR = HERE.parent / "scenarios_headroom"

# Fixed across all variants (identical to scenarios_study2/supplier.yaml) ----------
BATNA = 180
PRICE_BUYER = {
    10: 160,
    11: 128,
    12: 96,
    13: 64,
    14: 32,
    15: 0,
}  # joint 160 at any price
PRICE_SUPPLIER = {10: 0, 11: 32, 12: 64, 13: 96, 14: 128, 15: 160}
PAY_BUYER = {15: 30, 30: 25, 45: 20, 60: 15, 90: 10}  # near-flat distractor
PAY_SUPPLIER = {15: 10, 30: 15, 45: 20, 60: 25, 90: 30}  # joint 40 at any level
VOL_LEVELS = [50, 100, 150, 200]
WARR_LEVELS = [1, 2, 3, 5]

# Per-variant graded ladders (buyer/supplier), hand-derived, verified by asserts below.
# volume: both INCREASING in volume (compatible). vol=200 fixed at 200/260 (joint 460).
# warranty: supplier DECREASING in years (logroll, claim exposure); buyer INCREASING.
#           warranty=1 fixed at 0/300 (joint 300). vol=50 and warranty=5(supplier) anchor 0.
VARIANTS = {
    "h10": {  # target realized headroom .10
        "vol_buyer": {50: 0, 100: 140, 150: 170, 200: 200},
        "vol_supplier": {50: 0, 100: 190, 150: 230, 200: 260},
        "warr_buyer": {1: 0, 2: 8, 3: 16, 5: 28},
        "warr_supplier": {1: 300, 2: 280, 3: 244, 5: 0},
    },
    "h20": {  # .20
        "vol_buyer": {50: 0, 100: 120, 150: 150, 200: 200},
        "vol_supplier": {50: 0, 100: 160, 150: 200, 200: 260},
        "warr_buyer": {1: 0, 2: 12, 3: 24, 5: 40},
        "warr_supplier": {1: 300, 2: 272, 3: 196, 5: 0},
    },
    "h30": {  # .30
        "vol_buyer": {50: 0, 100: 95, 150: 125, 200: 200},
        "vol_supplier": {50: 0, 100: 125, 150: 165, 200: 260},
        "warr_buyer": {1: 0, 2: 16, 3: 32, 5: 52},
        "warr_supplier": {1: 300, 2: 256, 3: 148, 5: 0},
    },
    "h40": {  # .40
        "vol_buyer": {50: 0, 100: 70, 150: 100, 200: 200},
        "vol_supplier": {50: 0, 100: 90, 150: 130, 200: 260},
        "warr_buyer": {1: 0, 2: 20, 3: 40, 5: 64},
        "warr_supplier": {1: 300, 2: 240, 3: 100, 5: 0},
    },
    "h50": {  # .50
        "vol_buyer": {50: 0, 100: 48, 150: 78, 200: 200},
        "vol_supplier": {50: 0, 100: 62, 150: 102, 200: 260},
        "warr_buyer": {1: 0, 2: 24, 3: 48, 5: 76},
        "warr_supplier": {1: 300, 2: 224, 3: 52, 5: 0},
    },
}
TARGET_H = {"h10": 0.10, "h20": 0.20, "h30": 0.30, "h40": 0.40, "h50": 0.50}

PRICE_PAY_JOINT = 160 + 40  # zero-sum price (160) + distractor payment at net-45 (40)
PARETO_JOINT = 960


def vj(v: dict, level: int, who: str) -> int:
    return v[f"vol_{who}"][level]


def wj(v: dict, level: int, who: str) -> int:
    return v[f"warr_{who}"][level]


def bundle_joint(v: dict, vol: int, warr: int) -> int:
    return (
        PRICE_PAY_JOINT
        + vj(v, vol, "buyer")
        + vj(v, vol, "supplier")
        + wj(v, warr, "buyer")
        + wj(v, warr, "supplier")
    )


def buyer_points(v: dict, price: int, vol: int, pay: int, warr: int) -> int:
    return (
        PRICE_BUYER[price] + vj(v, vol, "buyer") + PAY_BUYER[pay] + wj(v, warr, "buyer")
    )


def supplier_points(v: dict, price: int, vol: int, pay: int, warr: int) -> int:
    return (
        PRICE_SUPPLIER[price]
        + vj(v, vol, "supplier")
        + PAY_SUPPLIER[pay]
        + wj(v, warr, "supplier")
    )


def verify() -> list[dict]:
    rows = []
    prev_naive = prev_mid = -1.0
    for name, v in VARIANTS.items():
        # monotonicity per issue
        for who in ("buyer", "supplier"):
            vols = [vj(v, lv, who) for lv in VOL_LEVELS]
            assert vols == sorted(vols), f"{name} volume {who} not increasing: {vols}"
        wb = [
            wj(v, lv, "buyer") for lv in WARR_LEVELS
        ]  # levels 1,2,3,5 -> buyer increasing
        ws = [wj(v, lv, "supplier") for lv in WARR_LEVELS]  # supplier decreasing
        assert wb == sorted(wb), f"{name} warranty buyer not increasing: {wb}"
        assert ws == sorted(
            ws, reverse=True
        ), f"{name} warranty supplier not decreasing: {ws}"

        pareto = bundle_joint(v, 200, 1)
        assert pareto == PARETO_JOINT, f"{name} Pareto joint {pareto} != 960"

        naive = bundle_joint(v, 100, 3)  # naive split bundle
        mid = bundle_joint(v, 150, 3)  # mid-grid proxy (NEUTRAL typical landing)
        h_naive = (PARETO_JOINT - naive) / PARETO_JOINT
        h_mid = (PARETO_JOINT - mid) / PARETO_JOINT

        # mid-grid proxy must track the target realized headroom within ~1% of Pareto
        # (nominal label only; the x-axis is the MEASURED realized headroom from the pilot)
        assert (
            abs(mid - PARETO_JOINT * (1 - TARGET_H[name])) <= 10.0
        ), f"{name} mid-grid joint {mid} off target {PARETO_JOINT*(1-TARGET_H[name])}"
        # monotone across variants at both naive and mid-grid levels
        assert h_naive > prev_naive, f"{name} naive headroom not monotone"
        assert h_mid > prev_mid, f"{name} mid-grid headroom not monotone"
        prev_naive, prev_mid = h_naive, h_mid

        # BATNA feasibility at Pareto and mid-grid for both roles
        for vol, warr, lbl in [(200, 1, "Pareto"), (150, 3, "mid-grid")]:
            b = buyer_points(v, 12, vol, 45, warr)
            s = supplier_points(v, 12, vol, 45, warr)
            assert (
                b > BATNA and s > BATNA
            ), f"{name} {lbl} below BATNA: buyer {b} supplier {s}"

        rows.append(
            {
                "name": name,
                "target_h": TARGET_H[name],
                "naive_joint": naive,
                "naive_h": round(h_naive, 3),
                "mid_joint": mid,
                "mid_h": round(h_mid, 3),
                "pareto_joint": pareto,
                "vol_j": {
                    lv: vj(v, lv, "buyer") + vj(v, lv, "supplier") for lv in VOL_LEVELS
                },
                "warr_j": {
                    lv: wj(v, lv, "buyer") + wj(v, lv, "supplier") for lv in WARR_LEVELS
                },
            }
        )
    return rows


def opts_block(d: dict, indent: int) -> str:
    pad = " " * indent
    return "\n".join(f"{pad}{k}: {d[k]}" for k in d)


def emit_yaml(name: str, v: dict, row: dict) -> str:
    hpct = f"{TARGET_H[name]*100:.0f}"
    return f"""---
# Scenario: supplier_{name}  (HEADROOM DOSE-RESPONSE — target realized headroom ~{hpct}%)
# Retuned 2026-06-08 by code/gen_headroom_variants.py (SSOT for all numbers below).
# Base template: scenarios_study2/supplier.yaml. Only the volume + warranty payoff
# tables vary across the h10..h50 series; unit_price (zero-sum, joint 160) and
# payment_terms (near-flat distractor, joint 40 band) are IDENTICAL to the base.
#
# HEADROOM (created on two missed moves a naive pair leaves on the table):
#   volume   = COMPATIBLE (both want 200; naive haggler settles it LOW)
#   warranty = LOGROLL    (supplier wants 1y, buyer ~indifferent; naive splits to 3y)
# Pareto (price=12, vol=200, pay=45, warranty=1): joint = {row['pareto_joint']} (fixed all variants)
# Naive  (price=12, vol=100, pay=45, warranty=3): joint = {row['naive_joint']}  -> headroom {row['naive_h']:.3f}
# Mid    (price=12, vol=150, pay=45, warranty=3): joint = {row['mid_joint']}  -> headroom {row['mid_h']:.3f}
#   (mid-grid = NEUTRAL's typical landing; the realized x-axis is MEASURED in the pilot.)

scenario_id: supplier_{name}
type: integrative
description: >
  A procurement buyer and a component supplier negotiate a one-year supply contract on
  four terms: unit price (USD/unit), committed annual volume (k units), payment terms
  (net days), and warranty length (years). Each party has a private point table; the
  full matrix is published. This is the ~{hpct}% headroom variant of the supplier family.

roles:
  - id: buyer
    label: Buyer
    description: >
      You are procurement for a manufacturer. You want a LOW unit price. You also
      genuinely benefit from a HIGH committed volume (it secures supply and locks
      pricing), though it is easy to forget that under price pressure. You are nearly
      indifferent to payment terms and care little about warranty length.
    batna_value: {BATNA}
    batna_description: >
      Source from an alternative supplier on worse terms — worth {BATNA} points.
    private_payoff_card:
      unit_price_usd:
        description: "Lower unit price is better for you."
        options:
{opts_block(PRICE_BUYER, 10)}
      volume_commit_kunits:
        description: "A higher committed volume secures your supply — better for you."
        options:
{opts_block(v['vol_buyer'], 10)}
      payment_terms_days:
        description: "You mildly prefer longer terms, but it barely matters."
        options:
{opts_block(PAY_BUYER, 10)}
      warranty_years:
        description: "A longer warranty is mildly nice but low priority for you."
        options:
{opts_block(v['warr_buyer'], 10)}

  - id: supplier
    label: Supplier
    description: >
      You are the vendor. You want a HIGH unit price. You also strongly benefit from a
      HIGH committed volume (predictable revenue and production planning). You are nearly
      indifferent to payment terms. You care intensely about a SHORT warranty (long
      warranties expose you to costly claims — your top priority).
    batna_value: {BATNA}
    batna_description: >
      Sell the capacity to another customer on worse terms — worth {BATNA} points.
    private_payoff_card:
      unit_price_usd:
        description: "Higher unit price is better for you."
        options:
{opts_block(PRICE_SUPPLIER, 10)}
      volume_commit_kunits:
        description: "A higher committed volume gives predictable revenue — better for you."
        options:
{opts_block(v['vol_supplier'], 10)}
      payment_terms_days:
        description: "You mildly prefer shorter terms, but it barely matters."
        options:
{opts_block(PAY_SUPPLIER, 10)}
      warranty_years:
        description: "A SHORTER warranty is much better for you (claim-cost exposure — top priority)."
        options:
{opts_block(v['warr_supplier'], 10)}

full_payoff_matrix:
  note: >
    Key reference bundles. Full per-issue tables above are published openly. Headroom is
    graded BY DESIGN across the h10..h50 family (this variant target ~{hpct}%).
  key_bundles:
    - label: "Naive (unit_price=12, volume=100, payment=45, warranty=3)"
      unit_price_usd: 12
      volume_commit_kunits: 100
      payment_terms_days: 45
      warranty_years: 3
      buyer_points: {buyer_points(v, 12, 100, 45, 3)}
      supplier_points: {supplier_points(v, 12, 100, 45, 3)}
      joint_points: {row['naive_joint']}
    - label: "Mid-grid (unit_price=12, volume=150, payment=45, warranty=3)"
      unit_price_usd: 12
      volume_commit_kunits: 150
      payment_terms_days: 45
      warranty_years: 3
      buyer_points: {buyer_points(v, 12, 150, 45, 3)}
      supplier_points: {supplier_points(v, 12, 150, 45, 3)}
      joint_points: {row['mid_joint']}
    - label: "Pareto-optimal (high volume both, short warranty, distractor neutral)"
      unit_price_usd: 12
      volume_commit_kunits: 200
      payment_terms_days: 45
      warranty_years: 1
      buyer_points: {buyer_points(v, 12, 200, 45, 1)}
      supplier_points: {supplier_points(v, 12, 200, 45, 1)}
      joint_points: {row['pareto_joint']}

analytic_optimum:
  description: >
    Pareto-optimal bundle: unit_price=$12/unit, volume=200k units, payment=net-45,
    warranty=1 year. unit_price is zero-sum (joint constant 160); payment is a near-flat
    distractor (joint ~40). Value is created on volume (compatible) and warranty (logroll).
  best_bundle:
    unit_price_usd: 12
    volume_commit_kunits: 200
    payment_terms_days: 45
    warranty_years: 1
  buyer_points: {buyer_points(v, 12, 200, 45, 1)}
  supplier_points: {supplier_points(v, 12, 200, 45, 1)}
  joint_points: {row['pareto_joint']}

offer_protocol:
  description: >
    Agents MUST use the structured offer protocol. A valid offer is an OFFER: line
    containing a JSON object whose keys are the four issue names exactly as they appear
    in the payoff card (unit_price_usd, volume_commit_kunits, payment_terms_days,
    warranty_years). Every value is a number drawn from the option set.
    Acceptance: ACCEPT on its own line. Rejection/counter: plain text + new OFFER.
    Example: 'OFFER: {{"unit_price_usd": 12, "volume_commit_kunits": 200, "payment_terms_days": 45, "warranty_years": 1}}'

max_rounds: 14
"""


def main() -> int:
    rows = verify()
    OUT_DIR.mkdir(exist_ok=True)
    # remove the stale analytic-ladder variants (h05/h15/h25/h40/h50 naive-tuned)
    for old in OUT_DIR.glob("supplier_h*.yaml"):
        old.unlink()
    for name, v in VARIANTS.items():
        row = next(r for r in rows if r["name"] == name)
        (OUT_DIR / f"supplier_{name}.yaml").write_text(emit_yaml(name, v, row))
    print("Wrote", len(VARIANTS), "variants to", OUT_DIR)
    print(
        f"{'variant':<8}{'target_h':>9}{'naive_h':>9}{'mid_h':>8}{'vol_j(150)':>12}{'warr_j(3)':>11}"
    )
    for r in rows:
        print(
            f"{r['name']:<8}{r['target_h']:>9.2f}{r['naive_h']:>9.3f}{r['mid_h']:>8.3f}"
            f"{r['vol_j'][150]:>12}{r['warr_j'][3]:>11}"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
