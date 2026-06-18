"""rescore_transcripts.py — Re-score existing transcripts with the v2 dominance rubric.

Loads all 20 existing transcripts from data/transcripts/, re-scores each agent's
warmth and dominance with BOTH scorers (gpt-4o and claude-haiku-4-5, temp=0) using
the updated WARMTH_DOMINANCE_SYSTEM rubric (v2), logs all calls via llm_call_logger
to phase="rescore_v2", and computes inter-scorer ICC(2,1) for warmth and dominance.

--- AUDIT MODE (capture_reasoning=True) ---

When `capture_reasoning=True` is passed to `main()`, the script uses a modified
scoring prompt variant that asks the scorer to give a 1-2 sentence rationale BEFORE
the JSON block, then stores the full response (rationale + JSON) in the log. This
mode is intended for POST-RUN stratified audits of a subsample of transcripts (e.g.,
the 30-transcript hand-check corpus) to verify rubric fidelity.

IMPORTANT: The reasoning-capture variant does NOT overwrite the primary numeric scores.
The primary scores were validated at ICC .863 (warmth) / .802 (dominance) using the
standard "Return ONLY valid JSON" prompt (per PREREGISTRATION §5 gate, recorded in
PILOT_GATE_AUDIT.md). The audit mode produces supplementary qualitative evidence only.

Do NOT run capture_reasoning=True during the live primary run.

Usage (standard rescore, from repo root):
    bws run -- uv run --with openai --with anthropic --with pyyaml --with numpy \\
        python [internal path removed]

Usage (audit mode, post-run only):
    bws run -- uv run --with openai --with anthropic --with pyyaml --with numpy \\
        python [internal path removed] \\
        --capture-reasoning

Cost cap: ~$0.30 standard (40 agent-turns x 2 scorers x ~$0.003/call).
Cost cap audit mode: ~$0.80 (higher output token count due to reasoning text).
"""

from __future__ import annotations

import json
import sys
import time
from collections import defaultdict
from pathlib import Path

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------
CODE_DIR = Path(__file__).resolve().parent
EXPERIMENT_DIR = CODE_DIR.parent
TRANSCRIPTS_DIR = EXPERIMENT_DIR / "data" / "transcripts"
LOGS_DIR = EXPERIMENT_DIR / "logs"

REPO_ROOT = Path(__file__).resolve().parents[3]
RESEARCH_CODE = REPO_ROOT / "research" / "code"
sys.path.insert(0, str(CODE_DIR))
sys.path.insert(0, str(RESEARCH_CODE))

from outcomes import compute_icc_2_1  # noqa: E402
from provider_errors import call_with_retry  # noqa: E402
from scoring_llm import (  # noqa: E402
    SCORER_MODELS,
    WARMTH_DOMINANCE_SYSTEM,
    _build_scoring_prompt,
    _parse_json_response,
    _score_with_anthropic,
    _score_with_openai,
)

# ---------------------------------------------------------------------------
# Audit-mode prompt variant (capture_reasoning=True)
# ---------------------------------------------------------------------------
#
# This prompt asks the scorer to provide a brief rationale before the JSON.
# It is ONLY used in --capture-reasoning audit passes; the primary numeric
# scores use WARMTH_DOMINANCE_SYSTEM (which ends in "Return ONLY valid JSON").
#
# The reasoning text is captured verbatim in the log's "response" field and
# does NOT affect the numeric scores (those are extracted via _parse_json_response
# which strips the reasoning before parsing the JSON block).

_WARMTH_DOMINANCE_REASONING_SUFFIX = (
    "\n\nIn 1-2 sentences, describe the key signals you used to assign these scores. "
    "Then, on a new line, return ONLY valid JSON: "
    '{"warmth_score": <0-100>, "dominance_score": <0-100>}'
)

