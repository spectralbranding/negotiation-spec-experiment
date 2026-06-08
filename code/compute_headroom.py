#!/usr/bin/env python3
"""Headroom dose-response analysis (Component 3).

Two modes, auto-detected from the conditions present in outcomes.csv:

  PILOT (NEUTRAL only): per-variant deal rate + realized NEUTRAL headroom; checks the
    pre-run gate (deal rate in [.3,.95]; realized headroom monotone across h10..h50).

  FULL (NEUTRAL + SPEC_NOCOT [+ COT_ONLY]): the above, plus per-variant
    SPEC_NOCOT - NEUTRAL value-created delta (Welch t, Cohen d) and the pre-specified
    spec x realized_headroom interaction (OLS) — the dose-response slope.

Realized headroom = 1 - mean(value_created | deal) / PARETO_JOINT, computed on DEALS only
(an impasse scores value_created = sum of BATNAs, a non-landing artifact, so it is excluded
from the "what a naive pair leaves on the table" measure; deal rate is reported separately).

    uv run --with pandas --with scipy --with numpy --with statsmodels python \
      code/compute_headroom.py \
      --input data_headroom/outcomes.csv
"""

from __future__ import annotations

import argparse
import sys

import numpy as np
import pandas as pd
from scipy import stats

PARETO_JOINT = (
    960.0  # fixed across all supplier_h10..h50 variants (gen_headroom_variants.py)
)
VARIANT_ORDER = [
    "supplier_h10",
    "supplier_h20",
    "supplier_h30",
    "supplier_h40",
    "supplier_h50",
]


def cohen_d(a: np.ndarray, b: np.ndarray) -> float:
    na, nb = len(a), len(b)
    if na < 2 or nb < 2:
        return float("nan")
    sa, sb = a.std(ddof=1), b.std(ddof=1)
    pooled = np.sqrt(((na - 1) * sa**2 + (nb - 1) * sb**2) / (na + nb - 2))
    return float((a.mean() - b.mean()) / pooled) if pooled > 0 else float("nan")


def per_variant_neutral(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    neu = df[(df["cond_a"] == "NEUTRAL") & (df["cond_b"] == "NEUTRAL")]
    for v in VARIANT_ORDER:
        sub = neu[neu["scenario_id"] == v]
        if len(sub) == 0:
            continue
        deals = sub[sub["deal"] == 1]
        deal_rate = float(sub["deal"].mean())
        vc_deal = float(deals["value_created"].mean()) if len(deals) else float("nan")
        realized_h = 1 - vc_deal / PARETO_JOINT if vc_deal == vc_deal else float("nan")
        rows.append(
            {
                "variant": v,
                "n": len(sub),
                "n_deals": len(deals),
                "deal_rate": round(deal_rate, 3),
                "neutral_vc_deal": round(vc_deal, 1) if vc_deal == vc_deal else None,
                "realized_headroom": (
                    round(realized_h, 3) if realized_h == realized_h else None
                ),
            }
        )
    return pd.DataFrame(rows)


def gate_check(vt: pd.DataFrame) -> bool:
    rh = vt["realized_headroom"].tolist()
    dr = vt["deal_rate"].tolist()
    monotone = all(
        rh[i] < rh[i + 1]
        for i in range(len(rh) - 1)
        if rh[i] is not None and rh[i + 1] is not None
    )
    in_band = all(d is not None and 0.30 <= d <= 0.95 for d in dr)
    print("\n=== GATE CHECK ===")
    print(
        f"  realized headroom monotone (h10<h20<h30<h40<h50): {'PASS' if monotone else 'FAIL'}  ({rh})"
    )
    print(
        f"  deal rate in [.30,.95] all variants:               {'PASS' if in_band else 'FAIL'}  ({dr})"
    )
    verdict = monotone and in_band
    print(
        f"  GATE: {'PASS — proceed to full headroom run' if verdict else 'FAIL — retune (bounded) or fall back to analytic x-axis'}"
    )
    return verdict


def dose_response(df: pd.DataFrame, vt: pd.DataFrame) -> None:
    if not ((df["cond_a"] == "SPEC_NOCOT") | (df["cond_b"] == "SPEC_NOCOT")).any():
        print("\n[full-mode skipped: no SPEC_NOCOT rows — this is a NEUTRAL pilot]")
        return
    print(
        "\n=== DOSE-RESPONSE: SPEC_NOCOT - NEUTRAL by variant (value created, deals only) ==="
    )
    rh_map = {r["variant"]: r["realized_headroom"] for _, r in vt.iterrows()}
    long_rows = []
    print(
        f"{'variant':<15}{'realized_h':>11}{'spec_vc':>9}{'neu_vc':>8}{'delta':>8}{'d':>7}{'p':>8}"
    )
    for v in VARIANT_ORDER:
        sub = df[df["scenario_id"] == v]
        # focal-agent value_created is joint (shared), so use dyads where the condition appears
        spec = (
            sub[
                ((sub["cond_a"] == "SPEC_NOCOT") | (sub["cond_b"] == "SPEC_NOCOT"))
                & (sub["deal"] == 1)
            ]["value_created"]
            .dropna()
            .values
        )
        neu = (
            sub[
                (sub["cond_a"] == "NEUTRAL")
                & (sub["cond_b"] == "NEUTRAL")
                & (sub["deal"] == 1)
            ]["value_created"]
            .dropna()
            .values
        )
        if len(spec) < 2 or len(neu) < 2:
            continue
        t, p = stats.ttest_ind(spec, neu, equal_var=False)
        d = cohen_d(spec, neu)
        print(
            f"{v:<15}{rh_map.get(v):>11}{spec.mean():>9.1f}{neu.mean():>8.1f}"
            f"{spec.mean()-neu.mean():>8.1f}{d:>7.3f}{p:>8.3f}"
        )
        for val in spec:
            long_rows.append(
                {"value_created": val, "is_spec": 1, "realized_h": rh_map.get(v)}
            )
        for val in neu:
            long_rows.append(
                {"value_created": val, "is_spec": 0, "realized_h": rh_map.get(v)}
            )

    # interaction model: value_created ~ is_spec * realized_h
    try:
        import statsmodels.formula.api as smf

        ld = pd.DataFrame(long_rows).dropna()
        m = smf.ols("value_created ~ is_spec * realized_h", data=ld).fit()
        coef = m.params.get("is_spec:realized_h", float("nan"))
        pval = m.pvalues.get("is_spec:realized_h", float("nan"))
        print("\n=== spec x realized_headroom INTERACTION (OLS) ===")
        print(f"  interaction coefficient: {coef:.1f}  (p = {pval:.3f})")
        print(
            f"  reading: SPEC advantage {'GROWS with' if coef > 0 else 'does NOT grow with'} headroom"
            f" — {'positive slope (P1 dose-response supported)' if (coef > 0 and pval < .05) else 'slope not significant; report threshold not slope'}"
        )
    except Exception as e:  # pragma: no cover
        print(f"\n[interaction model skipped: {e}]")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    args = ap.parse_args()
    df = pd.read_csv(args.input)
    print(f"[compute_headroom] {len(df)} dyads from {args.input}")
    vt = per_variant_neutral(df)
    print("\n=== PER-VARIANT NEUTRAL (deals only; Pareto=960) ===")
    print(vt.to_string(index=False))
    gate_check(vt)
    dose_response(df, vt)
    return 0


if __name__ == "__main__":
    sys.exit(main())
