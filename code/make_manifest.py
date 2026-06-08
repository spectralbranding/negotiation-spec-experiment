"""make_manifest.py — Generate DATA_MANIFEST.yaml from run artifacts.

Reads data/outcomes.csv + logs/ + git SHA and emits DATA_MANIFEST.yaml
with: total_dyads, per-condition counts, scenarios, play_models, scorer_models,
total_cost_usd (summed from log cost_usd_est), n_llm_calls, date, git_sha,
prereg_ref.

Run AFTER the experiment completes (not during the live run). The script is
robust to partial data and prints a warning if the run appears incomplete.

Usage (from repo root):
    uv run python code/make_manifest.py
    uv run python code/make_manifest.py \\
        --outcomes data/outcomes.csv \\
        --logs logs/ \\
        --out DATA_MANIFEST.yaml
"""

from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
import warnings
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

EXPERIMENT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_OUTCOMES = EXPERIMENT_DIR / "data" / "outcomes.csv"
DEFAULT_LOGS = EXPERIMENT_DIR / "logs"
DEFAULT_OUT = EXPERIMENT_DIR / "DATA_MANIFEST.yaml"
DEFAULT_PROMPT_HASHES = EXPERIMENT_DIR / "prompts" / "PROMPT_HASHES.txt"

# Target dyad count per MVP design (approx; exact depends on design matrix)
MVP_DYADS_TARGET = (
    450  # 3 scenarios x 6 conditions x 5 replicates x 5 role orders ~ upper bound
)


def _git_sha() -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            cwd=str(EXPERIMENT_DIR),
        )
        return result.stdout.strip() if result.returncode == 0 else "unknown"
    except Exception:
        return "unknown"


def _sum_costs(logs_dir: Path) -> tuple[float, int]:
    """Sum cost_usd_est across all JSONL files in logs_dir.

    Returns (total_cost, n_calls).
    """
    total_cost = 0.0
    n_calls = 0
    for p in sorted(logs_dir.glob("*.jsonl")):
        try:
            with open(p) as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        row = json.loads(line)
                        cost = row.get("cost_usd_est", 0) or 0
                        total_cost += float(cost)
                        n_calls += 1
                    except (json.JSONDecodeError, TypeError, ValueError):
                        pass
        except OSError:
            pass
    return total_cost, n_calls


def _read_outcomes(outcomes_path: Path) -> tuple[int, dict[str, int], list[str]]:
    """Read outcomes.csv and return (total_dyads, per_condition_counts, scenarios).

    Returns (0, {}, []) with a warning if the file does not exist.
    """
    if not outcomes_path.exists():
        warnings.warn(
            f"outcomes.csv not found at {outcomes_path}. "
            "Run is incomplete or path is wrong. "
            "Manifest will have PLACEHOLDER values for dyad counts.",
            stacklevel=2,
        )
        return 0, {}, []

    try:
        with open(outcomes_path, newline="") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
    except Exception as e:
        warnings.warn(f"Could not read outcomes.csv: {e}", stacklevel=2)
        return 0, {}, []

    total = len(rows)
    cond_counts: Counter = Counter()
    scenarios_seen: set = set()
    for row in rows:
        for side in ("a", "b"):
            cond = row.get(f"cond_{side}", "")
            if cond:
                cond_counts[cond] += 1
        scen = row.get("scenario_id", "")
        if scen:
            scenarios_seen.add(scen)

    return total, dict(cond_counts), sorted(scenarios_seen)


def _read_prompt_hashes_sha(prompt_hashes_path: Path) -> str:
    """Read the combined hash line from PROMPT_HASHES.txt."""
    if not prompt_hashes_path.exists():
        return "MISSING — run prompts/hash_prompts.py"
    try:
        text = prompt_hashes_path.read_text()
        for line in text.splitlines():
            if line.strip().startswith("COMBINED"):
                # Extract the hash after ": "
                parts = line.split(":")
                if len(parts) >= 2:
                    return parts[-1].strip()
    except Exception:
        pass
    return "ERROR reading PROMPT_HASHES.txt"


def _format_yaml_value(v: object) -> str:
    """Format a Python value as a YAML scalar (minimal, no quotes unless needed)."""
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return str(v)
    if v is None:
        return "null"
    s = str(v)
    # Quote if contains special YAML characters
    if any(
        c in s
        for c in (
            ":",
            "#",
            "{",
            "}",
            "[",
            "]",
            ",",
            "&",
            "*",
            "?",
            "|",
            "-",
            "<",
            ">",
            "=",
            "!",
            "%",
            "@",
            "`",
            '"',
            "'",
        )
    ):
        return f'"{s}"'
    return s


