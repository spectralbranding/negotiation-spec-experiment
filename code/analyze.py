"""analyze.py — statistical analysis of negotiation experiment outcomes.

Loads outcomes.csv, fits the pre-specified models from PREREGISTRATION §4,
computes contrasts + Cohen's d + exact p-values, and emits tables/figures.

Formatting follows PAPER_QUALITY_STANDARDS:
  - No leading zero on decimals below 1: .976 not 0.976
  - Exact p-values, three digits: p = .047
  - p < .001 floor (no smaller values reported)
  - No significance stars
  - Effect sizes mandatory alongside every hypothesis test
  - Table captions ABOVE table (in code comments/print); figure captions BELOW
  - ASCII-only axis labels (no Unicode)

Mixed model (primary):
    outcome ~ C(agent_type) + C(scenario) + C(role_order) + (1|opponent) + (1|dyad_id)
    - Full mixed model via statsmodels MixedLM where applicable
    - Fallback to OLS with cluster-robust SE (documented) if MixedLM fails to converge
      (common with small pilot data)

Usage:
    uv run python code/analyze.py
    uv run python code/analyze.py \\
        --input dryrun/outcomes.csv
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

try:
    import pandas as pd  # noqa: F401 — used in type annotations + function bodies
except ImportError:
    pd = None  # type: ignore[assignment]

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------
EXPERIMENT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = EXPERIMENT_DIR / "data" / "outcomes.csv"
DEFAULT_OUTPUT_TABLES = EXPERIMENT_DIR / "output" / "tables"
DEFAULT_OUTPUT_FIGURES = EXPERIMENT_DIR / "output" / "figures"


# ---------------------------------------------------------------------------
# Formatting helpers (PAPER_QUALITY_STANDARDS)
# ---------------------------------------------------------------------------


def fmt_p(p: float) -> str:
    """Format p-value per PAPER_QUALITY_STANDARDS: 3 decimals, no leading zero, floor .001."""
    if p < 0.001:
        return "p < .001"
    s = f"{p:.3f}"
    # Remove leading zero: "0.047" -> ".047"
    if s.startswith("0."):
        s = s[1:]
    elif s.startswith("-0."):
        s = "-" + s[2:]
    return f"p = {s}"


def fmt_d(d: float) -> str:
    """Format Cohen's d: 3 decimal places, no leading zero."""
    s = f"{abs(d):.3f}"
    if s.startswith("0."):
        s = s[1:]
    sign = "-" if d < 0 else ""
    return f"d = {sign}{s}"


def fmt_mean(v: float) -> str:
    """Format a mean to 2 decimal places."""
    return f"{v:.2f}"


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------


def load_outcomes(path: Path) -> Any:
    """Load outcomes CSV, validate columns, return DataFrame."""
    try:
        import pandas as pd
    except ImportError:
        raise RuntimeError("pandas not installed. Run: uv add pandas")

    if not path.exists():
        raise FileNotFoundError(f"Outcomes file not found: {path}")

    df = pd.read_csv(path)
    required = ["dyad_id", "scenario_id", "cond_a", "cond_b", "deal", "value_created"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"Outcomes CSV missing required columns: {missing}")

    print(f"[analyze] Loaded {len(df)} rows from {path}")
    print(f"  Conditions: {sorted(df['cond_a'].unique().tolist())}")
    print(f"  Scenarios: {sorted(df['scenario_id'].unique().tolist())}")
    print(f"  Deal rate: {df['deal'].mean():.3f}")
    return df


# ---------------------------------------------------------------------------
# Feature engineering
# ---------------------------------------------------------------------------


