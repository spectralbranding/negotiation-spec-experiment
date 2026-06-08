"""backfill_scores.py — re-score existing transcripts and backfill the warmth /
dominance / SVI columns into an existing outcomes.csv WITHOUT re-running negotiation.

Use when a run completed negotiation but the scorer was unavailable (e.g. the provider
balance ran dry mid-run), leaving the 6 scoring columns empty. This reuses the SAME
`score_warmth_dominance` / `score_svi` functions and the SAME mean->column mapping as
`run_experiment.py`, so the scoring methodology is identical. ONLY the 6 scoring
columns are written; negotiation columns and the transcripts themselves are never
touched.

Idempotent: skips any dyad whose `warmth_a_mean` is already populated, so re-running
after a provider pause continues where it stopped. Graceful provider-block handling
re-uses the same RUN_STATUS.md / ntfy mechanism as the main runner.

Usage (from repo root):
    uv run --with openai --with anthropic --with pyyaml --with numpy \\
        python code/backfill_scores.py \\
        --data-dir data_study2 --logs-dir logs_study2

Mock validation (no API calls; writes to outcomes.mocktest.csv, never the real file):
    uv run --with openai --with anthropic --with pyyaml --with numpy \\
        python code/backfill_scores.py \\
        --data-dir data_study2 --logs-dir /tmp/bf_logs --mock --limit 5
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any

EXPERIMENT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))

from provider_errors import (  # noqa: E402
    classify_provider_error,
    handle_provider_block,
)
from scoring_llm import score_svi, score_warmth_dominance  # noqa: E402

SCORING_COLS = [
    "warmth_a_mean",
    "dominance_a_mean",
    "warmth_b_mean",
    "dominance_b_mean",
    "svi_a_mean",
    "svi_b_mean",
]


def _mean_score(scores: dict[str, dict[str, float]], key: str) -> float | None:
    vals = [s[key] for s in scores.values() if key in s]
    return sum(vals) / len(vals) if vals else None


def _fmt(value: float | None) -> str:
    return "" if value is None else repr(value)


def _write(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    tmp = path.with_suffix(".csv.tmp")
    with open(tmp, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    tmp.replace(path)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", required=True)
    parser.add_argument("--logs-dir", required=True)
    parser.add_argument(
        "--limit", type=int, default=0, help="score at most N dyads (0 = all)"
    )
    parser.add_argument(
        "--mock",
        action="store_true",
        help="mock scores (no API); writes to outcomes.mocktest.csv only",
    )
    args = parser.parse_args()

    data_dir = EXPERIMENT_DIR / args.data_dir
    logs_dir = (
        EXPERIMENT_DIR / args.logs_dir
        if not Path(args.logs_dir).is_absolute()
        else Path(args.logs_dir)
    )
    transcripts_dir = data_dir / "transcripts"
    outcomes_path = data_dir / "outcomes.csv"
    logs_dir.mkdir(parents=True, exist_ok=True)

    # Mock writes to a SEPARATE file — never the real outcomes.csv.
    write_path = (
        outcomes_path.with_name("outcomes.mocktest.csv") if args.mock else outcomes_path
    )

    with open(outcomes_path, newline="") as f:
        reader = csv.DictReader(f)
        fieldnames = list(reader.fieldnames or [])
        rows: list[dict[str, str]] = list(reader)

    missing = [r for r in rows if not (r.get("warmth_a_mean") or "").strip()]
    todo = missing[: args.limit] if args.limit else missing
    print(
        f"[backfill] {len(missing)} dyads need scoring (of {len(rows)} total); "
        f"processing {len(todo)}{' [MOCK]' if args.mock else ''}"
    )

    resume_cmd = (
        "uv run --with openai --with anthropic --with pyyaml --with numpy "
        "python code/backfill_scores.py "
        f"--data-dir {args.data_dir} --logs-dir {args.logs_dir}"
    )

    done = 0
    for r in todo:
        dyad_id = r["dyad_id"]
        tpath = transcripts_dir / f"{dyad_id}.json"
        if not tpath.exists():
            print(f"  [SKIP] {dyad_id}: no transcript on disk")
            continue
        with open(tpath) as tf:
            transcript: dict[str, Any] = json.load(tf)
        role_a = transcript.get("role_a") or r.get("role_a") or ""
        role_b = transcript.get("role_b") or r.get("role_b") or ""

        try:
            wd_a = score_warmth_dominance(
                transcript, role_a, logs_dir=logs_dir, mock=args.mock
            )
            wd_b = score_warmth_dominance(
                transcript, role_b, logs_dir=logs_dir, mock=args.mock
            )
            svi_a = score_svi(transcript, role_a, logs_dir=logs_dir, mock=args.mock)
            svi_b = score_svi(transcript, role_b, logs_dir=logs_dir, mock=args.mock)
        except Exception as e:  # noqa: BLE001
            info = classify_provider_error(e)
            if not info.get("transient", False):
                remaining = sum(
                    1 for x in rows if not (x.get("warmth_a_mean") or "").strip()
                )
                handle_provider_block(
                    info=info,
                    data_dir=data_dir,
                    dyads_done=done,
                    dyads_remaining=remaining,
                    cost_so_far=0.0,
                    resume_cmd=resume_cmd,
                )
                _write(write_path, fieldnames, rows)
                print(
                    f"[backfill] HALTED on provider block "
                    f"({info.get('provider')}); wrote partial to {write_path.name}. "
                    "Deposit, then re-run the same command (idempotent)."
                )
                return
            print(f"  [WARN] {dyad_id}: transient scoring error: {e}")
            continue

        r["warmth_a_mean"] = _fmt(_mean_score(wd_a, "warmth_score"))
        r["dominance_a_mean"] = _fmt(_mean_score(wd_a, "dominance_score"))
        r["warmth_b_mean"] = _fmt(_mean_score(wd_b, "warmth_score"))
        r["dominance_b_mean"] = _fmt(_mean_score(wd_b, "dominance_score"))
        r["svi_a_mean"] = _fmt(_mean_score(svi_a, "instrumental"))
        r["svi_b_mean"] = _fmt(_mean_score(svi_b, "instrumental"))
        done += 1
        if done % 20 == 0:
            _write(write_path, fieldnames, rows)
            print(f"  [progress] scored {done}/{len(todo)}")

    _write(write_path, fieldnames, rows)
    print(f"[backfill] DONE: scored {done} dyads -> {write_path}")


if __name__ == "__main__":
    main()
