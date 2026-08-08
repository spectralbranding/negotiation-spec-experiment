"""test_outcomes.py — pytest unit tests for outcomes.py.

All tests are deterministic and make ZERO API calls.
Hand-computed expected values are derived from the scenario YAML payoff tables.

Run:
    uv run pytest code/test_outcomes.py -v
"""

import math
import sys
from pathlib import Path

import pytest

# Add parent dir to path so outcomes.py is importable
sys.path.insert(0, str(Path(__file__).resolve().parent))

from outcomes import (
    aggregate_svi_scores,
    compute_distributive_outcome,
    compute_icc_2_1,
    compute_integrative_outcome,
    compute_outcome,
    compute_total_points,
    _lookup_issue_points,
)

# ---------------------------------------------------------------------------
# Payoff card fixtures (derived from scenario YAMLs)
# ---------------------------------------------------------------------------

# Rental scenario — tenant payoff card (matching rental.yaml)
TENANT_CARD = {
    "rent_monthly_usd": {
        "options": {1600: 300, 1700: 240, 1800: 160, 1900: 80, 2000: 0, 2100: -40}
    },
    "lease_length_months": {"options": {6: 80, 9: 70, 12: 60, 15: 50, 18: 40, 24: 20}},
    "repair_allowance_usd": {
        "options": {0: 0, 300: 60, 600: 120, 900: 180, 1200: 240, 1500: 280}
    },
}

LANDLORD_CARD = {
    "rent_monthly_usd": {
        "options": {1600: 0, 1700: 80, 1800: 160, 1900: 240, 2000: 300, 2100: 340}
    },
    "lease_length_months": {
        "options": {6: 0, 9: 40, 12: 100, 15: 160, 18: 240, 24: 300}
    },
    "repair_allowance_usd": {
        "options": {0: 80, 300: 60, 600: 40, 900: 20, 1200: 0, 1500: -20}
    },
}

# Offer scenario — candidate and recruiter payoff cards (matching offer.yaml)
CANDIDATE_CARD = {
    "salary_usd_annual": {
        "options": {
            95000: 0,
            100000: 50,
            105000: 100,
            110000: 150,
            115000: 250,
            120000: 320,
            125000: 380,
        }
    },
    "remote_days_per_week": {"options": {0: 0, 1: 40, 2: 80, 3: 120, 4: 160, 5: 200}},
    "start_weeks": {"options": {1: 0, 2: 20, 3: 30, 4: 50, 6: 60, 8: 80, 12: 100}},
}

RECRUITER_CARD = {
    "salary_usd_annual": {
        "options": {
            95000: 220,
            100000: 180,
            105000: 140,
            110000: 110,
            115000: 60,
            120000: 20,
            125000: 0,
        }
    },
    "remote_days_per_week": {"options": {0: 120, 1: 100, 2: 80, 3: 60, 4: 40, 5: 20}},
    "start_weeks": {"options": {1: 300, 2: 280, 3: 240, 4: 180, 6: 80, 8: 20, 12: 0}},
}

# Scenario dicts (minimal, matching what compute_outcome expects)
RENTAL_SCENARIO = {
    "scenario_id": "rental",
    "type": "integrative",
    "roles": [
        {"id": "tenant", "private_payoff_card": TENANT_CARD, "batna_value": 200},
        {"id": "landlord", "private_payoff_card": LANDLORD_CARD, "batna_value": 200},
    ],
}

OFFER_SCENARIO = {
    "scenario_id": "offer",
    "type": "integrative",
    "roles": [
        {"id": "candidate", "private_payoff_card": CANDIDATE_CARD, "batna_value": 150},
        {"id": "recruiter", "private_payoff_card": RECRUITER_CARD, "batna_value": 150},
    ],
}

CHAIR_SCENARIO = {
    "scenario_id": "chair",
    "type": "distributive",
    "issue": {"name": "price"},
    "roles": [
        {"id": "buyer", "reservation_price": 420, "batna_value": 0},
        {"id": "seller", "reservation_price": 300, "batna_value": 0},
    ],
}


# ---------------------------------------------------------------------------
# _lookup_issue_points
# ---------------------------------------------------------------------------


class TestLookupIssuePoints:
    def test_exact_int_key(self):
        assert _lookup_issue_points(TENANT_CARD, "rent_monthly_usd", 1700) == 240.0

    def test_value_as_str_resolved(self):
        # value passed as string "1700" should resolve to 240
        assert _lookup_issue_points(TENANT_CARD, "rent_monthly_usd", "1700") == 240.0

    def test_negative_value(self):
        # 2100 gives -40 for tenant
        assert _lookup_issue_points(TENANT_CARD, "rent_monthly_usd", 2100) == -40.0

    def test_missing_issue_raises(self):
        with pytest.raises(KeyError, match="not found in payoff card"):
            _lookup_issue_points(TENANT_CARD, "nonexistent_issue", 100)

    def test_missing_value_raises(self):
        with pytest.raises(KeyError, match="not found in payoff card"):
            _lookup_issue_points(TENANT_CARD, "rent_monthly_usd", 9999)