def engineer_features(df: Any) -> Any:
    """Add derived columns for analysis."""
    import pandas as pd

    # Agent type = condition of the focal agent.
    # For dyad-level analysis, we treat the analysis from each agent's perspective.
    # Strategy: stack A and B into a long format where each row is one agent's perspective.
    rows = []
    for _, r in df.iterrows():
        for side in ["a", "b"]:
            other_side = "b" if side == "a" else "a"
            rows.append(
                {
                    "dyad_id": r["dyad_id"],
                    "scenario_id": r["scenario_id"],
                    "scenario_type": r.get("scenario_type", ""),
                    "agent_type": r[f"cond_{side}"],
                    "opponent_type": r[f"cond_{other_side}"],
                    "role": r[f"role_{side}"],
                    "replicate": r.get("replicate", 0),
                    "deal": float(r["deal"]),
                    "value_claimed": (
                        float(r[f"value_claimed_{side}"])
                        if pd.notna(r.get(f"value_claimed_{side}"))
                        else float("nan")
                    ),
                    "value_created": (
                        float(r["value_created"])
                        if pd.notna(r.get("value_created"))
                        else float("nan")
                    ),
                    "warmth": (
                        float(r[f"warmth_{side}_mean"])
                        if pd.notna(r.get(f"warmth_{side}_mean"))
                        else float("nan")
                    ),
                    "dominance": (
                        float(r[f"dominance_{side}_mean"])
                        if pd.notna(r.get(f"dominance_{side}_mean"))
                        else float("nan")
                    ),
                    "svi": (
                        float(r[f"svi_{side}_mean"])
                        if pd.notna(r.get(f"svi_{side}_mean"))
                        else float("nan")
                    ),
                    "mock": bool(r.get("mock", True)),
                }
            )

    long = pd.DataFrame(rows)

    # Role-order flag (for controlling role advantage)
    long["role_order"] = long["role"].astype(str)

    # Scenario dummies
    long["is_integrative"] = (long["scenario_type"] == "integrative").astype(int)
    long["is_distributive"] = (long["scenario_type"] == "distributive").astype(int)

    return long


# ---------------------------------------------------------------------------
# Statistical analysis
# ---------------------------------------------------------------------------


def cohen_d(group1: Any, group2: Any) -> float:
    """Compute Cohen's d between two samples."""
    import math

    n1, n2 = len(group1), len(group2)
    m1, m2 = group1.mean(), group2.mean()
    v1, v2 = group1.var(ddof=1), group2.var(ddof=1)
    if n1 + n2 <= 2:
        return float("nan")
    pooled_sd = math.sqrt(((n1 - 1) * v1 + (n2 - 1) * v2) / (n1 + n2 - 2))
    if pooled_sd == 0:
        return float("nan")
    return (m1 - m2) / pooled_sd


def fit_mixed_model(
    df: Any,
    outcome_col: str,
    group_col: str = "opponent_type",
    fallback_to_ols: bool = True,
) -> tuple[Any, str]:
    """Fit outcome ~ C(agent_type) + C(scenario_id) + C(role_order) with random groups.

    Returns (result, method_string).
    method_string = "MixedLM" or "OLS_cluster_robust".

    Primary model per PREREGISTRATION §4:
        outcome ~ agent_type + scenario + role_order + (1|opponent_id) + (1|dyad_id)

    Fallback (documented): OLS with cluster-robust SE clustered on opponent_type.
    This is the pre-specified fallback for small samples / convergence failures.
    """
    import pandas as pd

    sub = df[
        [outcome_col, "agent_type", "scenario_id", "role_order", group_col]
    ].dropna()
    if len(sub) < 10:
        raise ValueError(
            f"Too few observations ({len(sub)}) for outcome '{outcome_col}'. "
            "Need at least 10 complete rows."
        )

    try:
        import statsmodels.formula.api as smf

        formula = f"{outcome_col} ~ C(agent_type) + C(scenario_id) + C(role_order)"
        import warnings

        try:
            model = smf.mixedlm(
                formula,
                data=sub,
                groups=sub[group_col],
            )
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                result = model.fit(reml=True, method=["lbfgs"], maxiter=200)
            # Check for convergence: if gradient norm is large, treat as failed
            converged = getattr(result, "converged", True)
            if not converged and fallback_to_ols:
                raise ValueError("MixedLM did not converge (pilot data too sparse)")
            return result, "MixedLM"
        except Exception as mix_err:
            if not fallback_to_ols:
                raise
            # Documented fallback: OLS with cluster-robust SE
            # Pre-registered as acceptable for small pilot data.
            ols_model = smf.ols(formula, data=sub)
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                result = ols_model.fit(
                    cov_type="cluster",
                    cov_kwds={"groups": sub[group_col]},
                )
            return result, f"OLS_cluster_robust (MixedLM failed: {mix_err})"

    except ImportError:
        raise RuntimeError("statsmodels not installed. Run: uv add statsmodels")


