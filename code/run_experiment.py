"""run_experiment.py — orchestrator for the Spec-Agent vs Styled-Agent experiment.

Enumerates the full experimental grid and runs negotiations.

Grid:
    6 conditions x round-robin pairs (incl. self-play) x 3 scenarios x 2 role-orders
    x R replicates

Condition pairs (round-robin, incl. self):
    NEUTRAL vs NEUTRAL, NEUTRAL vs WARMTH, NEUTRAL vs DOMINANCE, NEUTRAL vs COT_ONLY,
    NEUTRAL vs SPEC_NOCOT, NEUTRAL vs SPEC_COT,
    WARMTH vs WARMTH, WARMTH vs DOMINANCE, ... etc.
    = 6*(6+1)/2 = 21 unique unordered pairs

Role-orders: 2 per pair (A plays role_a, B plays role_b; then swap)

Total cells: 21 pairs x 3 scenarios x 2 role-orders = 126 cells
With R=5 replicates: 630 negotiations (the pilot uses --pilot N to cap this)

Flags:
    --pilot N              cap to ~N negotiations, balanced across cells
    --dry-run              mock=True everywhere, zero API, writes to dryrun/
    --preflight            issue 1-token test calls to each required model; report
                           OK/NEEDS_DEPOSIT/AUTH/ERROR; exit non-zero if any blocked
    --model M              override primary model (default: gpt-4o-mini)
    --resume               skip dyads already on disk (verify-on-disk, idempotent)
    --replicates R         number of replicates per cell (default 5)
    --budget-stop B        abort when summed cost_usd_est >= B (default 38 USD)
    --temp T               sampling temperature (default 0.20)
    --score                also run warmth/dominance + SVI scoring after each dyad
    --data-dir PATH        override output root (transcripts/, outcomes.csv, run logs).
                           Default: data/ for live runs, dryrun/ for --dry-run.
                           Use to isolate per-model arms, e.g. --data-dir data_haiku.
    --logs-dir PATH        override JSONL logs directory.
                           Default: logs/ for live runs, dryrun/logs for --dry-run.
    --scenarios-dir PATH   override scenarios directory (default: scenarios/).
                           Use scenarios_study2/ for Study 2.
    --scenario-ids IDS     comma-separated scenario ids (default: chair,rental,offer).
                           Role pairs are read from each YAML's roles list.
                           Example: --scenario-ids merger,supplier,salvage
    --conditions IDS       comma-separated condition ids (default: all 6 CONDITIONS).
                           Each id must match an existing prompts/<ID>.txt file.
                           Example: --conditions NEUTRAL,COT_ONLY,SPEC_NOCOT,SPEC_NOLOGROLL
    --opponent COND        fix a single opponent condition (default: full round-robin).
                           When set, every condition in --conditions is paired ONLY against
                           COND (both role orders), instead of a round-robin.
                           Dyad count = len(conditions) × S scenarios × 2 orders × R reps.
                           Example: --opponent NEUTRAL

Usage (dry-run, zero API):
    uv run python code/run_experiment.py \\
        --dry-run --pilot 60

Usage (isolated dry-run for a second model arm):
    uv run python code/run_experiment.py \\
        --dry-run --pilot 30 --data-dir dryrun_iso

Usage (preflight check, real API):
    uv run python code/run_experiment.py \\
        --preflight --model gpt-4o-mini

Usage (pilot, real API):
    uv run python code/run_experiment.py \\
        --pilot 60 --model gpt-4o-mini

Usage (haiku robustness arm, isolated output dir):
    uv run python code/run_experiment.py \\
        --model claude-haiku-4-5 --score --data-dir data_haiku --budget-stop 38
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import itertools
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

import yaml

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------
EXPERIMENT_DIR = Path(__file__).resolve().parents[1]
_DEFAULT_SCENARIOS_DIR = EXPERIMENT_DIR / "scenarios"
SCENARIOS_DIR = (
    _DEFAULT_SCENARIOS_DIR  # kept for backward-compat; overridden at runtime
)
REPO_ROOT = Path(__file__).resolve().parents[3]
RESEARCH_CODE = REPO_ROOT / "research" / "code"
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(RESEARCH_CODE))

from provider_errors import (  # noqa: E402
    classify_provider_error,
    call_with_retry,
    handle_provider_block,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
CONDITIONS = ["NEUTRAL", "WARMTH", "DOMINANCE", "COT_ONLY", "SPEC_NOCOT", "SPEC_COT"]
_DEFAULT_SCENARIO_IDS = ["chair", "rental", "offer"]
SCENARIO_IDS = _DEFAULT_SCENARIO_IDS  # kept for backward-compat; overridden at runtime
# Fallback role pairs for Study 1 scenarios (used when YAML lacks a roles list).
SCENARIO_ROLES = {
    "chair": ("buyer", "seller"),
    "rental": ("tenant", "landlord"),
    "offer": ("candidate", "recruiter"),
}
DEFAULT_MODEL = "gpt-4o-mini"
DEFAULT_TEMPERATURE = 0.20
DEFAULT_REPLICATES = 5
BUDGET_STOP_DEFAULT = 38.0
COST_PRINT_EVERY = 10  # print cost line every N dyads


# ---------------------------------------------------------------------------
# Scenario loading
# ---------------------------------------------------------------------------
_SCENARIO_CACHE: dict[str, dict] = {}


def load_scenario(scenario_id: str, scenarios_dir: Path | None = None) -> dict:
    """Load and cache a scenario YAML.

    *scenarios_dir* overrides the module-level SCENARIOS_DIR.  When called
    from the grid runner the resolved dir is passed explicitly so that Study 2
    (or any custom dir) works without mutating module state.
    """
    sdir = scenarios_dir if scenarios_dir is not None else SCENARIOS_DIR
    cache_key = f"{sdir}::{scenario_id}"
    if cache_key in _SCENARIO_CACHE:
        return _SCENARIO_CACHE[cache_key]
    path = sdir / f"{scenario_id}.yaml"
    if not path.exists():
        raise FileNotFoundError(f"Scenario file not found: {path}")
    with path.open() as f:
        data = yaml.safe_load(f)
    _SCENARIO_CACHE[cache_key] = data
    return data


def _extract_roles_from_yaml(scenario: dict, scenario_id: str) -> tuple[str, str]:
    """Return (role_a, role_b) by reading the YAML roles list.

    Prefers the YAML ``roles`` list (works for any scenario set).
    Falls back to the hard-coded SCENARIO_ROLES dict for Study 1 ids so that
    existing behavior is unchanged even if the YAML is missing a roles list.
    """
    roles_list = scenario.get("roles", [])
    if len(roles_list) >= 2:
        return (roles_list[0]["id"], roles_list[1]["id"])
    # Fallback: Study 1 hard-coded dict
    if scenario_id in SCENARIO_ROLES:
        return SCENARIO_ROLES[scenario_id]
    raise ValueError(
        f"Cannot determine roles for scenario '{scenario_id}': "
        "YAML has fewer than 2 roles entries and id is not in SCENARIO_ROLES fallback."
    )


# ---------------------------------------------------------------------------
# Grid enumeration
# ---------------------------------------------------------------------------


def _all_condition_pairs(
    conditions: list[str] | None = None,
) -> list[tuple[str, str]]:
    """All unordered condition pairs (including self-play) for *conditions*.

    When *conditions* is None the module-level ``CONDITIONS`` list is used
    (default 6-condition full grid, backward-compatible).
    """
    clist = conditions if conditions is not None else CONDITIONS
    pairs = []
    for i, c1 in enumerate(clist):
        for c2 in clist[i:]:
            pairs.append((c1, c2))
    return pairs  # len = N*(N+1)/2


def _focal_opponent_pairs(
    focal_conditions: list[str],
    opponent: str,
) -> list[tuple[str, str]]:
    """Return (focal, opponent) pairs for the focal × fixed-opponent design.

    Every condition in *focal_conditions* is paired ONLY against *opponent*
    (both role orders are still generated at grid-build time).  Self-play
    (focal == opponent) is included if opponent is in focal_conditions, so
    that the opponent arm is always the same backboard.

    Dyad count = len(focal_conditions) × n_scenarios × 2 role_orders × R
    (i.e. NOT a round-robin — exactly len(focal_conditions) pairs).
    """
    return [(fc, opponent) for fc in focal_conditions]


def build_grid(
    replicates: int = DEFAULT_REPLICATES,
    scenario_ids: list[str] | None = None,
    scenarios_dir: Path | None = None,
    conditions: list[str] | None = None,
    opponent: str | None = None,
) -> list[dict]:
    """Build the full experimental grid as a list of dyad spec dicts.

    Each entry has all info needed to run and identify one dyad.
    Sorted deterministically so --resume always processes in same order.

    *scenario_ids* overrides the module-level SCENARIO_IDS list.
    *scenarios_dir* overrides the module-level SCENARIOS_DIR path; role pairs
    are read directly from each scenario's YAML ``roles`` list.
    *conditions* overrides the module-level CONDITIONS list (additive — does not
    change any other behavior; when None the default 6-condition list is used).
    *opponent* pins a fixed opponent for the focal-vs-fixed-opponent design:
    every condition in *conditions* is paired ONLY against *opponent* (both role
    orders), instead of a full round-robin.  When None the full round-robin is
    used (default behavior, unchanged).

    Dyad-count formula:
      - Default (no flags):      N*(N+1)/2 pairs × S scenarios × 2 orders × R
      - --conditions subset:     M*(M+1)/2 pairs × S scenarios × 2 orders × R
      - --opponent COND:         M pairs        × S scenarios × 2 orders × R
        where M = len(conditions).
    """
    ids = scenario_ids if scenario_ids is not None else SCENARIO_IDS
    clist = conditions if conditions is not None else CONDITIONS
    grid = []

    if opponent is not None:
        condition_pairs = _focal_opponent_pairs(clist, opponent)
    else:
        condition_pairs = _all_condition_pairs(clist)

    for scenario_id in ids:
        scenario = load_scenario(scenario_id, scenarios_dir=scenarios_dir)
        role_a_default, role_b_default = _extract_roles_from_yaml(scenario, scenario_id)
        for cond_a, cond_b in condition_pairs:
            # Two role-orders: (A=role_a, B=role_b) and (A=role_b, B=role_a)
            role_orders = [
                (role_a_default, role_b_default),
                (role_b_default, role_a_default),
            ]
            for role_a, role_b in role_orders:
                for rep in range(replicates):
                    dyad_id = _make_dyad_id(
                        scenario_id, cond_a, cond_b, role_a, role_b, rep
                    )
                    grid.append(
                        {
                            "dyad_id": dyad_id,
                            "scenario_id": scenario_id,
                            "cond_a": cond_a,
                            "cond_b": cond_b,
                            "role_a": role_a,
                            "role_b": role_b,
                            "replicate": rep,
                        }
                    )
    return grid


def _make_dyad_id(
    scenario_id: str,
    cond_a: str,
    cond_b: str,
    role_a: str,
    role_b: str,
    rep: int,
) -> str:
    """Create a deterministic, unique dyad_id string."""
    raw = f"{scenario_id}__{cond_a}__{cond_b}__{role_a}__{role_b}__r{rep:02d}"
    # Shorten with hash suffix to keep filenames manageable
    h = hashlib.md5(raw.encode()).hexdigest()[:6]
    short = f"{scenario_id}_{cond_a[:3]}_{cond_b[:3]}_{role_a[:3]}_{role_b[:3]}_r{rep:02d}_{h}"
    return short


def _pilot_sample(grid: list[dict], n: int) -> list[dict]:
    """Sample ~n dyads from the grid, balanced across cells.

    Strategy: take ceil(n / len(grid)) fraction of each cell, then truncate.
    Simpler: take every kth element where k = len(grid) // n.
    """
    if n >= len(grid):
        return grid
    # Systematic sample: take every k-th element for uniform coverage
    step = max(1, len(grid) // n)
    sampled = grid[::step]
    return sampled[:n]


# ---------------------------------------------------------------------------
# Output paths
# ---------------------------------------------------------------------------


def get_data_dir(dry_run: bool, data_dir_override: str | None = None) -> Path:
    """Return the transcripts directory.

    If *data_dir_override* is set it is resolved relative to EXPERIMENT_DIR and
    used as the root; transcripts land in <root>/transcripts/.
    Otherwise fall back to the historical defaults:
      live  → data/transcripts/
      dry   → dryrun/transcripts/
    """
    if data_dir_override is not None:
        root = Path(data_dir_override)
        if not root.is_absolute():
            root = EXPERIMENT_DIR / root
        return root / "transcripts"
    if dry_run:
        return EXPERIMENT_DIR / "dryrun" / "transcripts"
    return EXPERIMENT_DIR / "data" / "transcripts"


def get_outcomes_path(dry_run: bool, data_dir_override: str | None = None) -> Path:
    """Return the outcomes CSV path (sibling of the transcripts directory)."""
    if data_dir_override is not None:
        root = Path(data_dir_override)
        if not root.is_absolute():
            root = EXPERIMENT_DIR / root
        return root / "outcomes.csv"
    if dry_run:
        return EXPERIMENT_DIR / "dryrun" / "outcomes.csv"
    return EXPERIMENT_DIR / "data" / "outcomes.csv"


def get_logs_dir(dry_run: bool, logs_dir_override: str | None = None) -> Path:
    """Return the JSONL logs directory.

    If *logs_dir_override* is set it is resolved relative to EXPERIMENT_DIR.
    Otherwise fall back to:
      live  → logs/
      dry   → dryrun/logs/
    """
    if logs_dir_override is not None:
        p = Path(logs_dir_override)
        if not p.is_absolute():
            p = EXPERIMENT_DIR / p
        return p
    if dry_run:
        return EXPERIMENT_DIR / "dryrun" / "logs"
    return EXPERIMENT_DIR / "logs"


# ---------------------------------------------------------------------------
# Transcript I/O
# ---------------------------------------------------------------------------


def transcript_path(dyad_id: str, data_dir: Path) -> Path:
    return data_dir / f"{dyad_id}.json"


def transcript_exists(dyad_id: str, data_dir: Path) -> bool:
    """Return True only if a fully-written transcript (.json) exists.

    A stray .tmp file (left by a killed mid-write) does NOT count — only the
    final .json after os.replace() succeeds is considered complete.
    """
    p = transcript_path(dyad_id, data_dir)
    return p.exists() and p.stat().st_size > 0


def write_transcript(transcript: dict, data_dir: Path) -> None:
    """Atomically write transcript JSON (tmp then os.replace to avoid half-files)."""
    data_dir.mkdir(parents=True, exist_ok=True)
    p = transcript_path(transcript["dyad_id"], data_dir)
    tmp = p.with_suffix(".tmp")
    with tmp.open("w") as f:
        json.dump(transcript, f, indent=2)
    os.replace(tmp, p)


def read_transcript(dyad_id: str, data_dir: Path) -> dict:
    p = transcript_path(dyad_id, data_dir)
    with p.open() as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Outcomes CSV
# ---------------------------------------------------------------------------

OUTCOMES_FIELDNAMES = [
    "dyad_id",
    "scenario_id",
    "scenario_type",
    "cond_a",
    "cond_b",
    "role_a",
    "role_b",
    "replicate",
    "model_a",
    "model_b",
    "deal",
    "deal_terms_json",
    "rounds_to_deal",
    "value_claimed_a",
    "value_claimed_b",
    "points_a",
    "points_b",
    "value_created",
    "split",
    "warmth_a_mean",
    "dominance_a_mean",
    "warmth_b_mean",
    "dominance_b_mean",
    "svi_a_mean",
    "svi_b_mean",
    "cost_usd_est",
    "notes",
    "mock",
]


def write_outcomes_row(row: dict, outcomes_path: Path) -> None:
    """Append one outcomes row to the CSV.

    The CSV is append-only so a tmp/replace strategy is not used here; instead
    we flush immediately so partial rows are never left on disk (append is
    atomic at the OS level for short writes).
    """
    outcomes_path.parent.mkdir(parents=True, exist_ok=True)
    write_header = not outcomes_path.exists()
    with outcomes_path.open("a", newline="") as f:
        writer = csv.DictWriter(
            f, fieldnames=OUTCOMES_FIELDNAMES, extrasaction="ignore"
        )
        if write_header:
            writer.writeheader()
        writer.writerow(row)
        f.flush()


def outcome_row_exists(dyad_id: str, outcomes_path: Path) -> bool:
    """Check if an outcomes row already exists for this dyad_id."""
    if not outcomes_path.exists():
        return False
    with outcomes_path.open() as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get("dyad_id") == dyad_id:
                return True
    return False


# ---------------------------------------------------------------------------
# Cost tracking
# ---------------------------------------------------------------------------


def _extract_cost_from_logs(logs_dir: Path, dyad_id: str) -> float:
    """Sum cost_usd_est from all JSONL log rows mentioning dyad_id."""
    total = 0.0
    if not logs_dir.exists():
        return total
    for f in logs_dir.glob("*.jsonl"):
        try:
            with f.open() as fh:
                for line in fh:
                    row = json.loads(line)
                    if dyad_id in row.get("operation", ""):
                        total += float(row.get("cost_usd_est", 0.0))
        except (json.JSONDecodeError, OSError):
            pass
    return total


# ---------------------------------------------------------------------------
# Resume command builder
# ---------------------------------------------------------------------------


def _make_resume_cmd(args: argparse.Namespace) -> str:
    """Reconstruct the CLI command with --resume appended."""
    parts = [
        "uv run python",
        "code/run_experiment.py",
        "--resume",
    ]
    if args.dry_run:
        parts.append("--dry-run")
    if args.pilot is not None:
        parts += ["--pilot", str(args.pilot)]
    if args.model != DEFAULT_MODEL:
        parts += ["--model", args.model]
    if args.replicates != DEFAULT_REPLICATES:
        parts += ["--replicates", str(args.replicates)]
    if args.budget_stop != BUDGET_STOP_DEFAULT:
        parts += ["--budget-stop", str(args.budget_stop)]
    if args.temp != DEFAULT_TEMPERATURE:
        parts += ["--temp", str(args.temp)]
    if args.score:
        parts.append("--score")
    if args.data_dir is not None:
        parts += ["--data-dir", args.data_dir]
    if args.logs_dir is not None:
        parts += ["--logs-dir", args.logs_dir]
    if args.scenarios_dir is not None:
        parts += ["--scenarios-dir", args.scenarios_dir]
    if args.scenario_ids is not None:
        parts += ["--scenario-ids", args.scenario_ids]
    if args.conditions is not None:
        parts += ["--conditions", args.conditions]
    if args.opponent is not None:
        parts += ["--opponent", args.opponent]
    return " ".join(parts)


# ---------------------------------------------------------------------------
# Preflight check
# ---------------------------------------------------------------------------

# Scorer models used when --score is active
SCORER_MODELS_LIVE = ["gpt-4o", "claude-haiku-4-5"]


def _preflight_call_openai(model: str) -> None:
    """Issue a 1-token call to OpenAI to verify credentials and balance."""
    import openai

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY not set in environment.")
    client = openai.OpenAI(api_key=api_key)
    client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": "hi"}],
        max_tokens=1,
    )


def _preflight_call_grok(model: str) -> None:
    """Issue a 1-token call to xAI Grok (OpenAI-compatible endpoint) to verify
    credentials and reachability.

    Uses the same OpenAI SDK with ``base_url`` overridden to ``api.x.ai/v1``
    and ``GROK_API_KEY`` read from the environment.
    """
    import openai

    from negotiation_runner import GROK_BASE_URL

    api_key = os.environ.get("GROK_API_KEY")
    if not api_key:
        raise RuntimeError("GROK_API_KEY not set in environment.")
    client = openai.OpenAI(api_key=api_key, base_url=GROK_BASE_URL)
    client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": "hi"}],
        max_tokens=1,
    )


def _preflight_call_anthropic(model: str) -> None:
    """Issue a 1-token call to Anthropic to verify credentials and balance."""
    import anthropic

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY not set in environment.")
    client = anthropic.Anthropic(api_key=api_key)
    client.messages.create(
        model=model,
        messages=[{"role": "user", "content": "hi"}],
        max_tokens=1,
    )


def run_preflight(args: argparse.Namespace) -> int:
    """Run preflight checks for all models in scope.

    In dry-run mode: always reports OK without any API call.
    Returns 0 if all OK, 1 if any model is blocked.
    """
    from negotiation_runner import OPENAI_MODELS, ANTHROPIC_MODELS, GROK_MODELS

    if args.dry_run:
        # Dry-run: mock path — no real calls
        models_to_check = [args.model]
        if args.score:
            models_to_check += SCORER_MODELS_LIVE
        models_to_check = list(dict.fromkeys(models_to_check))  # deduplicate

        print("\n[preflight] DRY-RUN mode — mock path, no API calls")
        print(f"{'Model':<30}  Status")
        print("-" * 42)
        for m in models_to_check:
            print(f"  {m:<28}  OK (mock)")
        print()
        return 0

    # Live preflight
    models_to_check = [args.model]
    if args.score:
        models_to_check += SCORER_MODELS_LIVE
    models_to_check = list(dict.fromkeys(models_to_check))

    results: dict[str, str] = {}
    any_blocked = False

    print("\n[preflight] Checking model access (1-token calls)...")
    for model in models_to_check:
        try:
            if model in GROK_MODELS or model.startswith("grok"):
                call_with_retry(_preflight_call_grok, model)
            elif model in OPENAI_MODELS or model.startswith("gpt-"):
                call_with_retry(_preflight_call_openai, model)
            elif model in ANTHROPIC_MODELS or model.startswith("claude-"):
                call_with_retry(_preflight_call_anthropic, model)
            else:
                results[model] = "UNKNOWN_PROVIDER"
                any_blocked = True
                continue
            results[model] = "OK"
        except Exception as exc:
            info = classify_provider_error(exc)
            status = info["kind"].upper()
            results[model] = status
            if info["kind"] != "transient":
                any_blocked = True

    print(f"\n{'Model':<30}  Status")
    print("-" * 42)
    for model, status in results.items():
        marker = "  " if status == "OK" else "* "
        print(f"  {marker}{model:<26}  {status}")
    print()

    if any_blocked:
        blocked = [m for m, s in results.items() if s != "OK"]
        data_dir = get_data_dir(dry_run=False, data_dir_override=args.data_dir)
        resume_cmd = _make_resume_cmd(args)
        # Write RUN_STATUS.md for the first blocked provider
        first_model = blocked[0]
        kind_lower = results[first_model].lower()
        if first_model in GROK_MODELS or first_model.startswith("grok"):
            provider = "xai"
        elif first_model in OPENAI_MODELS or first_model.startswith("gpt-"):
            provider = "openai"
        else:
            provider = "anthropic"
        handle_provider_block(
            info={
                "kind": kind_lower,
                "provider": provider,
                "summary": "preflight check failed",
            },
            data_dir=data_dir,
            dyads_done=0,
            dyads_remaining=-1,
            cost_so_far=0.0,
            resume_cmd=resume_cmd,
        )
        print(
            f"[preflight] FAILED: {len(blocked)} model(s) blocked: {blocked}",
            file=sys.stderr,
        )
        return 1

    print("[preflight] All models OK.")
    return 0


# ---------------------------------------------------------------------------
# Main run loop
# ---------------------------------------------------------------------------


def run_grid(args: argparse.Namespace) -> None:
    from negotiation_runner import run_dyad
    from outcomes import compute_outcome
    from scoring_llm import (
        score_warmth_dominance,
        score_svi,
        compute_mean_across_scorers,  # noqa: F401 (imported for callers)
    )

    dry_run = args.dry_run
    mock = dry_run  # dry-run always uses mock
    model = args.model
    temperature = args.temp
    replicates = args.replicates
    budget_stop = args.budget_stop
    do_score = args.score or dry_run  # always score in dry-run to test the path
    pilot_n = args.pilot

    data_dir = get_data_dir(dry_run, data_dir_override=args.data_dir)
    outcomes_path = get_outcomes_path(dry_run, data_dir_override=args.data_dir)
    logs_dir = get_logs_dir(dry_run, logs_dir_override=args.logs_dir)

    data_dir.mkdir(parents=True, exist_ok=True)
    logs_dir.mkdir(parents=True, exist_ok=True)

    # Build resume command once (used in provider-block alerts)
    resume_cmd = _make_resume_cmd(args)

    # Resolve scenarios dir and ids from args
    resolved_scenarios_dir: Path | None = None
    if args.scenarios_dir is not None:
        p = Path(args.scenarios_dir)
        resolved_scenarios_dir = p if p.is_absolute() else EXPERIMENT_DIR / p
    resolved_scenario_ids: list[str] | None = None
    if args.scenario_ids is not None:
        resolved_scenario_ids = [
            s.strip() for s in args.scenario_ids.split(",") if s.strip()
        ]

    # Resolve conditions subset from --conditions flag
    resolved_conditions: list[str] | None = None
    if args.conditions is not None:
        resolved_conditions = [
            c.strip() for c in args.conditions.split(",") if c.strip()
        ]
        # Validate: each id must be a known default condition OR have a prompts file
        for cid in resolved_conditions:
            if cid not in CONDITIONS:
                prompt_path = EXPERIMENT_DIR / "prompts" / f"{cid}.txt"
                if not prompt_path.exists():
                    raise ValueError(
                        f"--conditions: unknown condition id '{cid}' — "
                        f"not in CONDITIONS and no prompts/{cid}.txt found."
                    )

    # Resolve --opponent flag
    resolved_opponent: str | None = None
    if args.opponent is not None:
        resolved_opponent = args.opponent.strip()
        # Validate opponent id
        if resolved_opponent not in CONDITIONS:
            prompt_path = EXPERIMENT_DIR / "prompts" / f"{resolved_opponent}.txt"
            if not prompt_path.exists():
                raise ValueError(
                    f"--opponent: unknown condition id '{resolved_opponent}' — "
                    f"not in CONDITIONS and no prompts/{resolved_opponent}.txt found."
                )

    # Build grid
    full_grid = build_grid(
        replicates=replicates,
        scenario_ids=resolved_scenario_ids,
        scenarios_dir=resolved_scenarios_dir,
        conditions=resolved_conditions,
        opponent=resolved_opponent,
    )
    if pilot_n is not None:
        grid = _pilot_sample(full_grid, pilot_n)
        print(
            f"[run_experiment] PILOT mode: {len(grid)} dyads sampled from "
            f"{len(full_grid)} total (--pilot {pilot_n})"
        )
    else:
        grid = full_grid
        print(f"[run_experiment] FULL GRID: {len(grid)} dyads")

    if dry_run:
        print(
            f"[run_experiment] DRY-RUN: mock=True, zero API calls, "
            f"writing to {data_dir.parent}/"
        )
    if args.resume:
        print("[run_experiment] RESUME: skipping already-completed dyads")

    cumulative_cost = 0.0
    completed = 0
    skipped = 0
    failed = 0
    start_time = time.time()

    # Provider-pause tracking: set of provider strings that are BLOCKED
    blocked_providers: set[str] = set()

    def _provider_of(m: str) -> str:
        if m.startswith("grok"):
            return "xai"
        if m.startswith("gpt-") or m in {"gpt-4o-mini", "gpt-4o", "gpt-4o-2024-11-20"}:
            return "openai"
        if m.startswith("claude-"):
            return "anthropic"
        return "unknown"

    def _all_needed_blocked() -> bool:
        """Return True when every provider needed for remaining work is blocked."""
        providers_needed: set[str] = set()
        for spec in grid[completed + skipped :]:
            p = _provider_of(spec.get("model_a", model) or model)
            providers_needed.add(p)
        # Scorer providers (if scoring)
        if do_score and not mock:
            providers_needed.add("openai")  # gpt-4o scorer
            providers_needed.add("anthropic")  # claude-haiku-4-5 scorer
        return bool(providers_needed) and providers_needed.issubset(blocked_providers)

    def _handle_block(exc: Exception, context: str) -> None:
        """Classify exc, mark provider blocked, emit alerts."""
        info = classify_provider_error(exc)
        prov = info.get("provider", "unknown")
        kind = info.get("kind", "unknown")
        if not info.get("transient", False) and prov not in blocked_providers:
            blocked_providers.add(prov)
            remaining = max(0, len(grid) - completed - skipped)
            print(
                f"  [PROVIDER BLOCK] {context}: {prov} marked BLOCKED ({kind})",
                file=sys.stderr,
            )
            handle_provider_block(
                info=info,
                data_dir=data_dir,
                dyads_done=completed,
                dyads_remaining=remaining,
                cost_so_far=cumulative_cost,
                resume_cmd=resume_cmd,
            )

    for i, spec in enumerate(grid):
        dyad_id = spec["dyad_id"]
        scenario_id = spec["scenario_id"]

        # Check if all needed providers are blocked → halt
        if not mock and _all_needed_blocked():
            print(
                f"\n[run_experiment] HALTING: all needed providers are blocked. "
                f"See {data_dir.parent / 'RUN_STATUS.md'} for resume instructions.",
                file=sys.stderr,
            )
            break

        # Resume check: verify-on-disk (transcript + outcomes row)
        if args.resume:
            if transcript_exists(dyad_id, data_dir) and outcome_row_exists(
                dyad_id, outcomes_path
            ):
                skipped += 1
                continue

        # Budget stop
        if cumulative_cost >= budget_stop and not dry_run:
            print(
                f"\n[run_experiment] BUDGET STOP: cumulative cost "
                f"${cumulative_cost:.4f} >= ${budget_stop}. Stopping."
            )
            break

        # Skip this dyad if its provider is blocked
        dyad_provider = _provider_of(model)
        if not mock and dyad_provider in blocked_providers:
            print(f"  [SKIP] {dyad_id}: provider {dyad_provider} is blocked")
            failed += 1
            continue

        # Load scenario
        try:
            scenario = load_scenario(scenario_id, scenarios_dir=resolved_scenarios_dir)
        except FileNotFoundError as e:
            print(f"  [SKIP] {dyad_id}: {e}")
            failed += 1
            continue

        agent_a_config = {"condition": spec["cond_a"], "model": model}
        agent_b_config = {"condition": spec["cond_b"], "model": model}

        # Run dyad (K=14; raised from 8 — harness-correctness fix)
        try:
            transcript = run_dyad(
                scenario=scenario,
                role_a_id=spec["role_a"],
                role_b_id=spec["role_b"],
                agent_a_config=agent_a_config,
                agent_b_config=agent_b_config,
                dyad_id=dyad_id,
                max_rounds=14,
                temperature=temperature,
                logs_dir=logs_dir,
                mock=mock,
            )
        except Exception as e:
            _handle_block(e, f"run_dyad {dyad_id}")
            info = classify_provider_error(e)
            if not info.get("transient", False) and not mock:
                failed += 1
                continue
            print(f"  [FAIL] {dyad_id}: run_dyad error: {e}")
            failed += 1
            continue

        # Write transcript atomically (SSOT)
        write_transcript(transcript, data_dir)

        # Compute outcomes
        try:
            outcome = compute_outcome(
                transcript, scenario, spec["role_a"], spec["role_b"]
            )
        except Exception as e:
            print(f"  [WARN] {dyad_id}: compute_outcome error: {e}")
            outcome = {
                "deal": False,
                "deal_terms": None,
                "value_claimed_a": 0.0,
                "value_claimed_b": 0.0,
                "value_created": None,
                "split": None,
                "scenario_type": scenario.get("type", "unknown"),
                "notes": [f"outcome_error: {e}"],
            }

        # Optionally score warmth/dominance + SVI
        wd_a: dict = {}
        svi_a: dict = {}
        wd_b: dict = {}
        svi_b: dict = {}
        if do_score:
            try:
                wd_a = score_warmth_dominance(
                    transcript, spec["role_a"], logs_dir=logs_dir, mock=mock
                )
                wd_b = score_warmth_dominance(
                    transcript, spec["role_b"], logs_dir=logs_dir, mock=mock
                )
                svi_a = score_svi(
                    transcript, spec["role_a"], logs_dir=logs_dir, mock=mock
                )
                svi_b = score_svi(
                    transcript, spec["role_b"], logs_dir=logs_dir, mock=mock
                )
            except Exception as e:
                _handle_block(e, f"scoring {dyad_id}")
                print(f"  [WARN] {dyad_id}: scoring error: {e}")

        # Estimate dyad cost (from logs if live, else 0)
        dyad_cost = 0.0 if mock else _extract_cost_from_logs(logs_dir, dyad_id)
        cumulative_cost += dyad_cost

        # Build outcomes row
        def _mean_score(scores: dict, key: str) -> float | None:
            vals = [s[key] for s in scores.values() if key in s]
            return sum(vals) / len(vals) if vals else None

        row: dict[str, Any] = {
            "dyad_id": dyad_id,
            "scenario_id": scenario_id,
            "scenario_type": outcome.get("scenario_type", ""),
            "cond_a": spec["cond_a"],
            "cond_b": spec["cond_b"],
            "role_a": spec["role_a"],
            "role_b": spec["role_b"],
            "replicate": spec["replicate"],
            "model_a": transcript.get("model_a", model),
            "model_b": transcript.get("model_b", model),
            "deal": int(outcome.get("deal", False)),
            "deal_terms_json": (
                json.dumps(outcome.get("deal_terms"))
                if outcome.get("deal_terms")
                else ""
            ),
            "rounds_to_deal": transcript.get("rounds_to_deal", ""),
            "value_claimed_a": outcome.get("value_claimed_a", ""),
            "value_claimed_b": outcome.get("value_claimed_b", ""),
            "points_a": outcome.get("points_a", ""),
            "points_b": outcome.get("points_b", ""),
            "value_created": outcome.get("value_created", ""),
            "split": outcome.get("split", ""),
            "warmth_a_mean": _mean_score(wd_a, "warmth_score"),
            "dominance_a_mean": _mean_score(wd_a, "dominance_score"),
            "warmth_b_mean": _mean_score(wd_b, "warmth_score"),
            "dominance_b_mean": _mean_score(wd_b, "dominance_score"),
            "svi_a_mean": _mean_score(
                svi_a, "instrumental"
            ),  # using instrumental as proxy
            "svi_b_mean": _mean_score(svi_b, "instrumental"),
            "cost_usd_est": dyad_cost,
            "notes": "; ".join(outcome.get("notes", [])),
            "mock": int(mock),
        }
        write_outcomes_row(row, outcomes_path)
        completed += 1

        # Progress report
        if completed % COST_PRINT_EVERY == 0:
            elapsed = time.time() - start_time
            rate = completed / elapsed if elapsed > 0 else 0
            remaining = len(grid) - completed - skipped
            print(
                f"  [progress] completed={completed} skipped={skipped} "
                f"failed={failed} "
                f"cost_so_far=${cumulative_cost:.4f} "
                f"rate={rate:.1f}/s remaining={remaining}"
            )

    # Final summary
    elapsed = time.time() - start_time
    print(
        f"\n[run_experiment] DONE: completed={completed} skipped={skipped} "
        f"failed={failed} total_cost=${cumulative_cost:.4f} "
        f"elapsed={elapsed:.1f}s"
    )
    print(f"  transcripts: {data_dir}")
    print(f"  outcomes:    {outcomes_path}")
    if blocked_providers:
        print(
            f"  BLOCKED providers: {sorted(blocked_providers)} — "
            f"see {data_dir.parent / 'RUN_STATUS.md'}",
            file=sys.stderr,
        )
    if dry_run:
        print("  (DRY-RUN: no real API calls were made)")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run the Spec-Agent vs Styled-Agent negotiation experiment."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Mock mode: zero API calls, output to dryrun/ (default for testing)",
    )
    parser.add_argument(
        "--preflight",
        action="store_true",
        help=(
            "Issue 1-token test calls to each required model; "
            "print OK/NEEDS_DEPOSIT/AUTH/ERROR table; exit non-zero if any blocked. "
            "In --dry-run mode, reports OK without real API calls."
        ),
    )
    parser.add_argument(
        "--pilot",
        type=int,
        default=None,
        metavar="N",
        help="Cap to ~N negotiations, balanced across cells",
    )
    parser.add_argument(
        "--model",
        type=str,
        default=DEFAULT_MODEL,
        help=f"Primary model ID (default: {DEFAULT_MODEL})",
    )
    parser.add_argument(
        "--replicates",
        type=int,
        default=DEFAULT_REPLICATES,
        help=f"Replicates per cell (default: {DEFAULT_REPLICATES})",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Skip dyads already on disk (idempotent)",
    )
    parser.add_argument(
        "--budget-stop",
        type=float,
        default=BUDGET_STOP_DEFAULT,
        metavar="USD",
        help=f"Abort when cumulative cost >= USD (default: {BUDGET_STOP_DEFAULT})",
    )
    parser.add_argument(
        "--temp",
        type=float,
        default=DEFAULT_TEMPERATURE,
        help=f"Sampling temperature (default: {DEFAULT_TEMPERATURE})",
    )
    parser.add_argument(
        "--score",
        action="store_true",
        help="Also run warmth/dominance + SVI scoring after each dyad",
    )
    parser.add_argument(
        "--data-dir",
        type=str,
        default=None,
        metavar="PATH",
        help=(
            "Override output root directory (transcripts/, outcomes.csv, run logs). "
            "Default: data/ for live, dryrun/ for --dry-run. "
            "Relative paths are resolved under the experiment directory. "
            "Use this to isolate per-model arms (e.g. --data-dir data_haiku)."
        ),
    )
    parser.add_argument(
        "--logs-dir",
        type=str,
        default=None,
        metavar="PATH",
        help=(
            "Override JSONL logs directory. "
            "Default: logs/ for live, dryrun/logs/ for --dry-run. "
            "Relative paths are resolved under the experiment directory."
        ),
    )
    parser.add_argument(
        "--scenarios-dir",
        type=str,
        default=None,
        metavar="PATH",
        help=(
            "Override the scenarios directory. "
            "Default: scenarios/ (Study 1). "
            "Use scenarios_study2/ for Study 2. "
            "Relative paths are resolved under the experiment directory."
        ),
    )
    parser.add_argument(
        "--scenario-ids",
        type=str,
        default=None,
        metavar="id1,id2,...",
        help=(
            "Comma-separated list of scenario ids to run. "
            "Default: chair,rental,offer (Study 1). "
            "Example for Study 2: merger,supplier,salvage. "
            "Role pairs are derived from each scenario's YAML roles list."
        ),
    )
    parser.add_argument(
        "--conditions",
        type=str,
        default=None,
        metavar="id1,id2,...",
        help=(
            "Comma-separated list of condition ids to include in the grid. "
            f"Default: all {len(CONDITIONS)} conditions ({','.join(CONDITIONS)}). "
            "Each id must be a known condition or have a matching prompts/<id>.txt file "
            "(allows new conditions like SPEC_NOLOGROLL and paraphrase variants like "
            "SPEC_NOCOT_p1 without modifying the CONDITIONS constant). "
            "When omitted, the full default condition set is used — behavior is "
            "byte-identical to the pre-flag baseline. "
            "Example: --conditions NEUTRAL,COT_ONLY,SPEC_NOCOT,SPEC_NOLOGROLL"
        ),
    )
    parser.add_argument(
        "--opponent",
        type=str,
        default=None,
        metavar="COND",
        help=(
            "Fix a single opponent condition for focal-vs-fixed-opponent pairing. "
            "When set, every condition in --conditions is paired ONLY against COND "
            "(both role orders), instead of a full round-robin over the condition set. "
            "This is for the paraphrase-envelope stage (focal paraphrase vs pinned NEUTRAL). "
            "Dyad count = len(conditions) × S scenarios × 2 role orders × R replicates "
            "(vs the round-robin's M*(M+1)/2 pairs × S × 2 × R). "
            "When omitted, the full round-robin is used — behavior is unchanged. "
            "Example: --opponent NEUTRAL"
        ),
    )

    args = parser.parse_args()

    if args.preflight:
        sys.exit(run_preflight(args))

    run_grid(args)


if __name__ == "__main__":
    main()
