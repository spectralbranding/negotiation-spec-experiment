"""scoring_llm.py — S19 warmth/dominance rubric + SVI 4-facet scoring.

Scoring uses TWO independent scorers: gpt-4o and claude-haiku-4-5.
Each LLM call is logged via llm_call_logger.

mock=True returns deterministic fake scores (zero API).

S19 rubric (from Vaccaro et al. 2026, SI Fig. S19):
    Returns {warmth_score: 0-100, dominance_score: 0-100}, orthogonal constructs.
    Warmth: friendly, empathetic, relationship-building.
    Dominance: assertive, forceful, pressure-applying.
    (SPEC agents should score LOW on both.)

SVI (Subjective Value Inventory) — 4 facets, 0-100 each:
    instrumental: "Did you get what you wanted?"
    self: "Are you satisfied with your own performance?"
    process: "Did the negotiation process feel fair and comfortable?"
    relationship: "How do you feel about your relationship with the counterpart?"

Inter-scorer reliability: compute_icc_2_1 in outcomes.py.
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]
RESEARCH_CODE = REPO_ROOT / "research" / "code"
sys.path.insert(0, str(RESEARCH_CODE))

# ---------------------------------------------------------------------------
# Rubric prompts (S19-faithful)
#
# PUBLISHED COPIES: the exact text of both rubrics is also published as
# standalone files for reviewer inspection per PROMPT_PURITY_PROTOCOL HARD RULE:
#   prompts/SCORING_WARMTH_DOMINANCE.txt  (this prompt, WARMTH_DOMINANCE_SYSTEM)
#   prompts/SCORING_SVI.txt               (SVI_SYSTEM below)
#
# The standalone files include YAML front-matter (version, scorer_models, date,
# source_code_reference). The system prompt text begins after the closing "---"
# line in those files. Keep the text here and in the .txt files in sync.
# SHA-256 of the .txt files is recorded in prompts/PROMPT_HASHES.txt.
# ---------------------------------------------------------------------------

WARMTH_DOMINANCE_SYSTEM = """You are a researcher coding negotiation transcripts for warmth and dominance.
Score the SPECIFIED AGENT's messages only (ignore the counterpart).

WARMTH (0-100): How friendly, empathetic, relationship-building, and socially warm is this agent?
  0 = completely cold, purely transactional
  50 = neutral, neither warm nor cold
  100 = extremely warm, highly empathetic, rapport-focused

DOMINANCE (0-100): How assertive and pressure-applying is this agent's COMMUNICATION STYLE?
Score the LANGUAGE STYLE, not the outcome (getting a good deal is NOT dominance).

WHAT DOMINANCE IS — score these behavioral signals from LOWEST to HIGHEST:

LEVEL 0 — No dominance signal
  Pure mechanical output with no interpersonal stance: bare offers only, or data/calculations
  with no framing whatsoever. Example: "OFFER: {price: 350}" with nothing else.

LEVEL 25 — Low dominance: informational refusals only
  States own limits matter-of-factly, no forcefulness: "I cannot go below $300." /
  "That does not meet my minimum." / "I propose $X." Simple first-person limit-statements
  without any pressure or claiming language. No expressions of will or intent.

LEVEL 50 — Moderate dominance: explicit will + firmness claims
  Actively asserts own position with explicit personal will or firmness:
  "I am firm on my request for $X." / "I am not willing to go above $X." /
  "I'm holding my ground." / "My best and final offer is $X." /
  "I expect $X." / "I must emphasize that..." / "I insist on..."
  These phrases express explicit personal determination, not just information.

LEVEL 75 — High dominance: commands + pressure + ultimatums
  Uses direct commands or explicit pressure tactics:
  "Lower your price." / "Take it or leave it." / "You must accept X." /
  "I will walk away if..." / "I demand $X." / "Give me X or we are done." /
  "This is non-negotiable." Combined with repeated refusals and forceful framing.

LEVEL 100 — Maximum dominance: aggressive, contemptuous, coercive
  Pervasive imperatives, threats, contemptuous dismissal of counterpart's position.
  Every message exerts explicit pressure. Coercive or hostile framing throughout.

