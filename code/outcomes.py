"""outcomes.py — deterministic outcome computation from negotiation transcripts.

Pure functions, zero API calls, fully unit-testable.

Given a transcript dict (from negotiation_runner.py) and a scenario's payoff
tables, computes:
  - deal (bool)
  - deal_terms (dict | None)
  - value_claimed_a (float): own surplus vs BATNA for agent_a
  - value_claimed_b (float): own surplus vs BATNA for agent_b
  - value_created (float | None): joint points (integrative only)
  - split (float | None): agent_a share of joint value (integrative)
  - notes (list[str]): any warnings / edge-cases

Impasse handling: if no deal, both agents receive their BATNA value.
For distributive: BATNA = 0 surplus (they buy/sell elsewhere at reservation price).
For integrative: BATNA = batna_value from scenario (200 pts in our scenarios).
"""

from __future__ import annotations

from typing import Any

# ---------------------------------------------------------------------------
# Payoff lookup helpers
# ---------------------------------------------------------------------------


def _lookup_issue_points(
    payoff_card: dict[str, dict[str, Any]],
    issue: str,
    value: Any,
) -> float:
    """Look up points for one issue option.

    Supports int and float keys stored as either int/float or str.
    Raises KeyError if issue not in card or value not in options.
    """
    if issue not in payoff_card:
        raise KeyError(
            f"Issue '{issue}' not found in payoff card. Available: {list(payoff_card)}"
        )
    options: dict = payoff_card[issue]["options"]
    # Normalize: try direct lookup first, then cast
    if value in options:
        return float(options[value])
    # Try numeric normalization
    try:
        v_int = int(value)
        if v_int in options:
            return float(options[v_int])
    except (ValueError, TypeError):
        pass
    try:
        v_float = float(value)
        if v_float in options:
            return float(options[v_float])
    except (ValueError, TypeError):
        pass
    # Try string key
    v_str = str(value)
    if v_str in options:
        return float(options[v_str])
    raise KeyError(
        f"Value {value!r} not found in payoff card for issue '{issue}'. "
        f"Available: {list(options)}"
    )


def compute_total_points(
    payoff_card: dict[str, dict[str, Any]],
    deal_terms: dict[str, Any],
) -> float:
    """Sum points across all issues for a given deal bundle."""
    total = 0.0
    for issue, card_entry in payoff_card.items():
        if issue not in deal_terms:
            raise KeyError(f"Deal terms missing issue '{issue}'.")
        total += _lookup_issue_points(payoff_card, issue, deal_terms[issue])
    return total


# ---------------------------------------------------------------------------
# Distributive outcome
# ---------------------------------------------------------------------------


def compute_distributive_outcome(
    transcript: dict[str, Any],
    scenario: dict[str, Any],
    role_a: str,
    role_b: str,
) -> dict[str, Any]:
    """Compute outcomes for a distributive (single-issue) scenario.

    transcript keys expected:
      - deal (bool)
      - deal_terms (dict | None): e.g. {"price": 360}
      - final_offer (dict | None): last offer if no deal

    scenario keys expected (from chair.yaml parsed):
      - roles: list of {id, reservation_price, batna_value, private_payoff: {formula}}
      - issue: {name}

    Returns outcome dict.
    """
    notes: list[str] = []
    deal: bool = bool(transcript.get("deal", False))
    deal_terms: dict | None = transcript.get("deal_terms")

    # Build role lookup
    role_lookup: dict[str, dict] = {}
    for r in scenario.get("roles", []):
        role_lookup[r["id"]] = r

    if role_a not in role_lookup:
        raise ValueError(f"Role '{role_a}' not in scenario roles: {list(role_lookup)}")
    if role_b not in role_lookup:
        raise ValueError(f"Role '{role_b}' not in scenario roles: {list(role_lookup)}")

    role_a_data = role_lookup[role_a]
    role_b_data = role_lookup[role_b]

    issue_name = scenario["issue"]["name"]

    if deal and deal_terms is not None:
        price = float(deal_terms.get(issue_name, deal_terms.get("price", 0)))
        res_a = float(role_a_data["reservation_price"])
        res_b = float(role_b_data["reservation_price"])

        # For buyer: surplus = reservation_price - price; for seller: price - reservation_price
        # We detect buyer/seller by which role has higher reservation_price (buyer pays up to res_a)
        # Generically: if role_a is buyer, res_a > price expected; surplus_a = res_a - price
        # if role_a is seller, res_b > price expected; surplus_a = price - res_a
        # We use a simple heuristic: if role has "buyer" in id, it's the buyer; else seller.
        # Fallback: if res_a > res_b, role_a is buyer.
        if "buyer" in role_a.lower() or (
            res_a > res_b and "seller" not in role_a.lower()
        ):
            surplus_a = res_a - price  # buyer: pays less than max = surplus
            surplus_b = price - res_b  # seller: gets more than min = surplus
        else:
            surplus_a = price - res_a  # seller: gets more than min
            surplus_b = res_b - price  # buyer: pays less than max

        # Clip negative surplus with a note (deal outside ZOPA)
        if surplus_a < 0:
            notes.append(
                f"Agent A ({role_a}) surplus negative ({surplus_a:.1f}) — deal outside ZOPA?"
            )
        if surplus_b < 0:
            notes.append(
                f"Agent B ({role_b}) surplus negative ({surplus_b:.1f}) — deal outside ZOPA?"
            )

        return {
            "deal": True,
            "deal_terms": deal_terms,
            "value_claimed_a": surplus_a,
            "value_claimed_b": surplus_b,
            "value_created": None,  # not meaningful for distributive
            "split": (
                surplus_a / (surplus_a + surplus_b)
                if (surplus_a + surplus_b) > 0
                else None
            ),
            "scenario_type": "distributive",
            "notes": notes,
        }
    else:
        # Impasse: both take BATNA
        batna_a = float(role_a_data.get("batna_value", 0))
        batna_b = float(role_b_data.get("batna_value", 0))
        notes.append("Impasse: both agents take BATNA.")
        return {
            "deal": False,
            "deal_terms": None,
            "value_claimed_a": batna_a,
            "value_claimed_b": batna_b,
            "value_created": None,
            "split": None,
            "scenario_type": "distributive",
            "notes": notes,
        }