def extract_contrasts(
    df: Any,
    outcome_col: str,
    baseline: str = "NEUTRAL",
) -> list[dict]:
    """Compute pre-specified pairwise contrasts for the outcome.

    Pre-specified contrasts (PREREGISTRATION §4):
      - SPEC_NOCOT - NEUTRAL
      - SPEC_NOCOT - COT_ONLY
      - SPEC_NOCOT - WARMTH
      - SPEC_NOCOT - DOMINANCE
      - (SPEC_COT - COT_ONLY) - (SPEC_NOCOT - NEUTRAL)  [interaction]

    Returns list of dicts with mean_diff, cohens_d, p_value, n_a, n_b, method.
    Uses Welch t-test for each pairwise contrast.
    """
    try:
        from scipy import stats as scipy_stats
    except ImportError:
        raise RuntimeError("scipy not installed. Run: uv add scipy")

    import pandas as pd

    sub = df[["agent_type", outcome_col]].dropna()
    groups: dict[str, pd.Series] = {
        c: sub[sub["agent_type"] == c][outcome_col] for c in sub["agent_type"].unique()
    }

    contrasts = [
        ("SPEC_NOCOT", "NEUTRAL"),
        ("SPEC_NOCOT", "COT_ONLY"),
        ("SPEC_NOCOT", "WARMTH"),
        ("SPEC_NOCOT", "DOMINANCE"),
        ("SPEC_COT", "COT_ONLY"),
        ("SPEC_COT", "WARMTH"),
        ("WARMTH", "NEUTRAL"),
        ("DOMINANCE", "NEUTRAL"),
    ]

    results = []
    for cond_a, cond_b in contrasts:
        g_a = groups.get(cond_a, pd.Series(dtype=float))
        g_b = groups.get(cond_b, pd.Series(dtype=float))
        if len(g_a) < 2 or len(g_b) < 2:
            results.append(
                {
                    "contrast": f"{cond_a} - {cond_b}",
                    "mean_a": float(g_a.mean()) if len(g_a) > 0 else float("nan"),
                    "mean_b": float(g_b.mean()) if len(g_b) > 0 else float("nan"),
                    "mean_diff": float("nan"),
                    "cohens_d": float("nan"),
                    "p_value": float("nan"),
                    "p_fmt": "insufficient data",
                    "d_fmt": "d = nan",
                    "n_a": len(g_a),
                    "n_b": len(g_b),
                    "method": "welch_t",
                }
            )
            continue
        t_stat, p_val = scipy_stats.ttest_ind(g_a, g_b, equal_var=False)
        d = cohen_d(g_a, g_b)
        results.append(
            {
                "contrast": f"{cond_a} - {cond_b}",
                "mean_a": float(g_a.mean()),
                "mean_b": float(g_b.mean()),
                "mean_diff": float(g_a.mean() - g_b.mean()),
                "cohens_d": d,
                "p_value": float(p_val),
                "p_fmt": fmt_p(p_val),
                "d_fmt": fmt_d(d),
                "n_a": len(g_a),
                "n_b": len(g_b),
                "method": "welch_t",
            }
        )

    # Interaction: (SPEC_COT - COT_ONLY) - (SPEC_NOCOT - NEUTRAL)
    sc_co = groups.get("SPEC_COT", pd.Series(dtype=float)).mean()
    co_co = groups.get("COT_ONLY", pd.Series(dtype=float)).mean()
    sn_ne = groups.get("SPEC_NOCOT", pd.Series(dtype=float)).mean()
    ne_ne = groups.get("NEUTRAL", pd.Series(dtype=float)).mean()
    interaction = (sc_co - co_co) - (sn_ne - ne_ne)
    results.append(
        {
            "contrast": "(SPEC_COT - COT_ONLY) - (SPEC_NOCOT - NEUTRAL) [interaction]",
            "mean_a": float("nan"),
            "mean_b": float("nan"),
            "mean_diff": float(interaction) if pd.notna(interaction) else float("nan"),
            "cohens_d": float("nan"),
            "p_value": float("nan"),
            "p_fmt": "see mixed model",
            "d_fmt": "n/a",
            "n_a": -1,
            "n_b": -1,
            "method": "raw_difference",
        }
    )

    return results