DISAMBIGUATION:
  - "I appreciate your offer, but I'm firm on $X" → LEVEL 50 (explicit firmness claim)
  - "I cannot accept below $X" → LEVEL 25 (informational limit, no personal will expressed)
  - "Accept $X or I leave" → LEVEL 75 (ultimatum with threat)
  - Bare offer only → LEVEL 0

IMPORTANT: warmth and dominance are ORTHOGONAL — score each independently.
An agent that states its limits without pressure language scores LOW on dominance (0-30)
even if it never concedes. An agent using "I am firm" / "I insist" / "I expect" scores
in the 40-60 range even without explicit commands or threats.

Return ONLY valid JSON: {"warmth_score": <0-100>, "dominance_score": <0-100>}"""


SVI_SYSTEM = """You are a researcher scoring a negotiator's subjective value experience.
Based on the transcript of the SPECIFIED AGENT's messages, score four SVI facets.

INSTRUMENTAL (0-100): Did the agent get what they wanted? (0=got nothing, 100=got everything)
SELF (0-100): Did the agent seem satisfied with their own performance? (0=dissatisfied, 100=very proud)
PROCESS (0-100): Did the negotiation process seem fair and comfortable for this agent? (0=awful, 100=ideal)
RELATIONSHIP (0-100): How positive does the agent's relationship with the counterpart appear? (0=hostile, 100=warm)

Return ONLY valid JSON:
{"instrumental": <0-100>, "self": <0-100>, "process": <0-100>, "relationship": <0-100>}"""


def _build_scoring_prompt(
    transcript: dict[str, Any],
    target_role: str,
    task: str,
) -> str:
    """Extract the target agent's turns and build a scoring user prompt."""
    agent_turns = [
        t for t in transcript.get("turns", []) if t.get("role") == target_role
    ]
    # Strip <think> blocks
    cleaned = []
    for t in agent_turns:
        text = re.sub(
            r"<think>.*?</think>", "", t.get("text", ""), flags=re.DOTALL
        ).strip()
        cleaned.append(f"[Round {t['round']}] {text}")

    transcript_text = (
        "\n\n".join(cleaned) if cleaned else "[No messages from this agent]"
    )
    dyad_id = transcript.get("dyad_id", "unknown")
    condition = (
        transcript.get("agent_a_condition", "")
        if target_role == transcript.get("role_a", "")
        else transcript.get("agent_b_condition", "")
    )

    return (
        f"Dyad: {dyad_id}\n"
        f"Agent role: {target_role}\n"
        f"Agent condition: {condition}\n"
        f"Task: {task}\n\n"
        f"AGENT MESSAGES:\n{transcript_text}"
    )


# ---------------------------------------------------------------------------
# Mock scoring — deterministic, zero API
# ---------------------------------------------------------------------------


def _mock_seed(dyad_id: str, role: str, scorer: str, facet: str) -> int:
    h = hashlib.md5(f"{dyad_id}:{role}:{scorer}:{facet}".encode()).hexdigest()
    return int(h[:8], 16)


def _mock_warmth_dominance(
    transcript: dict[str, Any],
    target_role: str,
    scorer: str,
) -> dict[str, float]:
    """Return deterministic fake warmth/dominance scores."""
    dyad_id = transcript.get("dyad_id", "")
    condition = (
        transcript.get("agent_a_condition", "NEUTRAL")
        if target_role == transcript.get("role_a", "")
        else transcript.get("agent_b_condition", "NEUTRAL")
    )
    # Condition-anchored base scores (reflects manipulation check H6)
    bases = {
        "WARMTH": {"warmth": 75, "dominance": 25},
        "DOMINANCE": {"warmth": 25, "dominance": 75},
        "NEUTRAL": {"warmth": 40, "dominance": 40},
        "SPEC_NOCOT": {"warmth": 20, "dominance": 20},
        "SPEC_COT": {"warmth": 20, "dominance": 25},
        "COT_ONLY": {"warmth": 35, "dominance": 45},
    }
    base = bases.get(condition, {"warmth": 40, "dominance": 40})
    # Add deterministic jitter (±10)
    w_jitter = (_mock_seed(dyad_id, target_role, scorer, "warmth") % 21) - 10
    d_jitter = (_mock_seed(dyad_id, target_role, scorer, "dominance") % 21) - 10
    warmth = max(0, min(100, base["warmth"] + w_jitter))
    dominance = max(0, min(100, base["dominance"] + d_jitter))
    return {"warmth_score": float(warmth), "dominance_score": float(dominance)}