def generate_manifest(
    outcomes_path: Path,
    logs_dir: Path,
    prompt_hashes_path: Path,
    out_path: Path,
) -> None:
    """Generate DATA_MANIFEST.yaml from run artifacts."""
    now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    sha = _git_sha()

    total_dyads, per_condition, scenarios = _read_outcomes(outcomes_path)
    total_cost, n_calls = _sum_costs(logs_dir)
    prompt_hashes_combined = _read_prompt_hashes_sha(prompt_hashes_path)

    # Completeness check
    is_partial = total_dyads < MVP_DYADS_TARGET or n_calls == 0
    if is_partial:
        print(
            f"WARNING: Run appears incomplete. "
            f"total_dyads={total_dyads} (target ~{MVP_DYADS_TARGET}), "
            f"n_calls={n_calls}. "
            "Manifest will reflect partial run state.",
            file=sys.stderr,
        )

    content = f"""# DATA_MANIFEST.yaml — machine-readable data inventory
# Spec-Agent vs Styled-Agent in AI-AI Negotiation experiment.
#
# Generated by code/make_manifest.py on {now_utc}.
# Regenerate with:
#   uv run python code/make_manifest.py

# --- Provenance ---
created_at: "{now_utc}"
git_sha: "{sha}"
{"partial_run: true  # WARNING: run was incomplete at manifest generation time" if is_partial else ""}

# --- Experimental design (FIXED) ---
model_primary: "gpt-4o-mini-2024-07-18"
model_robustness: "claude-haiku-4-5"
temperature_play: 0.20
scenarios: {json.dumps(scenarios if scenarios else ["chair", "rental", "offer"])}
conditions:
  - NEUTRAL
  - WARMTH
  - DOMINANCE
  - COT_ONLY
  - SPEC_NOCOT
  - SPEC_COT
replicates_per_cell_target: 5
budget_stop_usd: 38.0

# --- Data locations (relative to experiment root) ---
transcript_dir: "data/transcripts/"
outcomes_file: "data/outcomes.csv"
logs_dir: "logs/"
prompt_hashes_file: "prompts/PROMPT_HASHES.txt"
preregistration_file: "PREREGISTRATION.md"
pilot_gate_audit_file: "PILOT_GATE_AUDIT.md"

# --- Scoring models (FIXED) ---
scoring_models:
  warmth_dominance:
    - "gpt-4o-2024-08-06"
    - "claude-haiku-4-5"
  svi:
    - "gpt-4o-2024-08-06"
    - "claude-haiku-4-5"
inter_scorer_icc:
  warmth: 0.863   # pilot gate (rescore_v2 pass, 20 dyads)
  dominance: 0.802  # pilot gate (rescore_v2 pass, 20 dyads)
  gate_threshold: 0.70
  script: "code/compute_icc.py"

# --- Run summary ---
total_dyads_completed: {total_dyads}
total_dyads_target: {MVP_DYADS_TARGET}
per_condition_counts: {json.dumps(per_condition) if per_condition else "{}"}
n_llm_calls: {n_calls}
total_cost_usd_est: {round(total_cost, 4)}

# --- Integrity ---
prompt_hashes_sha256_combined: "{prompt_hashes_combined}"
prereg_ref: "PREREGISTRATION.md"

# --- Publication ---
zenodo_concept_doi: "PLACEHOLDER — minted at paper-draft/submission stage"
zenodo_version_doi: "PLACEHOLDER — minted at Zenodo upload"
hf_dataset_url: "PLACEHOLDER — spectralbranding/negotiation-spec-transcripts"
"""

    out_path.write_text(content.lstrip())
    print(f"Wrote DATA_MANIFEST.yaml to {out_path}")
    print(f"  total_dyads_completed: {total_dyads}")
    print(f"  n_llm_calls: {n_calls}")
    print(f"  total_cost_usd_est: ${total_cost:.4f}")
    if is_partial:
        print("  WARNING: partial run — rerun after experiment completes.")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate DATA_MANIFEST.yaml from experiment run artifacts."
    )
    parser.add_argument(
        "--outcomes",
        type=Path,
        default=DEFAULT_OUTCOMES,
        help=f"Path to outcomes.csv (default: {DEFAULT_OUTCOMES})",
    )
    parser.add_argument(
        "--logs",
        type=Path,
        default=DEFAULT_LOGS,
        help=f"Logs directory (default: {DEFAULT_LOGS})",
    )
    parser.add_argument(
        "--prompt-hashes",
        type=Path,
        default=DEFAULT_PROMPT_HASHES,
        help=f"Path to PROMPT_HASHES.txt (default: {DEFAULT_PROMPT_HASHES})",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=DEFAULT_OUT,
        help=f"Output path for DATA_MANIFEST.yaml (default: {DEFAULT_OUT})",
    )
    args = parser.parse_args()
    generate_manifest(
        outcomes_path=args.outcomes,
        logs_dir=args.logs,
        prompt_hashes_path=args.prompt_hashes,
        out_path=args.out,
    )


if __name__ == "__main__":
    main()