WARMTH_DOMINANCE_REASONING_SYSTEM = (
    WARMTH_DOMINANCE_SYSTEM.rstrip()
    .removesuffix(
        'Return ONLY valid JSON: {"warmth_score": <0-100>, "dominance_score": <0-100>}'
    )
    .rstrip()
    + _WARMTH_DOMINANCE_REASONING_SUFFIX
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _load_transcripts() -> list[dict]:
    transcripts = []
    for p in sorted(TRANSCRIPTS_DIR.glob("*.json")):
        with open(p) as f:
            transcripts.append(json.load(f))
    return transcripts


def _rescore_one_agent(
    transcript: dict,
    target_role: str,
    phase: str = "rescore_v2",
    capture_reasoning: bool = False,
) -> dict[str, dict[str, float]]:
    """Score warmth+dominance for one agent with both scorers.

    Args:
        transcript: transcript dict loaded from data/transcripts/.
        target_role: agent role to score (e.g. "buyer", "tenant").
        phase: phase tag for JSONL log file naming.
        capture_reasoning: if True, use the audit-mode prompt variant that asks
            the scorer for a 1-2 sentence rationale before the JSON. The rationale
            is stored verbatim in the log's "response" field.
            NOTE: this is for post-run audits only. The primary numeric scores
            (ICC-validated at .863/.802, per PILOT_GATE_AUDIT.md) used the
            standard "Return ONLY valid JSON" prompt. Do NOT use capture_reasoning
            during the live primary run.

    Returns:
        {"gpt-4o": {"warmth_score": float, "dominance_score": float},
         "claude-haiku-4-5": {...}}
    """
    user_prompt = _build_scoring_prompt(transcript, target_role, "warmth_dominance")
    dyad_id = transcript.get("dyad_id", "unknown")

    # Select system prompt based on audit mode
    system_prompt = (
        WARMTH_DOMINANCE_REASONING_SYSTEM
        if capture_reasoning
        else WARMTH_DOMINANCE_SYSTEM
    )

    # Use a distinct operation_tag that encodes the phase so logs are separate
    # from the original pilot scoring logs
    op_tag = f"{phase}_gpt4o"
    raw_gpt = call_with_retry(
        _score_with_openai,
        "gpt-4o",
        system_prompt,
        user_prompt,
        dyad_id,
        op_tag,
        LOGS_DIR,
    )
    gpt_scores = _parse_json_response(raw_gpt, ["warmth_score", "dominance_score"])

    op_tag = f"{phase}_haiku"
    raw_haiku = call_with_retry(
        _score_with_anthropic,
        "claude-haiku-4-5",
        system_prompt,
        user_prompt,
        dyad_id,
        op_tag,
        LOGS_DIR,
    )
    haiku_scores = _parse_json_response(raw_haiku, ["warmth_score", "dominance_score"])

    return {"gpt-4o": gpt_scores, "claude-haiku-4-5": haiku_scores}


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main(capture_reasoning: bool = False) -> None:
    """Re-score transcripts with the v2.1 dominance rubric.

    Args:
        capture_reasoning: if True, use the audit-mode prompt variant (stores
            scorer rationale in logs). For post-run audits only; do NOT use
            during the live primary run. See module docstring for details.
    """
    transcripts = _load_transcripts()
    print(f"Loaded {len(transcripts)} transcripts from {TRANSCRIPTS_DIR}")
    print(f"Logs -> {LOGS_DIR}")
    if capture_reasoning:
        print(
            "AUDIT MODE: capture_reasoning=True — scorer rationale will be "
            "stored in log response field. Logs tagged phase='rescore_v2_audit'."
        )
    print()

    phase = "rescore_v2_audit" if capture_reasoning else "rescore_v2"

    # Each transcript has two agents; collect per-(dyad,role) scores
    results: list[dict] = []  # flat list of scored agent-turns

    total_agents = sum(2 for _ in transcripts)
    done = 0

    for transcript in transcripts:
        dyad_id = transcript["dyad_id"]
        role_a = transcript["role_a"]
        role_b = transcript["role_b"]
        cond_a = transcript.get("agent_a_condition", "UNKNOWN")
        cond_b = transcript.get("agent_b_condition", "UNKNOWN")

        for role, cond in [(role_a, cond_a), (role_b, cond_b)]:
            done += 1
            print(
                f"  [{done:02d}/{total_agents}] {dyad_id[:45]:45s} {role:12s} {cond}",
                flush=True,
            )
            scores = _rescore_one_agent(
                transcript, role, phase=phase, capture_reasoning=capture_reasoning
            )
            gpt = scores["gpt-4o"]
            haiku = scores["claude-haiku-4-5"]
            print(
                f"         GPT4o: W={gpt['warmth_score']:.0f} D={gpt['dominance_score']:.0f} | "
                f"Haiku: W={haiku['warmth_score']:.0f} D={haiku['dominance_score']:.0f}"
            )
            results.append(
                {
                    "dyad_id": dyad_id,
                    "role": role,
                    "condition": cond,
                    "gpt4o_w": gpt["warmth_score"],
                    "gpt4o_d": gpt["dominance_score"],
                    "haiku_w": haiku["warmth_score"],
                    "haiku_d": haiku["dominance_score"],
                }
            )
            # Small pause to avoid rate limits
            time.sleep(0.5)

    # ---------------------------------------------------------------------------
    # ICC(2,1) computation
    # ---------------------------------------------------------------------------
    dom_gpt = [r["gpt4o_d"] for r in results]
    dom_haiku = [r["haiku_d"] for r in results]
    war_gpt = [r["gpt4o_w"] for r in results]
    war_haiku = [r["haiku_w"] for r in results]

    icc_dom = compute_icc_2_1(dom_gpt, dom_haiku)
    icc_war = compute_icc_2_1(war_gpt, war_haiku)

    print()
    print("=" * 60)
    print("INTER-SCORER ICC(2,1) — RESCORE v2")
    print("=" * 60)
    print(f"  WARMTH    ICC = {icc_war['icc']:.3f}  (n={icc_war['n_targets']})")
    print(f"  DOMINANCE ICC = {icc_dom['icc']:.3f}  (n={icc_dom['n_targets']})")
    print()

    gate_w = "PASS" if icc_war["icc"] >= 0.70 else "FAIL"
    gate_d = "PASS" if icc_dom["icc"] >= 0.70 else "FAIL"
    print(f"  WARMTH gate    (>=.70): {gate_w}")
    print(f"  DOMINANCE gate (>=.70): {gate_d}")
    print()

    # ---------------------------------------------------------------------------
    # Per-condition dominance means (manipulation check H6 sanity)
    # ---------------------------------------------------------------------------
    cond_buckets: dict[str, dict[str, list]] = defaultdict(
        lambda: {"gpt4o": [], "haiku": [], "mean": []}
    )
    for r in results:
        c = r["condition"]
        cond_buckets[c]["gpt4o"].append(r["gpt4o_d"])
        cond_buckets[c]["haiku"].append(r["haiku_d"])
        cond_buckets[c]["mean"].append((r["gpt4o_d"] + r["haiku_d"]) / 2)

    print("DOMINANCE means by condition (manipulation check H6):")
    print(f"  {'Condition':20s} {'GPT4o-D':8s} {'Haiku-D':8s} {'Mean-D':8s} {'N':4s}")
    print(f"  {'-'*20:20s} {'-'*8:8s} {'-'*8:8s} {'-'*8:8s} {'-'*4:4s}")
    for cond in sorted(cond_buckets.keys()):
        b = cond_buckets[cond]
        n = len(b["gpt4o"])
        g_mean = sum(b["gpt4o"]) / n
        h_mean = sum(b["haiku"]) / n
        m_mean = sum(b["mean"]) / n
        dom_flag = " <- should be HIGH" if cond == "DOMINANCE" else ""
        spec_flag = " <- should be LOW" if cond in ("SPEC_NOCOT", "SPEC_COT") else ""
        print(
            f"  {cond:20s} {g_mean:8.1f} {h_mean:8.1f} {m_mean:8.1f} {n:4d}"
            f"{dom_flag}{spec_flag}"
        )

    print()
    print("WARMTH means by condition:")
    print(f"  {'Condition':20s} {'GPT4o-W':8s} {'Haiku-W':8s} {'N':4s}")
    cond_w: dict[str, dict[str, list]] = defaultdict(lambda: {"gpt4o": [], "haiku": []})
    for r in results:
        c = r["condition"]
        cond_w[c]["gpt4o"].append(r["gpt4o_w"])
        cond_w[c]["haiku"].append(r["haiku_w"])
    for cond in sorted(cond_w.keys()):
        b = cond_w[cond]
        n = len(b["gpt4o"])
        g_mean = sum(b["gpt4o"]) / n
        h_mean = sum(b["haiku"]) / n
        print(f"  {cond:20s} {g_mean:8.1f} {h_mean:8.1f} {n:4d}")

    # ---------------------------------------------------------------------------
    # Save results CSV
    # ---------------------------------------------------------------------------
    out_csv = EXPERIMENT_DIR / "data" / "rescore_v2_results.csv"
    with open(out_csv, "w") as f:
        f.write("dyad_id,role,condition,gpt4o_w,gpt4o_d,haiku_w,haiku_d\n")
        for r in results:
            f.write(
                f"{r['dyad_id']},{r['role']},{r['condition']},"
                f"{r['gpt4o_w']:.0f},{r['gpt4o_d']:.0f},"
                f"{r['haiku_w']:.0f},{r['haiku_d']:.0f}\n"
            )
    print(f"\nResults saved to {out_csv}")
    print()

    # Exit with non-zero if dominance gate still fails (for CI awareness)
    if icc_dom["icc"] < 0.70:
        print(
            "WARNING: DOMINANCE ICC still below .70 gate. "
            "See report for next-lever recommendations."
        )
        sys.exit(1)
    else:
        print("Both warmth and dominance gates PASSED. Scorer reliability confirmed.")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Re-score negotiation transcripts with the v2.1 dominance rubric."
    )
    parser.add_argument(
        "--capture-reasoning",
        action="store_true",
        default=False,
        help=(
            "Audit mode: ask scorers for a 1-2 sentence rationale before the JSON. "
            "The rationale is stored in the log response field for post-run spot-checks. "
            "DO NOT use during the live primary run. "
            "See module docstring for details."
        ),
    )
    args = parser.parse_args()
    main(capture_reasoning=args.capture_reasoning)