def _mock_svi(
    transcript: dict[str, Any],
    target_role: str,
    scorer: str,
) -> dict[str, float]:
    """Return deterministic fake SVI scores."""
    dyad_id = transcript.get("dyad_id", "")
    deal = transcript.get("deal", False)
    base = 65.0 if deal else 40.0
    result = {}
    for facet in ["instrumental", "self", "process", "relationship"]:
        jitter = (_mock_seed(dyad_id, target_role, scorer, facet) % 21) - 10
        result[facet] = float(max(0, min(100, base + jitter)))
    return result


# ---------------------------------------------------------------------------
# Live scoring — real API
# ---------------------------------------------------------------------------


def _parse_json_response(text: str, required_keys: list[str]) -> dict[str, float]:
    """Extract JSON from scorer response, return dict with required keys.

    Handles both plain JSON and responses wrapped in ```json ... ``` fences
    (claude-haiku-4-5 emits fences plus optional reasoning text after the block).
    """
    # Step 1: strip ```json ... ``` fences if present (both scorers may emit them)
    fence_m = re.search(r"```json\s*(.*?)\s*```", text, re.DOTALL)
    if fence_m:
        text = fence_m.group(1).strip()

    # Step 2: try direct parse of (possibly fence-stripped) text
    try:
        data = json.loads(text.strip())
        return {k: float(data[k]) for k in required_keys}
    except (json.JSONDecodeError, KeyError, ValueError):
        pass

    # Step 3: extract the first {...} block (handles trailing reasoning text)
    m = re.search(r"\{[^{}]+\}", text, re.DOTALL)
    if m:
        try:
            data = json.loads(m.group())
            return {k: float(data[k]) for k in required_keys}
        except (json.JSONDecodeError, KeyError, ValueError):
            pass

    raise ValueError(
        f"Could not parse scorer response as JSON with keys {required_keys}. "
        f"Response: {text[:200]}"
    )


def _score_with_openai(
    model: str,
    system_prompt: str,
    user_prompt: str,
    dyad_id: str,
    operation_tag: str,
    logs_dir: Path,
) -> str:
    """One OpenAI scoring call, logged."""
    try:
        import openai
    except ImportError:
        raise RuntimeError("openai SDK not installed.")

    try:
        from llm_call_logger import log_call
    except ImportError:
        raise RuntimeError("llm_call_logger not found.")

    import os

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY not set.")

    client = openai.OpenAI(api_key=api_key)

    with log_call(
        phase="scoring",
        operation=f"{operation_tag}_{dyad_id}",
        operator=model,
        operator_role="orchestrator",
        endpoint="https://api.openai.com/v1/chat/completions",
        sdk_version="openai",
        logs_dir=logs_dir,
    ) as logger:
        logger.set_system_prompt(system_prompt)
        logger.set_user_prompt(user_prompt)
        logger.set_parameters({"model": model, "temperature": 0.0, "max_tokens": 200})
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.0,
            max_tokens=200,
        )
        logger.capture_response(response)

    return response.choices[0].message.content or ""


def _score_with_anthropic(
    model: str,
    system_prompt: str,
    user_prompt: str,
    dyad_id: str,
    operation_tag: str,
    logs_dir: Path,
) -> str:
    """One Anthropic scoring call, logged."""
    try:
        import anthropic
    except ImportError:
        raise RuntimeError("anthropic SDK not installed.")

    try:
        from llm_call_logger import log_call
    except ImportError:
        raise RuntimeError("llm_call_logger not found.")

    import os

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY not set.")

    client = anthropic.Anthropic(api_key=api_key)

    with log_call(
        phase="scoring",
        operation=f"{operation_tag}_{dyad_id}",
        operator=model,
        operator_role="orchestrator",
        endpoint="https://api.anthropic.com/v1/messages",
        sdk_version="anthropic-sdk",
        logs_dir=logs_dir,
    ) as logger:
        logger.set_system_prompt(system_prompt)
        logger.set_user_prompt(user_prompt)
        logger.set_parameters({"model": model, "temperature": 0.0, "max_tokens": 200})
        response = client.messages.create(
            model=model,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
            temperature=0.0,
            max_tokens=200,
        )
        logger.capture_response(response)

    return response.content[0].text if response.content else ""


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