# ---------------------------------------------------------------------------
# Descriptive statistics table
# ---------------------------------------------------------------------------


def descriptive_table(df: Any, outcome_cols: list[str]) -> Any:
    """Compute N, mean, SD per (agent_type, scenario_id) for outcome_cols."""
    try:
        import pandas as pd
    except ImportError:
        raise RuntimeError("pandas not installed.")

    records = []
    for cond in sorted(df["agent_type"].unique()):
        for scen in sorted(df["scenario_id"].unique()):
            sub = df[(df["agent_type"] == cond) & (df["scenario_id"] == scen)]
            row: dict[str, Any] = {
                "agent_type": cond,
                "scenario_id": scen,
                "n": len(sub),
            }
            for col in outcome_cols:
                vals = sub[col].dropna()
                row[f"{col}_mean"] = (
                    round(vals.mean(), 2) if len(vals) > 0 else float("nan")
                )
                row[f"{col}_sd"] = (
                    round(vals.std(ddof=1), 2) if len(vals) > 1 else float("nan")
                )
            records.append(row)

    return pd.DataFrame(records)


# ---------------------------------------------------------------------------
# Figure generation
# ---------------------------------------------------------------------------


def plot_outcomes_by_condition(
    df: Any,
    outcome_col: str,
    title: str,
    output_path: Path,
) -> None:
    """Bar plot of mean outcome by condition, error bars = 1 SD.

    Figures have captions BELOW. ASCII-only axis labels.
    """
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import numpy as np
    except ImportError:
        print(f"  [WARN] matplotlib not installed, skipping figure: {output_path.name}")
        return

    sub = df[["agent_type", outcome_col]].dropna()
    conditions = sorted(sub["agent_type"].unique())
    means = [sub[sub["agent_type"] == c][outcome_col].mean() for c in conditions]
    sds = [sub[sub["agent_type"] == c][outcome_col].std(ddof=1) for c in conditions]
    ns = [len(sub[sub["agent_type"] == c]) for c in conditions]

    fig, ax = plt.subplots(figsize=(8, 5))
    x = np.arange(len(conditions))
    ax.bar(
        x, means, yerr=sds, capsize=4, alpha=0.8, color="steelblue", edgecolor="black"
    )
    ax.set_xticks(x)
    ax.set_xticklabels(conditions, rotation=20, ha="right")
    ax.set_xlabel("Agent Condition")
    ax.set_ylabel(outcome_col.replace("_", " ").title())
    ax.set_title(title)

    # Add n labels
    for i, (m, n) in enumerate(zip(means, ns)):
        if not __import__("math").isnan(m):
            ax.text(i, m + (max(sds) or 1) * 0.1, f"n={n}", ha="center", fontsize=8)

    # Caption BELOW (as text below figure)
    caption = f"Note: Means with SD error bars. n per condition shown above bars."
    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close()

    # Write caption sidecar
    caption_path = output_path.with_suffix(".caption.txt")
    caption_path.write_text(f"{title}\n{caption}\nGenerated from: outcomes.csv\n")