# ---------------------------------------------------------------------------
# compute_total_points
# ---------------------------------------------------------------------------


class TestComputeTotalPoints:
    def test_pareto_optimal_tenant(self):
        # Pareto-optimal: rent=1700, lease=24, repairs=1200
        # tenant: 240 + 20 + 240 = 500
        deal = {
            "rent_monthly_usd": 1700,
            "lease_length_months": 24,
            "repair_allowance_usd": 1200,
        }
        assert compute_total_points(TENANT_CARD, deal) == 500.0

    def test_pareto_optimal_landlord(self):
        # landlord: 80 + 300 + 0 = 380
        deal = {
            "rent_monthly_usd": 1700,
            "lease_length_months": 24,
            "repair_allowance_usd": 1200,
        }
        assert compute_total_points(LANDLORD_CARD, deal) == 380.0

    def test_equal_split_bundle_tenant(self):
        # (1800, 12, 600): tenant = 160 + 60 + 120 = 340
        deal = {
            "rent_monthly_usd": 1800,
            "lease_length_months": 12,
            "repair_allowance_usd": 600,
        }
        assert compute_total_points(TENANT_CARD, deal) == 340.0

    def test_equal_split_bundle_landlord(self):
        # (1800, 12, 600): landlord = 160 + 100 + 40 = 300
        deal = {
            "rent_monthly_usd": 1800,
            "lease_length_months": 12,
            "repair_allowance_usd": 600,
        }
        assert compute_total_points(LANDLORD_CARD, deal) == 300.0

    def test_offer_pareto_candidate(self):
        # (115000, 4 remote, 2 start): 250 + 160 + 20 = 430
        deal = {
            "salary_usd_annual": 115000,
            "remote_days_per_week": 4,
            "start_weeks": 2,
        }
        assert compute_total_points(CANDIDATE_CARD, deal) == 430.0

    def test_offer_pareto_recruiter(self):
        # (115000, 4 remote, 2 start): 60 + 40 + 280 = 380
        deal = {
            "salary_usd_annual": 115000,
            "remote_days_per_week": 4,
            "start_weeks": 2,
        }
        assert compute_total_points(RECRUITER_CARD, deal) == 380.0

    def test_missing_issue_in_deal_raises(self):
        deal = {"rent_monthly_usd": 1700, "lease_length_months": 12}
        # missing repair_allowance_usd
        with pytest.raises(KeyError, match="Deal terms missing issue"):
            compute_total_points(TENANT_CARD, deal)


# ---------------------------------------------------------------------------
# compute_distributive_outcome
# ---------------------------------------------------------------------------


class TestDistributiveOutcome:
    def test_nash_split_deal(self):
        # Deal at Nash price $360: buyer surplus = 60, seller surplus = 60
        transcript = {"deal": True, "deal_terms": {"price": 360}}
        out = compute_distributive_outcome(
            transcript, CHAIR_SCENARIO, "buyer", "seller"
        )
        assert out["deal"] is True
        assert out["value_claimed_a"] == pytest.approx(60.0)
        assert out["value_claimed_b"] == pytest.approx(60.0)
        assert out["split"] == pytest.approx(0.5)
        assert out["value_created"] is None
        assert out["scenario_type"] == "distributive"

    def test_buyer_favored_deal(self):
        # Deal at $300 (seller's floor): buyer surplus = 120, seller surplus = 0
        transcript = {"deal": True, "deal_terms": {"price": 300}}
        out = compute_distributive_outcome(
            transcript, CHAIR_SCENARIO, "buyer", "seller"
        )
        assert out["value_claimed_a"] == pytest.approx(120.0)
        assert out["value_claimed_b"] == pytest.approx(0.0)

    def test_seller_favored_deal(self):
        # Deal at $420 (buyer's ceiling): buyer surplus = 0, seller surplus = 120
        transcript = {"deal": True, "deal_terms": {"price": 420}}
        out = compute_distributive_outcome(
            transcript, CHAIR_SCENARIO, "buyer", "seller"
        )
        assert out["value_claimed_a"] == pytest.approx(0.0)
        assert out["value_claimed_b"] == pytest.approx(120.0)

    def test_impasse(self):
        # No deal: both take BATNA (0 surplus in distributive scenario)
        transcript = {"deal": False, "deal_terms": None}
        out = compute_distributive_outcome(
            transcript, CHAIR_SCENARIO, "buyer", "seller"
        )
        assert out["deal"] is False
        assert out["value_claimed_a"] == 0.0
        assert out["value_claimed_b"] == 0.0
        assert "Impasse" in out["notes"][0]

    def test_role_reversed(self):
        # Seller is agent A, buyer is agent B
        transcript = {"deal": True, "deal_terms": {"price": 360}}
        out = compute_distributive_outcome(
            transcript, CHAIR_SCENARIO, "seller", "buyer"
        )
        assert out["value_claimed_a"] == pytest.approx(60.0)  # seller surplus
        assert out["value_claimed_b"] == pytest.approx(60.0)  # buyer surplus