SCORER_MODELS = ["gpt-4o", "claude-haiku-4-5"]


def score_warmth_dominance(
    transcript: dict[str, Any],
    target_role: str,
    logs_dir: Path | None = None,
    mock: bool = False,
) -> dict[str, dict[str, float]]:
    """Score warmth and dominance for one agent using BOTH scorers.

    Returns:
        {
            "gpt-4o": {"warmth_score": float, "dominance_score": float},
            "claude-haiku-4-5": {"warmth_score": float, "dominance_score": float},
        }
    """
    if logs_dir is None:
        logs_dir = Path(__file__).resolve().parents[1] / "logs"

    if mock:
        return {
            scorer: _mock_warmth_dominance(transcript, target_role, scorer)
            for scorer in SCORER_MODELS
        }

    user_prompt = _build_scoring_prompt(transcript, target_role, "warmth_dominance")
    dyad_id = transcript.get("dyad_id", "unknown")

    results = {}
    # Scorer 1: gpt-4o
    raw = _score_with_openai(
        "gpt-4o",
        WARMTH_DOMINANCE_SYSTEM,
        user_prompt,
        dyad_id,
        "wd_gpt4o",
        logs_dir,
    )
    results["gpt-4o"] = _parse_json_response(raw, ["warmth_score", "dominance_score"])

    # Scorer 2: claude-haiku-4-5
    raw = _score_with_anthropic(
        "claude-haiku-4-5",
        WARMTH_DOMINANCE_SYSTEM,
        user_prompt,
        dyad_id,
        "wd_haiku",
        logs_dir,
    )
    results["claude-haiku-4-5"] = _parse_json_response(
        raw, ["warmth_score", "dominance_score"]
    )

    return results


def score_svi(
    transcript: dict[str, Any],
    target_role: str,
    logs_dir: Path | None = None,
    mock: bool = False,
) -> dict[str, dict[str, float]]:
    """Score SVI 4 facets for one agent using BOTH scorers.

    Returns:
        {
            "gpt-4o": {"instrumental": float, "self": float, "process": float, "relationship": float},
            "claude-haiku-4-5": {...},
        }
    """
    if logs_dir is None:
        logs_dir = Path(__file__).resolve().parents[1] / "logs"

    if mock:
        return {
            scorer: _mock_svi(transcript, target_role, scorer)
            for scorer in SCORER_MODELS
        }

    user_prompt = _build_scoring_prompt(transcript, target_role, "svi")
    dyad_id = transcript.get("dyad_id", "unknown")
    required_keys = ["instrumental", "self", "process", "relationship"]

    results = {}
    raw = _score_with_openai(
        "gpt-4o",
        SVI_SYSTEM,
        user_prompt,
        dyad_id,
        "svi_gpt4o",
        logs_dir,
    )
    results["gpt-4o"] = _parse_json_response(raw, required_keys)

    raw = _score_with_anthropic(
        "claude-haiku-4-5",
        SVI_SYSTEM,
        user_prompt,
        dyad_id,
        "svi_haiku",
        logs_dir,
    )
    results["claude-haiku-4-5"] = _parse_json_response(raw, required_keys)

    return results


def compute_mean_across_scorers(
    scores_by_scorer: dict[str, dict[str, float]],
    metric: str,
) -> float:
    """Compute the mean of a metric across all scorers."""
    values = [s[metric] for s in scores_by_scorer.values() if metric in s]
    if not values:
        raise ValueError(f"No scorer returned metric '{metric}'.")
    return sum(values) / len(values)
