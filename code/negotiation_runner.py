"""negotiation_runner.py — runs ONE dyad (two agents, one scenario).

Conducts a multi-turn alternating dialogue between two agents.
Each turn = one model call wrapped through llm_call_logger.

Offer protocol (STRUCTURED):
    Agent emits offers using one of these exact patterns:
        Distributive (single-issue):
            OFFER: {"price": <number>}
        Integrative (multi-issue, rental):
            OFFER: {"rent_monthly_usd": <n>, "lease_length_months": <n>, "repair_allowance_usd": <n>}
        Integrative (multi-issue, offer):
            OFFER: {"salary_usd_annual": <n>, "remote_days_per_week": <n>, "start_weeks": <n>}
        Acceptance:
            ACCEPT
    Agents are instructed to always include a parseable OFFER in each message
    until they say ACCEPT or the round cap is reached.

    On K rounds without ACCEPT → impasse (both take BATNA).

Mock mode (mock=True):
    Returns deterministic synthetic turns/offers with ZERO API calls.
    Seed is derived from dyad_id + scenario_id so results are reproducible.

Usage (production):
    from negotiation_runner import run_dyad
    transcript = run_dyad(
        scenario=parsed_yaml_dict,
        role_a_id="buyer",
        role_b_id="seller",
        agent_a_config={"condition": "SPEC_NOCOT", "model": "gpt-4o-mini"},
        agent_b_config={"condition": "WARMTH", "model": "gpt-4o-mini"},
        dyad_id="chair_SPEC_NOCOT_WARMTH_buyer_seller_r00",
        logs_dir=Path("logs"),
    )

Usage (dry-run, zero API):
    transcript = run_dyad(..., mock=True)
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Path setup — allow importing llm_call_logger from [internal path removed]
# ---------------------------------------------------------------------------
REPO_ROOT = Path(__file__).resolve().parents[3]
RESEARCH_CODE = REPO_ROOT / "research" / "code"
EXPERIMENT_DIR = Path(__file__).resolve().parents[1]
PROMPTS_DIR = EXPERIMENT_DIR / "prompts"
sys.path.insert(0, str(RESEARCH_CODE))


# ---------------------------------------------------------------------------
# Offer parsing
# ---------------------------------------------------------------------------

OFFER_PATTERN = re.compile(r"OFFER:\s*(\{[^}]+\})", re.IGNORECASE | re.DOTALL)
# Robust ACCEPT: must be a standalone token — the word "ACCEPT" on its own line
# or surrounded by whitespace/punctuation, NOT embedded in phrases like "I cannot accept".
# Strategy: require "ACCEPT" to appear either alone on a line, or at the start of
# a line/sentence, or immediately after sentence-ending punctuation — not mid-clause.
_ACCEPT_STANDALONE = re.compile(
    r"(?:^|\n|(?<=[.!?])\s*)\s*ACCEPT\s*(?:[.!?\n]|$)",
    re.IGNORECASE | re.MULTILINE,
)
# Secondary: bare "ACCEPT" as the entire (stripped) text after CoT removal.
_ACCEPT_BARE = re.compile(r"^\s*ACCEPT\s*$", re.IGNORECASE | re.MULTILINE)


def _strip_cot(text: str) -> str:
    """Strip <think>...</think> blocks from agent output before parsing/display."""
    return re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()


def parse_offer(text: str) -> dict | None:
    """Extract the first OFFER: {...} from agent text. Returns None if none found."""
    clean = _strip_cot(text)
    m = OFFER_PATTERN.search(clean)
    if m:
        try:
            raw = m.group(1)
            # Allow numeric values without quotes
            parsed = json.loads(raw)
            return parsed
        except json.JSONDecodeError:
            # Try relaxed parse: replace single quotes
            try:
                relaxed = m.group(1).replace("'", '"')
                return json.loads(relaxed)
            except json.JSONDecodeError:
                return None
    return None


def is_acceptance(text: str) -> bool:
    """Return True if the agent text contains an unambiguous standalone ACCEPT signal.

    Matches:
      - "ACCEPT" alone on a line (most common harness pattern)
      - "ACCEPT." / "ACCEPT!" at end of line
      - "ACCEPT" at the very start of the text

    Does NOT match "accept" embedded in ordinary prose such as
    "I cannot accept these terms" or "I accept that rent is high."
    """
    clean = _strip_cot(text)
    if _ACCEPT_BARE.search(clean):
        return True
    if _ACCEPT_STANDALONE.search(clean):
        return True
    return False


# ---------------------------------------------------------------------------
# Prompt assembly
# ---------------------------------------------------------------------------


def _load_prompt_body(condition: str) -> str:
    """Load the strategy body for a condition (e.g. 'SPEC_NOCOT')."""
    path = PROMPTS_DIR / f"{condition}.txt"
    if not path.exists():
        raise FileNotFoundError(f"Prompt body not found: {path}")
    return path.read_text().strip()


def _load_harness_preface() -> str:
    path = PROMPTS_DIR / "harness_preface.txt"
    return path.read_text().strip()


def _build_system_prompt(
    condition: str,
    scenario: dict,
    role_id: str,
    max_rounds: int,
) -> str:
    """Build the full system prompt for one agent.

    Structure:
        [harness_preface]

        [condition body — with <RV> / <K> / issue placeholders filled in]

        [role + scenario instructions]
        [payoff card]
        [offer protocol instructions]
    """
    preface = _load_harness_preface()
    body = _load_prompt_body(condition)

    # Find role data
    role_data = next((r for r in scenario["roles"] if r["id"] == role_id), None)
    if role_data is None:
        raise ValueError(f"Role '{role_id}' not found in scenario.")

    # Fill SPEC template placeholders
    if "private_payoff_card" in role_data:
        # Integrative
        card = role_data["private_payoff_card"]
        issues_ranked = sorted(
            card.items(),
            key=lambda kv: -max(kv[1]["options"].values()),
        )
        issue_lines = []
        for rank, (issue_name, issue_data) in enumerate(issues_ranked, 1):
            max_pts = max(issue_data["options"].values())
            issue_lines.append(f"  {rank}. {issue_name} — max points {max_pts}")
        priorities_block = "\n".join(issue_lines)
        rv = str(int(role_data.get("batna_value", 200)))
        body = body.replace("<RV>", rv)
        body = body.replace("<K>", str(max_rounds))
        body = body.replace(
            "  1. <issue_a> — weight <w_a>  (most valuable to you)\n"
            "  2. <issue_b> — weight <w_b>\n"
            "  3. <issue_c> — weight <w_c>",
            priorities_block,
        )
    elif "reservation_price" in role_data:
        # Distributive
        rv = str(int(role_data["reservation_price"]))
        body = body.replace("<RV>", rv)
        body = body.replace("<K>", str(max_rounds))
        body = body.replace(
            "  1. <issue_a> — weight <w_a>  (most valuable to you)\n"
            "  2. <issue_b> — weight <w_b>\n"
            "  3. <issue_c> — weight <w_c>",
            f"  1. price — single issue",
        )

    # Build role description block
    role_label = role_data.get("label", role_id)
    role_desc = role_data.get("description", "").strip()

    # Build payoff card block — FULL numeric table so agents can evaluate any offer.
    if "private_payoff_card" in role_data:
        card = role_data["private_payoff_card"]
        batna_val = role_data.get("batna_value", 200)
        batna_desc = role_data.get("batna_description", "")
        payoff_lines = [
            "YOUR PRIVATE PAYOFF CARD (do not reveal to counterpart):",
            "  To evaluate an offer, sum the points for each issue value below.",
            f"  Your RESERVATION VALUE (minimum acceptable total) = {batna_val} points.",
        ]
        for issue, data in card.items():
            # Sort options for readability
            opts = data["options"]
            try:
                sorted_opts = dict(sorted(opts.items(), key=lambda kv: float(kv[0])))
            except (TypeError, ValueError):
                sorted_opts = opts
            payoff_lines.append(f"  {issue}:")
            for val, pts in sorted_opts.items():
                payoff_lines.append(f"    {val} → {pts} pts")
        payoff_block = "\n".join(payoff_lines)
        payoff_block += (
            f"\nYOUR BATNA: {batna_desc} (worth {batna_val} points to you)\n"
            f"RESERVATION VALUE: {batna_val} points total — "
            "never accept an offer whose total points fall below this."
        )
    else:
        # Distributive
        res = role_data.get("reservation_price", "")
        target = role_data.get("target_price", "")
        payoff_block = (
            f"YOUR RESERVATION PRICE: ${res} (never accept worse than this)\n"
            f"YOUR ASPIRATION PRICE: ${target}\n"
            f"YOUR BATNA: {role_data.get('batna_description', '')}"
        )

    # Build offer protocol instructions + per-turn accept guidance
    scenario_type = scenario.get("type", "integrative")
    if scenario_type == "distributive":
        offer_instr = (
            "OFFER PROTOCOL (MANDATORY):\n"
            "  Every message MUST contain either:\n"
            '    OFFER: {"price": <number>}    (your proposed price)\n'
            "  OR:\n"
            "    ACCEPT\n"
            "  on its own line to accept the counterpart's last stated offer.\n"
            "  NEVER send a message without one of these.\n"
            '  Example: "I propose $350. OFFER: {"price": 350}"\n'
            "ACCEPTANCE RULE: Reply with exactly ACCEPT (on its own line) if the\n"
            "  counterpart's last offer meets or exceeds your reservation price AND\n"
            "  you do not expect a materially better deal in remaining rounds."
        )
    else:
        # Get issue keys from role card
        if "private_payoff_card" in role_data:
            keys = list(role_data["private_payoff_card"].keys())
        else:
            keys = ["issue1", "issue2", "issue3"]
        sample = {k: "<number>" for k in keys}
        offer_instr = (
            "OFFER PROTOCOL (MANDATORY):\n"
            "  Every message MUST contain either:\n"
            f"    OFFER: {json.dumps(sample)}    (your proposed terms)\n"
            "  OR:\n"
            "    ACCEPT\n"
            "  on its own line to accept the counterpart's last stated offer.\n"
            "  NEVER send a message without one of these.\n"
            "ACCEPTANCE RULE: Reply with exactly ACCEPT (on its own line) if the\n"
            "  counterpart's last offer totals >= your reservation value when scored\n"
            "  against your payoff card AND you do not expect a materially better\n"
            "  deal in the remaining rounds. Compute the points before deciding."
        )

    round_info = (
        f"ROUND LIMIT: {max_rounds} rounds total. "
        "If no agreement is reached by then, both parties take their BATNA."
    )

    parts = [
        preface,
        "",
        body,
        "",
        f"=== YOUR ROLE: {role_label} ===",
        role_desc,
        "",
        payoff_block,
        "",
        offer_instr,
        "",
        round_info,
        "",
        f"Scenario: {scenario.get('description', '').strip()}",
    ]
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Mock mode — deterministic synthetic dialogues
# ---------------------------------------------------------------------------


def _mock_seed(dyad_id: str, turn: int) -> int:
    """Derive a deterministic integer seed from dyad_id + turn."""
    h = hashlib.md5(f"{dyad_id}:{turn}".encode()).hexdigest()
    return int(h[:8], 16)


def _mock_offer_for_scenario(scenario: dict, seed: int, role_id: str) -> dict:
    """Generate a deterministic mock offer for a scenario."""
    stype = scenario.get("type", "integrative")
    scenario_id = scenario.get("scenario_id", "unknown")

    if stype == "distributive":
        # Pick a price in ZOPA range deterministically
        prices = [300, 320, 340, 360, 380, 400, 420]
        return {"price": prices[seed % len(prices)]}

    if scenario_id == "rental":
        rents = [1600, 1700, 1800, 1900, 2000]
        leases = [6, 9, 12, 15, 18, 24]
        repairs = [0, 300, 600, 900, 1200, 1500]
        return {
            "rent_monthly_usd": rents[seed % len(rents)],
            "lease_length_months": leases[(seed // 5) % len(leases)],
            "repair_allowance_usd": repairs[(seed // 11) % len(repairs)],
        }

    if scenario_id == "offer":
        salaries = [95000, 100000, 105000, 110000, 115000, 120000, 125000]
        remotes = [0, 1, 2, 3, 4, 5]
        starts = [1, 2, 3, 4, 6, 8, 12]
        return {
            "salary_usd_annual": salaries[seed % len(salaries)],
            "remote_days_per_week": remotes[(seed // 7) % len(remotes)],
            "start_weeks": starts[(seed // 13) % len(starts)],
        }

    # Generic fallback
    return {"value": seed % 100}


def _run_mock_dyad(
    scenario: dict,
    role_a_id: str,
    role_b_id: str,
    agent_a_config: dict,
    agent_b_config: dict,
    dyad_id: str,
    max_rounds: int = 14,
) -> dict[str, Any]:
    """Run a fully deterministic mock dyad with zero API calls."""
    seed_base = _mock_seed(dyad_id, 0)

    turns = []
    last_offer_by: str | None = None
    last_offer: dict | None = None
    deal = False
    deal_terms = None

    # Determine acceptance turn deterministically:
    # Use seed to decide which round (if any) results in ACCEPT
    accept_round = (seed_base % max_rounds) + 1  # 1..max_rounds
    # ~70% of dyads reach a deal (matches expected deal rate)
    will_deal = (seed_base % 10) < 7

    roles = [role_a_id, role_b_id]
    agents = [agent_a_config, agent_b_config]

    for round_num in range(1, max_rounds + 1):
        role = roles[(round_num - 1) % 2]
        agent = agents[(round_num - 1) % 2]
        seed = _mock_seed(dyad_id, round_num)

        if will_deal and round_num == accept_round and last_offer is not None:
            # This agent accepts the last offer — ACCEPT on its own line for parser
            text = (
                f"After careful consideration, I agree to the proposed terms.\nACCEPT"
            )
            turns.append(
                {
                    "round": round_num,
                    "role": role,
                    "condition": agent["condition"],
                    "text": text,
                    "parsed_offer": None,
                    "is_acceptance": True,
                    "mock": True,
                }
            )
            deal = True
            deal_terms = last_offer
            break
        else:
            offer = _mock_offer_for_scenario(scenario, seed, role)
            offer_json = json.dumps(offer)
            text = (
                f"[Mock turn {round_num}, {role}, {agent['condition']}] "
                f"I propose the following terms. OFFER: {offer_json}"
            )
            turns.append(
                {
                    "round": round_num,
                    "role": role,
                    "condition": agent["condition"],
                    "text": text,
                    "parsed_offer": offer,
                    "is_acceptance": False,
                    "mock": True,
                }
            )
            last_offer = offer
            last_offer_by = role

    return {
        "dyad_id": dyad_id,
        "scenario_id": scenario.get("scenario_id", "unknown"),
        "scenario_type": scenario.get("type", "integrative"),
        "role_a": role_a_id,
        "role_b": role_b_id,
        "agent_a_condition": agent_a_config["condition"],
        "agent_b_condition": agent_b_config["condition"],
        "model_a": agent_a_config.get("model", "mock"),
        "model_b": agent_b_config.get("model", "mock"),
        "turns": turns,
        "deal": deal,
        "deal_terms": deal_terms,
        "rounds_to_deal": len(turns) if deal else None,
        "mock": True,
    }


# ---------------------------------------------------------------------------
# Live mode — real API calls
# ---------------------------------------------------------------------------


def _build_messages_for_turn(
    turns: list[dict],
    current_role: str,
    system_prompt_a: str,
    system_prompt_b: str,
    role_a_id: str,
    role_b_id: str,
) -> tuple[str, list[dict]]:
    """Build the system prompt and messages array for the current turn.

    OpenAI / Anthropic both use a list of {role: user/assistant, content: ...}.
    We present the conversation from the perspective of the agent whose turn it is:
      - their own previous messages are "assistant"
      - counterpart messages are "user"
    The system prompt is their private instruction.
    """
    if current_role == role_a_id:
        system = system_prompt_a
        my_role = role_a_id
    else:
        system = system_prompt_b
        my_role = role_b_id

    messages: list[dict] = []
    for turn in turns:
        if turn["role"] == my_role:
            messages.append({"role": "assistant", "content": _strip_cot(turn["text"])})
        else:
            messages.append({"role": "user", "content": _strip_cot(turn["text"])})

    # If no messages yet (first turn), add a minimal opener
    if not messages:
        messages.append({"role": "user", "content": "Let's begin the negotiation."})

    return system, messages


def _call_openai(
    model: str,
    system_prompt: str,
    messages: list[dict],
    temperature: float,
    dyad_id: str,
    turn_num: int,
    role: str,
    logs_dir: Path,
) -> str:
    """Make one OpenAI API call, logged via llm_call_logger."""
    try:
        import openai
    except ImportError:
        raise RuntimeError("openai SDK not installed. Run: uv add openai")

    try:
        from llm_call_logger import log_call
    except ImportError:
        raise RuntimeError("llm_call_logger not found.")

    import os

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY not set in environment.")

    client = openai.OpenAI(api_key=api_key, timeout=90.0, max_retries=3)

    # Merge system into messages for OpenAI
    full_messages = [{"role": "system", "content": system_prompt}] + messages

    with log_call(
        phase="negotiation",
        operation=f"turn_{turn_num}_{role}_{dyad_id}",
        operator=model,
        operator_role="orchestrator",
        endpoint="https://api.openai.com/v1/chat/completions",
        sdk_version=f"openai",
        logs_dir=logs_dir,
    ) as logger:
        logger.set_system_prompt(system_prompt)
        user_context = (
            json.dumps(messages[-3:]) if len(messages) > 3 else json.dumps(messages)
        )
        logger.set_user_prompt(user_context)
        logger.set_parameters(
            {
                "model": model,
                "temperature": temperature,
                "max_tokens": 1024,
            }
        )
        response = client.chat.completions.create(
            model=model,
            messages=full_messages,
            temperature=temperature,
            max_tokens=1024,
        )
        logger.capture_response(response)

    return response.choices[0].message.content or ""


def _call_anthropic(
    model: str,
    system_prompt: str,
    messages: list[dict],
    temperature: float,
    dyad_id: str,
    turn_num: int,
    role: str,
    logs_dir: Path,
) -> str:
    """Make one Anthropic API call, logged via llm_call_logger."""
    try:
        import anthropic
    except ImportError:
        raise RuntimeError("anthropic SDK not installed. Run: uv add anthropic")

    try:
        from llm_call_logger import log_call
    except ImportError:
        raise RuntimeError("llm_call_logger not found.")

    import os

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY not set in environment.")

    client = anthropic.Anthropic(api_key=api_key, timeout=90.0, max_retries=3)

    with log_call(
        phase="negotiation",
        operation=f"turn_{turn_num}_{role}_{dyad_id}",
        operator=model,
        operator_role="orchestrator",
        endpoint="https://api.anthropic.com/v1/messages",
        sdk_version=f"anthropic-sdk",
        logs_dir=logs_dir,
    ) as logger:
        logger.set_system_prompt(system_prompt)
        user_context = (
            json.dumps(messages[-3:]) if len(messages) > 3 else json.dumps(messages)
        )
        logger.set_user_prompt(user_context)
        logger.set_parameters(
            {
                "model": model,
                "temperature": temperature,
                "max_tokens": 1024,
            }
        )
        response = client.messages.create(
            model=model,
            system=system_prompt,
            messages=messages,
            temperature=temperature,
            max_tokens=1024,
        )
        logger.capture_response(response)

    return response.content[0].text if response.content else ""


OPENAI_MODELS = {"gpt-4o-mini", "gpt-4o", "gpt-4o-2024-11-20"}
ANTHROPIC_MODELS = {"claude-haiku-4-5", "claude-haiku-4-5-20251001"}
# xAI Grok models: routed via OpenAI-compatible endpoint at api.x.ai/v1.
# GROK_API_KEY is injected by BWS at run time.
GROK_MODELS = {"grok-4.3"}
GROK_BASE_URL = "https://api.x.ai/v1"


def _call_grok(
    model: str,
    system_prompt: str,
    messages: list[dict],
    temperature: float,
    dyad_id: str,
    turn_num: int,
    role: str,
    logs_dir: Path,
) -> str:
    """Make one xAI Grok API call via the OpenAI-compatible endpoint, logged via
    llm_call_logger.

    Grok exposes an OpenAI-compatible chat-completions API at
    ``https://api.x.ai/v1``.  We construct an ``openai.OpenAI`` client with
    ``base_url`` overridden to that endpoint and ``api_key`` read from
    ``GROK_API_KEY`` (injected by BWS).  The call is otherwise identical to
    ``_call_openai``.

    The SCORERS (gpt-4o + claude-haiku-4-5) are UNCHANGED — this branch is only
    reached for the PLAYER model when the model name starts with "grok".
    """
    try:
        import openai
    except ImportError:
        raise RuntimeError("openai SDK not installed. Run: uv add openai")

    try:
        from llm_call_logger import log_call
    except ImportError:
        raise RuntimeError("llm_call_logger not found.")

    import os

    api_key = os.environ.get("GROK_API_KEY")
    if not api_key:
        raise RuntimeError("GROK_API_KEY not set in environment.")

    client = openai.OpenAI(
        api_key=api_key, base_url=GROK_BASE_URL, timeout=90.0, max_retries=3
    )

    # Merge system into messages — same convention as _call_openai.
    full_messages = [{"role": "system", "content": system_prompt}] + messages

    with log_call(
        phase="negotiation",
        operation=f"turn_{turn_num}_{role}_{dyad_id}",
        operator=model,
        operator_role="orchestrator",
        endpoint=f"{GROK_BASE_URL}/chat/completions",
        sdk_version="openai",
        logs_dir=logs_dir,
    ) as logger:
        logger.set_system_prompt(system_prompt)
        user_context = (
            json.dumps(messages[-3:]) if len(messages) > 3 else json.dumps(messages)
        )
        logger.set_user_prompt(user_context)
        logger.set_parameters(
            {
                "model": model,
                "temperature": temperature,
                "max_tokens": 1024,
            }
        )
        response = client.chat.completions.create(
            model=model,
            messages=full_messages,
            temperature=temperature,
            max_tokens=1024,
        )
        logger.capture_response(response)

    return response.choices[0].message.content or ""


def _call_model(
    model: str,
    system_prompt: str,
    messages: list[dict],
    temperature: float,
    dyad_id: str,
    turn_num: int,
    role: str,
    logs_dir: Path,
) -> str:
    """Dispatch model call to the appropriate SDK.

    Routing priority (first match wins):
      1. model starts with "grok" → xAI endpoint via ``_call_grok``
      2. model in OPENAI_MODELS or starts with "gpt-" → ``_call_openai``
      3. model in ANTHROPIC_MODELS or starts with "claude-" → ``_call_anthropic``
      4. unknown → ValueError

    The SCORERS (gpt-4o + claude-haiku-4-5) are always dispatched through paths
    2 and 3; path 1 is only reached for the PLAYER model.
    """
    if model in GROK_MODELS or model.startswith("grok"):
        return _call_grok(
            model,
            system_prompt,
            messages,
            temperature,
            dyad_id,
            turn_num,
            role,
            logs_dir,
        )
    elif model in OPENAI_MODELS or model.startswith("gpt-"):
        return _call_openai(
            model,
            system_prompt,
            messages,
            temperature,
            dyad_id,
            turn_num,
            role,
            logs_dir,
        )
    elif model in ANTHROPIC_MODELS or model.startswith("claude-"):
        return _call_anthropic(
            model,
            system_prompt,
            messages,
            temperature,
            dyad_id,
            turn_num,
            role,
            logs_dir,
        )
    else:
        raise ValueError(
            f"Unknown model: {model!r}. "
            "Add to GROK_MODELS, OPENAI_MODELS, or ANTHROPIC_MODELS."
        )


_FINAL_ROUND_NOTICE = (
    "\n[HARNESS NOTICE — FINAL ROUNDS]: This is one of the last rounds. "
    "If the counterpart's standing offer scores above your reservation value, "
    "you should ACCEPT it now — further counter-offers risk an impasse where "
    "both parties take their BATNA. If no acceptable offer is on the table, "
    "make your best final offer. Write ACCEPT on its own line to accept."
)


def _run_live_dyad(
    scenario: dict,
    role_a_id: str,
    role_b_id: str,
    agent_a_config: dict,
    agent_b_config: dict,
    dyad_id: str,
    max_rounds: int = 14,
    temperature: float = 0.20,
    logs_dir: Path | None = None,
) -> dict[str, Any]:
    """Run a live dyad with real API calls."""
    if logs_dir is None:
        logs_dir = EXPERIMENT_DIR / "logs"

    model_a = agent_a_config["model"]
    model_b = agent_b_config["model"]

    system_a = _build_system_prompt(
        agent_a_config["condition"], scenario, role_a_id, max_rounds
    )
    system_b = _build_system_prompt(
        agent_b_config["condition"], scenario, role_b_id, max_rounds
    )

    turns: list[dict] = []
    last_offer: dict | None = None
    deal = False
    deal_terms = None

    roles = [role_a_id, role_b_id]
    models = [model_a, model_b]
    systems = [system_a, system_b]
    conditions = [agent_a_config["condition"], agent_b_config["condition"]]

    # Final-round threshold: inject forcing notice on the last 2 rounds.
    final_round_threshold = max_rounds - 1

    for round_num in range(1, max_rounds + 1):
        idx = (round_num - 1) % 2
        current_role = roles[idx]
        current_model = models[idx]
        current_system = systems[idx]

        system_prompt, messages = _build_messages_for_turn(
            turns, current_role, system_a, system_b, role_a_id, role_b_id
        )

        # Inject final-round forcing notice into the last user-turn message
        if round_num >= final_round_threshold and messages:
            last_msg = messages[-1]
            if last_msg["role"] == "user":
                messages = messages[:-1] + [
                    {
                        "role": "user",
                        "content": last_msg["content"] + _FINAL_ROUND_NOTICE,
                    }
                ]

        text = _call_model(
            current_model,
            current_system,
            messages,
            temperature,
            dyad_id,
            round_num,
            current_role,
            logs_dir,
        )

        offer = parse_offer(text)
        accepted = is_acceptance(text)

        turns.append(
            {
                "round": round_num,
                "role": current_role,
                "condition": conditions[idx],
                "text": text,
                "parsed_offer": offer,
                "is_acceptance": accepted,
                "mock": False,
            }
        )

        if offer is not None:
            last_offer = offer

        if accepted and last_offer is not None:
            deal = True
            deal_terms = last_offer
            break

    return {
        "dyad_id": dyad_id,
        "scenario_id": scenario.get("scenario_id", "unknown"),
        "scenario_type": scenario.get("type", "integrative"),
        "role_a": role_a_id,
        "role_b": role_b_id,
        "agent_a_condition": agent_a_config["condition"],
        "agent_b_condition": agent_b_config["condition"],
        "model_a": model_a,
        "model_b": model_b,
        "turns": turns,
        "deal": deal,
        "deal_terms": deal_terms,
        "rounds_to_deal": len(turns) if deal else None,
        "mock": False,
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def run_dyad(
    scenario: dict,
    role_a_id: str,
    role_b_id: str,
    agent_a_config: dict,
    agent_b_config: dict,
    dyad_id: str,
    max_rounds: int = 14,
    temperature: float = 0.20,
    logs_dir: Path | None = None,
    mock: bool = False,
) -> dict[str, Any]:
    """Run one negotiation dyad.

    Args:
        scenario: parsed YAML dict for the scenario
        role_a_id: role string for agent A (e.g. "buyer", "tenant")
        role_b_id: role string for agent B (e.g. "seller", "landlord")
        agent_a_config: dict with keys "condition" (str) and "model" (str)
        agent_b_config: dict with keys "condition" (str) and "model" (str)
        dyad_id: unique string identifying this dyad (used for logging + resume)
        max_rounds: maximum number of alternating turns (default 14; K=8 caused
            all-impasse in integrative scenarios — raised to 14 per harness fix)
        temperature: LLM sampling temperature (default 0.20 per base paper)
        logs_dir: Path to write JSONL logs; defaults to experiment/logs/
        mock: if True, use deterministic mock mode (zero API calls)

    Returns:
        transcript dict with turns, parsed_offers, deal, deal_terms.
        Pass to outcomes.compute_outcome() to get scored outcomes.
    """
    if mock:
        return _run_mock_dyad(
            scenario=scenario,
            role_a_id=role_a_id,
            role_b_id=role_b_id,
            agent_a_config=agent_a_config,
            agent_b_config=agent_b_config,
            dyad_id=dyad_id,
            max_rounds=max_rounds,
        )
    else:
        return _run_live_dyad(
            scenario=scenario,
            role_a_id=role_a_id,
            role_b_id=role_b_id,
            agent_a_config=agent_a_config,
            agent_b_config=agent_b_config,
            dyad_id=dyad_id,
            max_rounds=max_rounds,
            temperature=temperature,
            logs_dir=logs_dir,
        )