# ---------------------------------------------------------------------------
# compute_integrative_outcome
# ---------------------------------------------------------------------------


class TestIntegrativeOutcome:
    def test_pareto_optimal_rental(self):
        # Pareto bundle: (1700, 24, 1200) → tenant=500, landlord=380, joint=880
        transcript = {
            "deal": True,
            "deal_terms": {
                "rent_monthly_usd": 1700,
                "lease_length_months": 24,
                "repair_allowance_usd": 1200,
            },
        }
        out = compute_integrative_outcome(
            transcript, RENTAL_SCENARIO, "tenant", "landlord"
        )
        assert out["deal"] is True
        assert out["points_a"] == pytest.approx(500.0)
        assert out["points_b"] == pytest.approx(380.0)
        assert out["value_created"] == pytest.approx(880.0)
        assert out["value_claimed_a"] == pytest.approx(300.0)  # 500 - 200 BATNA
        assert out["value_claimed_b"] == pytest.approx(180.0)  # 380 - 200 BATNA
        assert out["split"] == pytest.approx(500.0 / 880.0)

    def test_equal_split_rental(self):
        # (1800, 12, 600) → tenant=340, landlord=300, joint=640
        transcript = {
            "deal": True,
            "deal_terms": {
                "rent_monthly_usd": 1800,
                "lease_length_months": 12,
                "repair_allowance_usd": 600,
            },
        }
        out = compute_integrative_outcome(
            transcript, RENTAL_SCENARIO, "tenant", "landlord"
        )
        assert out["points_a"] == pytest.approx(340.0)
        assert out["points_b"] == pytest.approx(300.0)
        assert out["value_created"] == pytest.approx(640.0)

    def test_impasse_rental(self):
        # Impasse: both take BATNA (200 pts), value_created = 400
        transcript = {"deal": False, "deal_terms": None}
        out = compute_integrative_outcome(
            transcript, RENTAL_SCENARIO, "tenant", "landlord"
        )
        assert out["deal"] is False
        assert out["value_claimed_a"] == 0.0
        assert out["value_claimed_b"] == 0.0
        assert out["value_created"] == pytest.approx(400.0)  # 200 + 200

    def test_offer_pareto(self):
        # (115000, 4 remote, 2 start): candidate=430, recruiter=380, joint=810
        transcript = {
            "deal": True,
            "deal_terms": {
                "salary_usd_annual": 115000,
                "remote_days_per_week": 4,
                "start_weeks": 2,
            },
        }
        out = compute_integrative_outcome(
            transcript, OFFER_SCENARIO, "candidate", "recruiter"
        )
        assert out["points_a"] == pytest.approx(430.0)
        assert out["points_b"] == pytest.approx(380.0)
        assert out["value_created"] == pytest.approx(810.0)
        assert out["value_claimed_a"] == pytest.approx(280.0)  # 430 - 150 BATNA
        assert out["value_claimed_b"] == pytest.approx(230.0)  # 380 - 150 BATNA

    def test_below_batna_deal_flagged(self):
        # Tenant accepts a terrible deal: 2100 rent (-40) + long lease + no repairs = awful
        transcript = {
            "deal": True,
            "deal_terms": {
                "rent_monthly_usd": 2100,
                "lease_length_months": 24,
                "repair_allowance_usd": 0,
            },
        }
        out = compute_integrative_outcome(
            transcript, RENTAL_SCENARIO, "tenant", "landlord"
        )
        # tenant: -40 + 20 + 0 = -20 (below BATNA of 200)
        assert out["points_a"] == pytest.approx(-20.0)
        assert any("below BATNA" in n for n in out["notes"])

    def test_impasse_offer(self):
        # Offer scenario impasse: BATNA = 150 each
        transcript = {"deal": False, "deal_terms": None}
        out = compute_integrative_outcome(
            transcript, OFFER_SCENARIO, "candidate", "recruiter"
        )
        assert out["deal"] is False
        assert out["value_created"] == pytest.approx(300.0)  # 150 + 150


# ---------------------------------------------------------------------------
# compute_outcome dispatcher
# ---------------------------------------------------------------------------