def plot_deal_rate_by_condition(
    df: Any,
    output_path: Path,
) -> None:
    """Bar plot of deal rate by agent condition."""
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import numpy as np
    except ImportError:
        print(f"  [WARN] matplotlib not installed, skipping figure: {output_path.name}")
        return

    sub = df[["agent_type", "deal"]].dropna()
    conditions = sorted(sub["agent_type"].unique())
    rates = [sub[sub["agent_type"] == c]["deal"].mean() for c in conditions]
    ns = [len(sub[sub["agent_type"] == c]) for c in conditions]

    fig, ax = plt.subplots(figsize=(8, 5))
    x = np.arange(len(conditions))
    ax.bar(x, rates, alpha=0.8, color="darkorange", edgecolor="black")
    ax.set_xticks(x)
    ax.set_xticklabels(conditions, rotation=20, ha="right")
    ax.set_xlabel("Agent Condition")
    ax.set_ylabel("Deal Rate (proportion)")
    ax.set_ylim(0, 1.1)
    ax.axhline(0.5, color="gray", linestyle="--", alpha=0.5, label="50% reference")
    ax.set_title("H1: Deal Rate by Agent Condition")
    ax.legend()

    for i, (r, n) in enumerate(zip(rates, ns)):
        if not __import__("math").isnan(r):
            ax.text(i, r + 0.02, f"{r:.2f}\nn={n}", ha="center", fontsize=8)

    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close()

    caption_path = output_path.with_suffix(".caption.txt")
    caption_path.write_text(
        "H1: Deal Rate by Agent Condition.\n"
        "Note: Proportion of dyads reaching agreement by agent condition (both sides pooled). "
        "Dashed line = 50% reference.\n"
        "Generated from: outcomes.csv\n"
    )


# ---------------------------------------------------------------------------
# Exploratory / robustness tables (preregistration amendment; NOT confirmatory)
# ---------------------------------------------------------------------------


def expected_value_table(df: Any, df_raw: Any, output_dir: Path) -> None:
    """Compute unconditional expected value per agent condition (integrative scenarios only).

    Unconditional EV = deal_rate * value_if_deal (no-deal contributes 0).
    Corrects the conditional-on-deal selection bias in value_created.

    Uses one-side-per-dyad (cond_a perspective) to avoid double-counting the
    shared value_created column.  This is an EXPLORATORY/robustness measure —
    preregistration amendment, NOT a confirmatory test.

    Writes: output_dir/expected_value_by_condition.txt
    """
    import pandas as pd

    # Filter integrative dyads, use cond_a-perspective only (one row per dyad)
    integ_raw = df_raw[df_raw["scenario_type"] == "integrative"].copy()
    integ_raw["ev"] = integ_raw.apply(
        lambda r: float(r["value_created"]) if r["deal"] == 1 else 0.0,
        axis=1,
    )

    # Group by cond_a (agent condition for the focal side)
    ev_by_cond = (
        integ_raw.groupby("cond_a")["ev"]
        .agg(mean_ev="mean", n="count", sd_ev="std")
        .reset_index()
        .rename(columns={"cond_a": "agent_type"})
        .sort_values("mean_ev", ascending=False)
    )
    ev_by_cond["mean_ev_rounded"] = ev_by_cond["mean_ev"].round(0).astype(int)

    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / "expected_value_by_condition.txt"

    header_lines = [
        "EXPLORATORY / ROBUSTNESS — preregistration amendment; NOT a confirmatory test.",
        "Unconditional expected value = deal_rate * value_if_deal (no-deal = 0).",
        "Scope: integrative scenarios only; one dyad-side (cond_a) to avoid double-counting.",
        "",
        "Table: Mean Unconditional Expected Value by Agent Condition",
        "(Corrects conditional-on-deal selection bias in value_created)",
        "",
        f"{'Agent condition':<15} {'Mean EV':>10} {'Mean EV (int)':>14} {'SD':>10} {'N dyads':>10}",
        "-" * 65,
    ]
    data_lines = []
    for _, row in ev_by_cond.iterrows():
        sd_str = (
            f"{row['sd_ev']:.1f}"
            if not __import__("math").isnan(row["sd_ev"])
            else "n/a"
        )
        data_lines.append(
            f"{row['agent_type']:<15} {row['mean_ev']:>10.1f} {row['mean_ev_rounded']:>14} {sd_str:>10} {int(row['n']):>10}"
        )
    footer_lines = [
        "",
        "Note: EV = mean(value_created if deal=1, else 0) per condition. No-deal rows contribute 0.",
        "SD and N refer to integrative dyads where the agent held that condition.",
        "Ordering and magnitude differences are descriptive; no hypothesis test conducted.",
    ]

    out_path.write_text("\n".join(header_lines + data_lines + footer_lines) + "\n")
    print(f"  Wrote EV table: {out_path}")


