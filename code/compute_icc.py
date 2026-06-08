"""compute_icc.py — Reproducible ICC(2,1) inter-scorer reliability from JSONL logs.

Reads phase_scoring_wd_gpt4o_* and phase_scoring_wd_haiku_* JSONL logs, aligns
the two scorers per (dyad_id, agent_role), and computes ICC(2,1) for warmth and
dominance (and optionally SVI facets from phase_scoring_svi_* logs).

ICC(2,1): two-way random effects, single rater, absolute agreement.
Formula: (MSR - MSE) / (MSR + (k-1)*MSE + k*(MSC-MSE)/n), k=2.

This script makes this paper's cited ICC values (.863 warmth / .802 dominance)
script-reproducible per PAPER_QUALITY_STANDARDS §37a.

Usage (from repo root):
    uv run python code/compute_icc.py
    uv run python code/compute_icc.py \\
        --logs-dir logs/
    uv run python code/compute_icc.py \\
        --logs-dir logs/ \\
        --phase-filter rescore_v2
    uv run python code/compute_icc.py \\
        --logs-dir logs/ \\
        --include-svi
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from pathlib import Path
from typing import Optional

CODE_DIR = Path(__file__).resolve().parent
EXPERIMENT_DIR = CODE_DIR.parent
DEFAULT_LOGS_DIR = EXPERIMENT_DIR / "logs"

sys.path.insert(0, str(CODE_DIR))

from outcomes import compute_icc_2_1  # noqa: E402

# ---------------------------------------------------------------------------
# JSON fence stripper (haiku emits ```json ... ``` fences)
# ---------------------------------------------------------------------------


def _strip_fences_and_parse(text: str) -> dict:
    """Parse JSON from scorer response, handling ```json ... ``` fences."""
    fence_m = re.search(r"```json\s*(.*?)\s*```", text, re.DOTALL)
    if fence_m:
        text = fence_m.group(1).strip()
    try:
        return json.loads(text.strip())
    except json.JSONDecodeError:
        pass
    m = re.search(r"\{[^{}]+\}", text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group())
        except json.JSONDecodeError:
            pass
    raise ValueError(f"Cannot parse JSON from: {text[:200]!r}")


# ---------------------------------------------------------------------------
# Log file parsers
# ---------------------------------------------------------------------------


def _extract_dyad_role_from_operation(operation: str) -> tuple[str, str]:
    """Extract (dyad_id_suffix, role_hint) from operation field.

    Operation format examples:
      wd_gpt4o_dyad_abc123_buyer  (buyer agent)
      wd_haiku_<dyad_id>_seller   (seller agent)
      svi_gpt4o_<dyad_id>_tenant  (tenant agent)

    Returns (operation_string, "") if parsing fails; caller uses operation as key.
    """
    # The operation field contains the dyad id hash embedded in it.
    # We use the full operation string as the alignment key.
    return operation, ""


def _parse_wd_log(path: Path, scorer_label: str) -> dict[str, dict[str, float]]:
    """Parse a single phase_scoring_wd_* JSONL file.

    Returns dict keyed by operation (which encodes dyad_id + agent_role):
        {"<operation>": {"warmth_score": float, "dominance_score": float}}
    """
    results = {}
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            operation = row.get("operation", "")
            response = row.get("response", "")
            if not response or not operation:
                continue
            try:
                scores = _strip_fences_and_parse(response)
                warmth = float(scores.get("warmth_score", float("nan")))
                dominance = float(scores.get("dominance_score", float("nan")))
                results[operation] = {
                    "warmth_score": warmth,
                    "dominance_score": dominance,
                }
            except (ValueError, KeyError, TypeError):
                pass  # skip unparseable rows
    return results


def _parse_svi_log(path: Path, scorer_label: str) -> dict[str, dict[str, float]]:
    """Parse a single phase_scoring_svi_* JSONL file.

    Returns dict keyed by operation:
        {"<operation>": {"instrumental": float, "self": float, ...}}
    """
    results = {}
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            operation = row.get("operation", "")
            response = row.get("response", "")
            if not response or not operation:
                continue
            try:
                scores = _strip_fences_and_parse(response)
                results[operation] = {
                    k: float(scores[k])
                    for k in ["instrumental", "self", "process", "relationship"]
                    if k in scores
                }
            except (ValueError, KeyError, TypeError):
                pass
    return results


# ---------------------------------------------------------------------------
# Operation-key normalization
# ---------------------------------------------------------------------------


def _normalize_key(operation: str) -> str:
    """Normalize operation string to a scorer-agnostic alignment key.

    Both wd_gpt4o_<dyad>_<role> and wd_haiku_<dyad>_<role> refer to the same
    target; strip the scorer prefix to get the shared key.
    """
    # Remove scorer prefix: wd_gpt4o_ / wd_haiku_ / svi_gpt4o_ / svi_haiku_ /
    # rescore_v2_gpt4o_ / rescore_v2_haiku_
    normalized = re.sub(
        r"^(wd_gpt4o_|wd_haiku_|svi_gpt4o_|svi_haiku_|rescore_v2_gpt4o_|rescore_v2_haiku_)",
        "",
        operation,
    )
    return normalized


# ---------------------------------------------------------------------------
# Main ICC computation
# ---------------------------------------------------------------------------


def compute_interscorer_icc(
    logs_dir: Path,
    phase_filter: Optional[str] = None,
    include_svi: bool = False,
    verbose: bool = True,
) -> dict[str, dict]:
    """Compute ICC(2,1) between gpt-4o and claude-haiku-4-5 scorers.

    Reads phase_scoring_wd_gpt4o_* and phase_scoring_wd_haiku_* JSONL logs,
    aligns per normalized operation key, and computes ICC(2,1) for warmth
    and dominance. Optionally computes ICC for each SVI facet.

    Args:
        logs_dir: directory containing the JSONL log files.
        phase_filter: if set (e.g., "rescore_v2"), only include files whose
            names contain this string.
        include_svi: if True, also compute ICC for SVI facets.
        verbose: print results to stdout.

    Returns:
        dict with keys "warmth", "dominance", and optionally SVI facet names,
        each mapping to the output of compute_icc_2_1().
    """
    logs_dir = Path(logs_dir)
    if not logs_dir.exists():
        raise FileNotFoundError(f"Logs directory not found: {logs_dir}")

    # --- Collect wd log files ---
    def _filter(name: str, tag: str) -> bool:
        if phase_filter and phase_filter not in name:
            return False
        return tag in name

    gpt4o_wd_files = sorted(
        p
        for p in logs_dir.glob("*.jsonl")
        if _filter(p.name, "phase_scoring_wd_gpt4o")
        or _filter(p.name, "rescore_v2_gpt4o")
    )
    haiku_wd_files = sorted(
        p
        for p in logs_dir.glob("*.jsonl")
        if _filter(p.name, "phase_scoring_wd_haiku")
        or _filter(p.name, "rescore_v2_haiku")
    )

    if not gpt4o_wd_files:
        raise FileNotFoundError(
            f"No phase_scoring_wd_gpt4o_* files found in {logs_dir}"
            + (f" matching filter '{phase_filter}'" if phase_filter else "")
        )
    if not haiku_wd_files:
        raise FileNotFoundError(
            f"No phase_scoring_wd_haiku_* files found in {logs_dir}"
            + (f" matching filter '{phase_filter}'" if phase_filter else "")
        )

    # --- Parse all wd logs ---
    gpt4o_scores: dict[str, dict[str, float]] = {}
    for p in gpt4o_wd_files:
        gpt4o_scores.update(_parse_wd_log(p, "gpt4o"))

    haiku_scores: dict[str, dict[str, float]] = {}
    for p in haiku_wd_files:
        haiku_scores.update(_parse_wd_log(p, "haiku"))

    # Normalize keys to scorer-agnostic form
    gpt4o_norm = {_normalize_key(k): v for k, v in gpt4o_scores.items()}
    haiku_norm = {_normalize_key(k): v for k, v in haiku_scores.items()}

    # --- Align by shared key ---
    common_keys = sorted(set(gpt4o_norm) & set(haiku_norm))
    if not common_keys:
        raise ValueError(
            f"No shared operation keys between gpt4o and haiku scorer logs. "
            f"gpt4o keys (sample): {list(gpt4o_norm)[:3]}; "
            f"haiku keys (sample): {list(haiku_norm)[:3]}"
        )

    warmth_gpt4o = [gpt4o_norm[k]["warmth_score"] for k in common_keys]
    warmth_haiku = [haiku_norm[k]["warmth_score"] for k in common_keys]
    dom_gpt4o = [gpt4o_norm[k]["dominance_score"] for k in common_keys]
    dom_haiku = [haiku_norm[k]["dominance_score"] for k in common_keys]

    # Filter out NaN pairs
    def _clean_pair(a_list: list, b_list: list) -> tuple[list, list]:
        clean_a, clean_b = [], []
        for a, b in zip(a_list, b_list):
            if not math.isnan(a) and not math.isnan(b):
                clean_a.append(a)
                clean_b.append(b)
        return clean_a, clean_b

    warmth_g, warmth_h = _clean_pair(warmth_gpt4o, warmth_haiku)
    dom_g, dom_h = _clean_pair(dom_gpt4o, dom_haiku)

    icc_warmth = compute_icc_2_1(warmth_g, warmth_h)
    icc_dominance = compute_icc_2_1(dom_g, dom_h)

    def _pearson_r(a: list, b: list) -> float:
        n = len(a)
        if n < 2:
            return float("nan")
        ma = sum(a) / n
        mb = sum(b) / n
        num = sum((a[i] - ma) * (b[i] - mb) for i in range(n))
        denom = math.sqrt(
            sum((a[i] - ma) ** 2 for i in range(n))
            * sum((b[i] - mb) ** 2 for i in range(n))
        )
        return num / denom if denom > 0 else float("nan")

    r_warmth = _pearson_r(warmth_g, warmth_h)
    r_dom = _pearson_r(dom_g, dom_h)

    results: dict[str, dict] = {
        "warmth": {**icc_warmth, "pearson_r": round(r_warmth, 4)},
        "dominance": {**icc_dominance, "pearson_r": round(r_dom, 4)},
    }

    if verbose:
        print("=" * 60)
        print("INTER-SCORER ICC(2,1) — gpt-4o vs claude-haiku-4-5")
        if phase_filter:
            print(f"Phase filter: {phase_filter}")
        print("=" * 60)
        print(
            f"  WARMTH    ICC(2,1) = {icc_warmth['icc']:.3f}  "
            f"r = {r_warmth:.3f}  "
            f"n = {icc_warmth['n_targets']}"
        )
        print(
            f"  DOMINANCE ICC(2,1) = {icc_dominance['icc']:.3f}  "
            f"r = {r_dom:.3f}  "
            f"n = {icc_dominance['n_targets']}"
        )
        print()
        gate_w = "PASS" if icc_warmth["icc"] >= 0.70 else "FAIL"
        gate_d = "PASS" if icc_dominance["icc"] >= 0.70 else "FAIL"
        print(f"  WARMTH gate    (ICC >= .70): {gate_w}")
        print(f"  DOMINANCE gate (ICC >= .70): {gate_d}")
        print()

    if include_svi:
        gpt4o_svi_files = sorted(
            p
            for p in logs_dir.glob("*.jsonl")
            if _filter(p.name, "phase_scoring_svi_gpt4o")
        )
        haiku_svi_files = sorted(
            p
            for p in logs_dir.glob("*.jsonl")
            if _filter(p.name, "phase_scoring_svi_haiku")
        )
        gpt4o_svi: dict[str, dict] = {}
        for p in gpt4o_svi_files:
            gpt4o_svi.update(_parse_svi_log(p, "gpt4o"))
        haiku_svi: dict[str, dict] = {}
        for p in haiku_svi_files:
            haiku_svi.update(_parse_svi_log(p, "haiku"))

        gpt4o_svi_norm = {_normalize_key(k): v for k, v in gpt4o_svi.items()}
        haiku_svi_norm = {_normalize_key(k): v for k, v in haiku_svi.items()}
        svi_keys = sorted(set(gpt4o_svi_norm) & set(haiku_svi_norm))

        for facet in ["instrumental", "self", "process", "relationship"]:
            g_vals = [gpt4o_svi_norm[k].get(facet, float("nan")) for k in svi_keys]
            h_vals = [haiku_svi_norm[k].get(facet, float("nan")) for k in svi_keys]
            g_clean, h_clean = _clean_pair(g_vals, h_vals)
            if len(g_clean) < 2:
                if verbose:
                    print(f"  SVI {facet}: insufficient data")
                continue
            icc_facet = compute_icc_2_1(g_clean, h_clean)
            r_facet = _pearson_r(g_clean, h_clean)
            results[f"svi_{facet}"] = {**icc_facet, "pearson_r": round(r_facet, 4)}
            if verbose:
                print(
                    f"  SVI {facet:14s} ICC(2,1) = {icc_facet['icc']:.3f}  "
                    f"r = {r_facet:.3f}  "
                    f"n = {icc_facet['n_targets']}"
                )

    return results


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Compute ICC(2,1) inter-scorer reliability from scorer JSONL logs. "
            "Reproduces the pilot-gate ICC values cited in PILOT_GATE_AUDIT.md."
        )
    )
    parser.add_argument(
        "--logs-dir",
        type=Path,
        default=DEFAULT_LOGS_DIR,
        help=f"Directory containing JSONL log files (default: {DEFAULT_LOGS_DIR})",
    )
    parser.add_argument(
        "--phase-filter",
        type=str,
        default=None,
        help=(
            "Only include log files whose names contain this string "
            "(e.g., 'rescore_v2' to reproduce the pilot ICC values). "
            "Default: include all scoring logs."
        ),
    )
    parser.add_argument(
        "--include-svi",
        action="store_true",
        default=False,
        help="Also compute ICC for each SVI facet (requires svi_gpt4o_* + svi_haiku_* logs).",
    )
    args = parser.parse_args()

    try:
        compute_interscorer_icc(
            logs_dir=args.logs_dir,
            phase_filter=args.phase_filter,
            include_svi=args.include_svi,
            verbose=True,
        )
    except (FileNotFoundError, ValueError) as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