class TestComputeOutcomeDispatcher:
    def test_dispatches_distributive(self):
        transcript = {"deal": True, "deal_terms": {"price": 360}}
        out = compute_outcome(transcript, CHAIR_SCENARIO, "buyer", "seller")
        assert out["scenario_type"] == "distributive"

    def test_dispatches_integrative(self):
        transcript = {
            "deal": True,
            "deal_terms": {
                "rent_monthly_usd": 1700,
                "lease_length_months": 12,
                "repair_allowance_usd": 600,
            },
        }
        out = compute_outcome(transcript, RENTAL_SCENARIO, "tenant", "landlord")
        assert out["scenario_type"] == "integrative"


# ---------------------------------------------------------------------------
# aggregate_svi_scores
# ---------------------------------------------------------------------------


class TestAggregateSVI:
    def test_mean_of_four(self):
        svi = {"instrumental": 80, "self": 70, "process": 60, "relationship": 50}
        assert aggregate_svi_scores(svi) == pytest.approx(65.0)

    def test_all_same(self):
        svi = {"instrumental": 75, "self": 75, "process": 75, "relationship": 75}
        assert aggregate_svi_scores(svi) == pytest.approx(75.0)

    def test_missing_facet_raises(self):
        svi = {"instrumental": 80, "self": 70, "process": 60}
        with pytest.raises(ValueError, match="SVI facet 'relationship' missing"):
            aggregate_svi_scores(svi)


# ---------------------------------------------------------------------------
# compute_icc_2_1
# ---------------------------------------------------------------------------


class TestICC21:
    def test_perfect_agreement(self):
        s1 = [10.0, 20.0, 30.0, 40.0, 50.0]
        s2 = [10.0, 20.0, 30.0, 40.0, 50.0]
        result = compute_icc_2_1(s1, s2)
        assert result["icc"] == pytest.approx(1.0, abs=1e-3)

    def test_perfect_disagreement_is_low(self):
        # One scorer always says 100, other always says 0 — no between-subject variance
        # relative to within-subject variance
        s1 = [100.0, 100.0, 100.0, 100.0]
        s2 = [0.0, 0.0, 0.0, 0.0]
        result = compute_icc_2_1(s1, s2)
        # ICC should be low/negative — scores provide no agreement on target rankings
        assert result["icc"] < 0.5

    def test_known_value(self):
        # Hand-computed: two raters, 4 targets
        # Rater 1: [1, 2, 3, 4]; Rater 2: [2, 3, 4, 5]
        # Perfect rank agreement, constant 1-point shift → ICC close to 1 (rank) but
        # absolute agreement ICC(2,1) is lower due to systematic bias.
        s1 = [1.0, 2.0, 3.0, 4.0]
        s2 = [2.0, 3.0, 4.0, 5.0]
        result = compute_icc_2_1(s1, s2)
        # ICC(2,1) absolute agreement with systematic bias should be moderate
        # The exact value: grand_mean=3, row_means=[1.5,2.5,3.5,4.5], col_means=[2.5,3.5]
        # ss_r = 2 * [(1.5-3)^2+(2.5-3)^2+(3.5-3)^2+(4.5-3)^2] = 2*[2.25+0.25+0.25+2.25] = 10
        # ss_c = 4 * [(2.5-3)^2+(3.5-3)^2] = 4*[0.25+0.25] = 2
        # ss_total = (1-3)^2+(2-3)^2+(3-3)^2+(4-3)^2 + (2-3)^2+(3-3)^2+(4-3)^2+(5-3)^2
        #          = 4+1+0+1 + 1+0+1+4 = 12
        # ss_e = 12-10-2 = 0
        # ms_r = 10/3, ms_c = 2/1 = 2, ms_e = 0/3 = 0
        # denom = ms_r + 1*ms_e + (2/4)*(ms_c - ms_e) = 10/3 + 0 + 0.5*2 = 10/3 + 1 = 13/3
        # icc = (10/3 - 0) / (13/3) = 10/13 ≈ 0.769
        assert result["icc"] == pytest.approx(10.0 / 13.0, abs=1e-3)

    def test_unequal_length_raises(self):
        with pytest.raises(ValueError, match="same length"):
            compute_icc_2_1([1.0, 2.0], [1.0])

    def test_too_few_raises(self):
        with pytest.raises(ValueError, match="at least 2"):
            compute_icc_2_1([5.0], [5.0])

    def test_n_targets_reported(self):
        s1 = [10.0, 20.0, 30.0]
        s2 = [12.0, 18.0, 32.0]
        result = compute_icc_2_1(s1, s2)
        assert result["n_targets"] == 3
        assert math.isfinite(result["icc"])