def h6_manipulation_table(df: Any, output_dir: Path) -> None:
    """Compute mean warmth and dominance grouped by agent's own condition (all scenarios).

    This is the H6 manipulation check as a TABLE (figures generated separately).
    An EXPLORATORY/robustness output — preregistration amendment, NOT confirmatory.

    Writes: output_dir/h6_manipulation_by_condition.txt
    """
    import math

    sub = df[["agent_type", "warmth", "dominance"]].copy()
    warmth_avail = sub["warmth"].notna().sum()
    dominance_avail = sub["dominance"].notna().sum()

    if warmth_avail == 0 and dominance_avail == 0:
        print("  [SKIP h6_manipulation_table] No warmth/dominance scores in data.")
        return

    grp = (
        sub.groupby("agent_type")[["warmth", "dominance"]]
        .agg(["mean", "std", "count"])
        .reset_index()
    )
    # Flatten multi-level columns
    grp.columns = ["_".join(c).strip("_") if c[1] else c[0] for c in grp.columns]

    # Sort by warmth_mean descending
    grp = grp.sort_values("warmth_mean", ascending=False)

    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / "h6_manipulation_by_condition.txt"

    header_lines = [
        "EXPLORATORY / ROBUSTNESS — preregistration amendment; NOT a confirmatory test.",
        "H6 agent-level manipulation check: mean warmth and dominance by agent's own condition.",
        "All scenarios where scores exist (warmth/dominance scored by LLM judge on 0-100 scale).",
        "",
        "Table: Mean Warmth and Dominance by Agent Condition (H6 Manipulation Check)",
        "",
        f"{'Agent condition':<15} {'Warmth mean':>13} {'Warmth SD':>11} {'Dom mean':>10} {'Dom SD':>8} {'N agents':>10}",
        "-" * 75,
    ]
    data_lines = []
    for _, row in grp.iterrows():
        w_mean = (
            f"{row['warmth_mean']:.1f}"
            if not math.isnan(row.get("warmth_mean", float("nan")))
            else "n/a"
        )
        w_sd = (
            f"{row['warmth_std']:.1f}"
            if not math.isnan(row.get("warmth_std", float("nan")))
            else "n/a"
        )
        d_mean = (
            f"{row['dominance_mean']:.1f}"
            if not math.isnan(row.get("dominance_mean", float("nan")))
            else "n/a"
        )
        d_sd = (
            f"{row['dominance_std']:.1f}"
            if not math.isnan(row.get("dominance_std", float("nan")))
            else "n/a"
        )
        n = int(row.get("warmth_count", row.get("dominance_count", 0)))
        data_lines.append(
            f"{row['agent_type']:<15} {w_mean:>13} {w_sd:>11} {d_mean:>10} {d_sd:>8} {n:>10}"
        )
    footer_lines = [
        "",
        "Note: Scores from LLM judge (S19 scale); mean across all agent turns in all scenarios.",
        "Expected pattern (H6): WARMTH highest warmth, DOMINANCE highest dominance,",
        "SPEC conditions low on both (spec achieves value without warmth or dominance).",
        "N = rows with non-missing warmth score (same sample used for dominance).",
    ]

    out_path.write_text("\n".join(header_lines + data_lines + footer_lines) + "\n")
    print(f"  Wrote H6 manipulation table: {out_path}")


# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------


def write_table_csv(
    table: Any,
    path: Path,
    caption: str,
) -> None:
    """Write a CSV table with a caption header line."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as f:
        f.write(f"# {caption}\n")
        table.to_csv(f, index=False)
    print(f"  Wrote table: {path}")


def write_contrasts_txt(
    contrasts: list[dict],
    outcome_col: str,
    path: Path,
) -> None:
    """Write a human-readable contrasts table (PAPER_QUALITY_STANDARDS format)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        f"Table: Pre-specified contrasts for outcome '{outcome_col}'",
        f"(PREREGISTRATION §4 contrasts; Welch t-tests; per PAPER_QUALITY_STANDARDS)",
        "",
        f"{'Contrast':<50} {'Mean A':>8} {'Mean B':>8} {'Diff':>8} {'d':>12} {'p':>12} {'n_A':>6} {'n_B':>6}",
        "-" * 110,
    ]
    for c in contrasts:
        m_diff = (
            f"{c['mean_diff']:+.2f}"
            if not __import__("math").isnan(c["mean_diff"])
            else "  n/a"
        )
        m_a = (
            f"{c['mean_a']:.2f}"
            if not __import__("math").isnan(c.get("mean_a", float("nan")))
            else "n/a"
        )
        m_b = (
            f"{c['mean_b']:.2f}"
            if not __import__("math").isnan(c.get("mean_b", float("nan")))
            else "n/a"
        )
        n_a = str(c["n_a"]) if c["n_a"] >= 0 else "n/a"
        n_b = str(c["n_b"]) if c["n_b"] >= 0 else "n/a"
        lines.append(
            f"{c['contrast']:<50} {m_a:>8} {m_b:>8} {m_diff:>8} {c['d_fmt']:>12} {c['p_fmt']:>12} {n_a:>6} {n_b:>6}"
        )
    lines += [
        "",
        "Note: d = Cohen's d (pooled SD); p = exact Welch t-test p-value (3 decimals; floor p < .001).",
        "No significance stars per PAPER_QUALITY_STANDARDS.",
        "Method: " + contrasts[0].get("method", "welch_t") if contrasts else "",
    ]
    path.write_text("\n".join(lines) + "\n")
    print(f"  Wrote contrasts: {path}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main(
    input_path: Path | None = None,
    output_tables: Path | None = None,
    output_figures: Path | None = None,
) -> None:
    tables_dir = output_tables or DEFAULT_OUTPUT_TABLES
    figures_dir = output_figures or DEFAULT_OUTPUT_FIGURES
    tables_dir.mkdir(parents=True, exist_ok=True)
    figures_dir.mkdir(parents=True, exist_ok=True)

    inp = input_path or DEFAULT_INPUT

    # Load data
    df_raw = load_outcomes(inp)
    df = engineer_features(df_raw)

    print(f"\n[analyze] Long-format rows: {len(df)}")
    print(f"  Agent types present: {sorted(df['agent_type'].unique().tolist())}")

    # --- Descriptive statistics table (Table 1) ---
    outcome_cols_for_desc = ["deal", "value_claimed", "value_created"]
    available_outcomes = [c for c in outcome_cols_for_desc if c in df.columns]
    desc = descriptive_table(df, available_outcomes)
    write_table_csv(
        desc,
        tables_dir / "table1_descriptive_by_condition_scenario.csv",
        "Table 1: Descriptive statistics by agent condition and scenario.",
    )

    # --- Pre-specified contrasts (Tables 2, 3, 4) ---
    for outcome_col, h_label in [
        ("deal", "H1_deal_rate"),
        ("value_created", "H3_value_created"),
        ("value_claimed", "H4_value_claimed"),
    ]:
        if outcome_col not in df.columns:
            continue
        sub = df[df[outcome_col].notna() & df["agent_type"].notna()]
        if len(sub) < 10:
            print(f"  [SKIP contrasts] {outcome_col}: too few rows ({len(sub)})")
            continue
        contrasts = extract_contrasts(sub, outcome_col)
        write_contrasts_txt(
            contrasts,
            outcome_col,
            tables_dir / f"contrasts_{h_label}.txt",
        )

    # --- Mixed model (primary H3) ---
    print("\n[analyze] Fitting primary mixed model for value_created (H3)...")
    integrative_df = df[df["scenario_type"] == "integrative"].copy()
    if len(integrative_df.dropna(subset=["value_created"])) >= 10:
        try:
            result, method = fit_mixed_model(
                integrative_df,
                "value_created",
                group_col="opponent_type",
            )
            summary_path = tables_dir / "mixed_model_H3_value_created.txt"
            with summary_path.open("w") as f:
                f.write(f"Model method: {method}\n\n")
                f.write(str(result.summary()))
            print(f"  Mixed model ({method}) summary written to {summary_path}")
        except Exception as e:
            print(f"  [WARN] Mixed model failed: {e}")
    else:
        print(f"  [SKIP] Not enough integrative rows for mixed model.")

    # --- Deal rate mixed model (H1) ---
    print("\n[analyze] Fitting deal rate model (H1)...")
    if len(df.dropna(subset=["deal"])) >= 10:
        try:
            result_deal, method_deal = fit_mixed_model(
                df,
                "deal",
                group_col="opponent_type",
            )
            deal_path = tables_dir / "mixed_model_H1_deal_rate.txt"
            with deal_path.open("w") as f:
                f.write(f"Model method: {method_deal}\n\n")
                f.write(str(result_deal.summary()))
            print(f"  Deal rate model ({method_deal}) written to {deal_path}")
        except Exception as e:
            print(f"  [WARN] Deal rate model failed: {e}")

    # --- Figures ---
    print("\n[analyze] Generating figures...")
    plot_deal_rate_by_condition(
        df,
        figures_dir / "fig1_deal_rate_by_condition.png",
    )

    for outcome_col, title in [
        ("value_created", "H3: Value Created (Joint Points) by Agent Condition"),
        ("value_claimed", "H4: Value Claimed (Own Points vs BATNA) by Agent Condition"),
        ("warmth", "H6: S19 Warmth Score by Agent Condition"),
        ("dominance", "H6: S19 Dominance Score by Agent Condition"),
    ]:
        if outcome_col in df.columns and df[outcome_col].notna().sum() > 0:
            plot_outcomes_by_condition(
                df,
                outcome_col,
                title,
                figures_dir / f"fig_{outcome_col}_by_condition.png",
            )

    # --- Exploratory / robustness tables (preregistration amendment; NOT confirmatory) ---
    print("\n[analyze] Generating exploratory/robustness tables...")
    expected_value_table(df, df_raw, tables_dir)
    h6_manipulation_table(df, tables_dir)

    print(f"\n[analyze] Done. Tables: {tables_dir}  Figures: {figures_dir}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Analyze negotiation experiment outcomes."
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=None,
        help="Path to outcomes.csv (default: data/outcomes.csv)",
    )
    parser.add_argument(
        "--output-tables",
        type=Path,
        default=None,
        help="Directory for output tables (default: output/tables/)",
    )
    parser.add_argument(
        "--output-figures",
        type=Path,
        default=None,
        help="Directory for output figures (default: output/figures/)",
    )
    args = parser.parse_args()
    main(
        input_path=args.input,
        output_tables=args.output_tables,
        output_figures=args.output_figures,
    )