# ---------------------------------------------------------------------------
# Integrative outcome
# ---------------------------------------------------------------------------


def compute_integrative_outcome(
    transcript: dict[str, Any],
    scenario: dict[str, Any],
    role_a: str,
    role_b: str,
) -> dict[str, Any]:
    """Compute outcomes for an integrative (multi-issue) scenario.

    transcript keys expected:
      - deal (bool)
      - deal_terms (dict | None): e.g. {"rent": 1700, "lease": 24, "repairs": 1200}

    scenario keys expected (from rental.yaml / offer.yaml parsed):
      - roles: list of {id, private_payoff_card, batna_value}

    Returns outcome dict with value_claimed, value_created (joint points), split.
    """
    notes: list[str] = []
    deal: bool = bool(transcript.get("deal", False))
    deal_terms: dict | None = transcript.get("deal_terms")

    # Build role lookup
    role_lookup: dict[str, dict] = {}
    for r in scenario.get("roles", []):
        role_lookup[r["id"]] = r

    if role_a not in role_lookup:
        raise ValueError(f"Role '{role_a}' not in scenario roles: {list(role_lookup)}")
    if role_b not in role_lookup:
        raise ValueError(f"Role '{role_b}' not in scenario roles: {list(role_lookup)}")

    role_a_data = role_lookup[role_a]
    role_b_data = role_lookup[role_b]

    batna_a = float(role_a_data.get("batna_value", 200))
    batna_b = float(role_b_data.get("batna_value", 200))

    if deal and deal_terms is not None:
        card_a = role_a_data["private_payoff_card"]
        card_b = role_b_data["private_payoff_card"]

        try:
            pts_a = compute_total_points(card_a, deal_terms)
        except KeyError as e:
            notes.append(f"Payoff lookup error for {role_a}: {e}")
            pts_a = batna_a  # fallback to BATNA on lookup error

        try:
            pts_b = compute_total_points(card_b, deal_terms)
        except KeyError as e:
            notes.append(f"Payoff lookup error for {role_b}: {e}")
            pts_b = batna_b

        joint = pts_a + pts_b
        split = pts_a / joint if joint > 0 else None

        # Value claimed = own points vs BATNA (surplus above walkaway)
        surplus_a = pts_a - batna_a
        surplus_b = pts_b - batna_b

        if pts_a < batna_a:
            notes.append(
                f"Agent A ({role_a}) accepted a deal below BATNA "
                f"({pts_a:.1f} < {batna_a:.1f})."
            )
        if pts_b < batna_b:
            notes.append(
                f"Agent B ({role_b}) accepted a deal below BATNA "
                f"({pts_b:.1f} < {batna_b:.1f})."
            )

        return {
            "deal": True,
            "deal_terms": deal_terms,
            "points_a": pts_a,
            "points_b": pts_b,
            "value_claimed_a": surplus_a,
            "value_claimed_b": surplus_b,
            "value_created": joint,
            "split": split,
            "scenario_type": "integrative",
            "notes": notes,
        }
    else:
        # Impasse: both take BATNA
        notes.append("Impasse: both agents take BATNA.")
        return {
            "deal": False,
            "deal_terms": None,
            "points_a": batna_a,
            "points_b": batna_b,
            "value_claimed_a": 0.0,  # surplus vs BATNA = 0 at BATNA
            "value_claimed_b": 0.0,
            "value_created": batna_a + batna_b,  # joint "value" at impasse
            "split": batna_a / (batna_a + batna_b) if (batna_a + batna_b) > 0 else None,
            "scenario_type": "integrative",
            "notes": notes,
        }


# ---------------------------------------------------------------------------
# Unified dispatcher
# ---------------------------------------------------------------------------


def compute_outcome(
    transcript: dict[str, Any],
    scenario: dict[str, Any],
    role_a: str,
    role_b: str,
) -> dict[str, Any]:
    """Dispatch to the appropriate outcome function based on scenario type.

    Args:
        transcript: output dict from negotiation_runner.run_dyad()
        scenario: parsed YAML dict for the scenario
        role_a: role id for agent A (e.g. "buyer", "tenant", "candidate")
        role_b: role id for agent B (e.g. "seller", "landlord", "recruiter")

    Returns:
        outcome dict with keys: deal, deal_terms, value_claimed_a, value_claimed_b,
        value_created, split, scenario_type, notes.
    """
    stype = scenario.get("type", "integrative")
    if stype == "distributive":
        return compute_distributive_outcome(transcript, scenario, role_a, role_b)
    else:
        return compute_integrative_outcome(transcript, scenario, role_a, role_b)


# ---------------------------------------------------------------------------
# SVI (Subjective Value Inventory) aggregation — deterministic post-scoring
# ---------------------------------------------------------------------------


def aggregate_svi_scores(svi_dict: dict[str, float]) -> float:
    """Aggregate the 4 SVI facets into a single mean score.

    SVI facets (each 0-100 from the LLM scorer):
      - instrumental: did you get what you wanted?
      - self: did you feel good about your own performance?
      - process: did you feel good about the negotiation process?
      - relationship: how do you feel about your relationship with the counterpart?

    Returns the arithmetic mean of the four facets.
    Raises ValueError if any facet is missing.
    """
    required = ["instrumental", "self", "process", "relationship"]
    for f in required:
        if f not in svi_dict:
            raise ValueError(
                f"SVI facet '{f}' missing from dict. Got: {list(svi_dict)}"
            )
    return sum(svi_dict[f] for f in required) / 4.0


# ---------------------------------------------------------------------------
# ICC(2,1) computation — two-way random effects, absolute agreement
# ---------------------------------------------------------------------------


def compute_icc_2_1(
    ratings_scorer1: list[float],
    ratings_scorer2: list[float],
) -> dict[str, float]:
    """Compute ICC(2,1) between two raters over a set of targets.

    ICC(2,1): two-way random effects, single measures, absolute agreement.
    Formula follows Shrout & Fleiss (1979) and McGraw & Wong (1996).

    Args:
        ratings_scorer1: list of scores from scorer 1 (length n)
        ratings_scorer2: list of scores from scorer 2 (same length n)

    Returns dict with:
        icc: the ICC(2,1) estimate
        n_targets: number of targets scored
        mean_s1: mean of scorer 1
        mean_s2: mean of scorer 2
    """
    n = len(ratings_scorer1)
    if n != len(ratings_scorer2):
        raise ValueError("Rating lists must be the same length.")
    if n < 2:
        raise ValueError("Need at least 2 targets to compute ICC.")

    k = 2  # number of raters

    # Grand mean
    all_r = ratings_scorer1 + ratings_scorer2
    grand_mean = sum(all_r) / len(all_r)

    # Mean for each target (row mean)
    row_means = [(ratings_scorer1[i] + ratings_scorer2[i]) / k for i in range(n)]

    # Mean for each rater (column mean)
    mean_s1 = sum(ratings_scorer1) / n
    mean_s2 = sum(ratings_scorer2) / n
    col_means = [mean_s1, mean_s2]

    # SS between subjects (rows)
    ss_r = k * sum((row_means[i] - grand_mean) ** 2 for i in range(n))

    # SS between raters (columns)
    ss_c = n * sum((col_means[j] - grand_mean) ** 2 for j in range(k))

    # SS total
    ss_total = sum(
        (ratings_scorer1[i] - grand_mean) ** 2 + (ratings_scorer2[i] - grand_mean) ** 2
        for i in range(n)
    )

    # SS error (residual)
    ss_e = ss_total - ss_r - ss_c

    # Degrees of freedom
    df_r = n - 1
    df_c = k - 1
    df_e = (n - 1) * (k - 1)

    # Mean squares
    ms_r = ss_r / df_r if df_r > 0 else 0.0
    ms_c = ss_c / df_c if df_c > 0 else 0.0
    ms_e = ss_e / df_e if df_e > 0 else 0.0

    # ICC(2,1) absolute agreement
    denom = ms_r + (k - 1) * ms_e + (k / n) * (ms_c - ms_e)
    icc = (ms_r - ms_e) / denom if denom > 0 else 0.0

    return {
        "icc": round(icc, 4),
        "n_targets": n,
        "mean_s1": round(mean_s1, 3),
        "mean_s2": round(mean_s2, 3),
        "ms_r": round(ms_r, 4),
        "ms_e": round(ms_e, 4),
        "ms_c": round(ms_c, 4),
    }
