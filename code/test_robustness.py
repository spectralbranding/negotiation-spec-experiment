"""test_robustness.py — unit tests for provider error classification, atomic writes,
and offer/accept parsing.

All tests are deterministic and make ZERO API calls.

Tests:
    classify_provider_error — all kind/transient combinations for fake exceptions
    atomic write safety      — .tmp left by a simulated kill is ignored by --resume
    is_acceptance            — standalone ACCEPT required; prose "accept" not matched

Run:
    uv run pytest [internal path removed] -v
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from provider_errors import classify_provider_error

# ---------------------------------------------------------------------------
# Helpers: build fake exception objects
# ---------------------------------------------------------------------------
# We define custom exception subclasses with the right __module__ so the
# classifier sees them as originating from the correct SDK package.


def _make_exc_class(type_name: str, module_name: str):
    """Dynamically create an exception class with given name and module."""
    cls = type(type_name, (Exception,), {})
    cls.__module__ = module_name
    return cls


# Persistent fake exception classes (module-level so isinstance works)
_OpenAIError = _make_exc_class("OpenAIError", "openai")
_AnthropicError = _make_exc_class("AnthropicError", "anthropic")
_HttpxConnectionError = _make_exc_class("ConnectionError", "httpx")
_HttpxTimeoutError = _make_exc_class("TimeoutError", "httpx")
_GenericError = _make_exc_class("APIError", "")


def _make_exc(
    cls,
    status_code: int | None = None,
    code: str = "",
    message: str = "",
    body: str = "",
) -> Exception:
    """Instantiate a fake SDK exception with the given attributes."""
    exc = cls(message or f"Fake {cls.__name__}")
    if status_code is not None:
        exc.status_code = status_code  # type: ignore[attr-defined]
    if code:
        exc.code = code  # type: ignore[attr-defined]
    if message:
        exc.message = message  # type: ignore[attr-defined]
    if body:
        exc.body = body  # type: ignore[attr-defined]
    return exc


def _make_openai_exc(
    status_code: int | None = None,
    code: str = "",
    message: str = "",
    body: str = "",
) -> Exception:
    return _make_exc(
        _OpenAIError, status_code=status_code, code=code, message=message, body=body
    )


def _make_anthropic_exc(
    status_code: int | None = None,
    message: str = "",
    body: str = "",
) -> Exception:
    return _make_exc(
        _AnthropicError, status_code=status_code, message=message, body=body
    )


# ---------------------------------------------------------------------------
# classify_provider_error — NEEDS_DEPOSIT cases
# ---------------------------------------------------------------------------


class TestNeedsDeposit:
    def test_openai_insufficient_quota_code(self):
        exc = _make_openai_exc(
            status_code=429,
            code="insufficient_quota",
            message="You exceeded your current quota",
        )
        info = classify_provider_error(exc)
        assert info["kind"] == "needs_deposit"
        assert info["provider"] == "openai"
        assert info["transient"] is False

    def test_openai_http_402(self):
        exc = _make_openai_exc(status_code=402, message="Payment required")
        info = classify_provider_error(exc)
        assert info["kind"] == "needs_deposit"
        assert info["provider"] == "openai"
        assert info["transient"] is False

    def test_anthropic_http_402(self):
        exc = _make_anthropic_exc(status_code=402, message="Payment required")
        info = classify_provider_error(exc)
        assert info["kind"] == "needs_deposit"
        assert info["provider"] == "anthropic"
        assert info["transient"] is False

    def test_anthropic_credit_balance_too_low(self):
        exc = _make_anthropic_exc(
            message="Your credit balance is too low to make this request."
        )
        info = classify_provider_error(exc)
        assert info["kind"] == "needs_deposit"
        assert info["provider"] == "anthropic"
        assert info["transient"] is False

    def test_anthropic_billing_message_in_body(self):
        exc = _make_anthropic_exc(body="billing error: insufficient credits")
        info = classify_provider_error(exc)
        assert info["kind"] == "needs_deposit"
        assert info["transient"] is False

    def test_anthropic_out_of_credits_message(self):
        exc = _make_anthropic_exc(message="out of credits")
        info = classify_provider_error(exc)
        assert info["kind"] == "needs_deposit"
        assert info["transient"] is False


# ---------------------------------------------------------------------------
# classify_provider_error — AUTH cases
# ---------------------------------------------------------------------------


class TestAuth:
    def test_openai_401(self):
        exc = _make_openai_exc(status_code=401, message="Invalid API key")
        info = classify_provider_error(exc)
        assert info["kind"] == "auth"
        assert info["provider"] == "openai"
        assert info["transient"] is False

    def test_anthropic_403(self):
        exc = _make_anthropic_exc(status_code=403, message="Permission denied")
        info = classify_provider_error(exc)
        assert info["kind"] == "auth"
        assert info["provider"] == "anthropic"
        assert info["transient"] is False

    def test_invalid_api_key_message(self):
        exc = _make_openai_exc(message="Invalid API key provided")
        info = classify_provider_error(exc)
        assert info["kind"] == "auth"
        assert info["transient"] is False

    def test_authentication_error_message(self):
        exc = _make_openai_exc(message="Authentication error: bad credentials")
        info = classify_provider_error(exc)
        assert info["kind"] == "auth"
        assert info["transient"] is False


# ---------------------------------------------------------------------------
# classify_provider_error — TRANSIENT cases
# ---------------------------------------------------------------------------


class TestTransient:
    def test_openai_429_no_quota_code(self):
        exc = _make_openai_exc(status_code=429, message="Rate limit exceeded")
        info = classify_provider_error(exc)
        assert info["kind"] == "transient"
        assert info["transient"] is True

    def test_anthropic_429(self):
        exc = _make_anthropic_exc(status_code=429, message="Rate limited")
        info = classify_provider_error(exc)
        assert info["kind"] == "transient"
        assert info["transient"] is True

    def test_openai_500(self):
        exc = _make_openai_exc(status_code=500, message="Internal server error")
        info = classify_provider_error(exc)
        assert info["kind"] == "transient"
        assert info["transient"] is True

    def test_anthropic_503(self):
        exc = _make_anthropic_exc(status_code=503, message="Service unavailable")
        info = classify_provider_error(exc)
        assert info["kind"] == "transient"
        assert info["transient"] is True

    def test_connection_error_by_type_name(self):
        exc = _make_exc(_HttpxConnectionError, message="Connection refused")
        info = classify_provider_error(exc)
        assert info["kind"] == "transient"
        assert info["transient"] is True

    def test_timeout_error_by_type_name(self):
        exc = _make_exc(_HttpxTimeoutError, message="Request timed out")
        info = classify_provider_error(exc)
        assert info["kind"] == "transient"
        assert info["transient"] is True

    def test_connection_error_by_message(self):
        exc = _make_exc(_GenericError, message="connection reset by peer")
        info = classify_provider_error(exc)
        assert info["kind"] == "transient"
        assert info["transient"] is True

    def test_429_with_quota_code_is_not_transient(self):
        """OpenAI's insufficient_quota arrives as a 429 but is non-transient."""
        exc = _make_openai_exc(
            status_code=429,
            code="insufficient_quota",
            message="Quota exceeded",
        )
        info = classify_provider_error(exc)
        assert info["kind"] == "needs_deposit"
        assert info["transient"] is False


# ---------------------------------------------------------------------------
# classify_provider_error — UNKNOWN cases
# ---------------------------------------------------------------------------


class TestUnknown:
    def test_generic_exception_is_unknown_non_transient(self):
        exc = ValueError("Something weird happened")
        info = classify_provider_error(exc)
        assert info["kind"] == "unknown"
        assert info["transient"] is False

    def test_classifier_never_raises_on_pathological_input(self):
        """The classifier must not raise even on a completely bizarre object."""
        # Use a plain exc with attributes that explode when accessed.
        exc = Exception("boom")
        # Attach a non-integer to status_code to force a ValueError path
        exc.status_code = "not-an-int"  # type: ignore[attr-defined]
        result = classify_provider_error(exc)
        # Must return a dict, never raise
        assert isinstance(result, dict)
        assert "kind" in result


# ---------------------------------------------------------------------------
# Atomic write safety — .tmp left by kill is NOT visible to --resume
# ---------------------------------------------------------------------------


class TestAtomicWriteSafety:
    def test_stray_tmp_not_counted_as_complete(self, tmp_path):
        """A .tmp file left by a mid-write kill must not satisfy transcript_exists."""
        # Simulate: write only the .tmp, never call os.replace
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from run_experiment import transcript_exists, transcript_path

        dyad_id = "test_dyad_001"
        data_dir = tmp_path / "transcripts"
        data_dir.mkdir()

        # Write only the .tmp (simulate a process killed mid-write)
        p = transcript_path(dyad_id, data_dir)
        tmp = p.with_suffix(".tmp")
        tmp.write_text(json.dumps({"dyad_id": dyad_id, "partial": True}))

        # The .tmp must NOT be counted as a completed transcript
        assert tmp.exists(), "tmp file should exist"
        assert not p.exists(), ".json should NOT exist yet"
        assert (
            transcript_exists(dyad_id, data_dir) is False
        ), "transcript_exists must return False for stray .tmp"

    def test_completed_transcript_is_found(self, tmp_path):
        """After a successful atomic write, transcript_exists must return True."""
        import os

        from run_experiment import transcript_exists, transcript_path, write_transcript

        dyad_id = "test_dyad_002"
        data_dir = tmp_path / "transcripts"
        data_dir.mkdir()

        transcript = {"dyad_id": dyad_id, "turns": [], "deal": False, "mock": True}
        write_transcript(transcript, data_dir)

        p = transcript_path(dyad_id, data_dir)
        assert p.exists(), ".json should exist after write_transcript"
        assert not p.with_suffix(
            ".tmp"
        ).exists(), ".tmp should be gone after os.replace"
        assert transcript_exists(dyad_id, data_dir) is True

    def test_write_transcript_leaves_no_tmp_on_success(self, tmp_path):
        """write_transcript must clean up the .tmp file after os.replace."""
        import os

        from run_experiment import transcript_path, write_transcript

        dyad_id = "test_dyad_003"
        data_dir = tmp_path / "transcripts"
        data_dir.mkdir()

        write_transcript({"dyad_id": dyad_id, "mock": True}, data_dir)

        p = transcript_path(dyad_id, data_dir)
        tmp = p.with_suffix(".tmp")
        assert not tmp.exists(), ".tmp must be absent after successful write"
        assert p.exists()


# ---------------------------------------------------------------------------
# write_run_status — spot check output format
# ---------------------------------------------------------------------------


class TestWriteRunStatus:
    def test_creates_file_with_action_required(self, tmp_path):
        from provider_errors import write_run_status

        p = write_run_status(
            data_dir=tmp_path,
            provider="openai",
            kind="needs_deposit",
            dyads_done=42,
            dyads_remaining=88,
            cost_so_far=1.23,
            resume_cmd="bws run -- uv run python run_experiment.py --resume",
        )
        assert p.exists()
        content = p.read_text()
        assert "ACTION REQUIRED" in content
        assert "OPENAI" in content
        assert "needs_deposit" in content
        assert "42" in content
        assert "$1.2300" in content
        assert "Add a deposit" in content
        assert "--resume" in content

    def test_auth_kind_different_hint(self, tmp_path):
        from provider_errors import write_run_status

        p = write_run_status(
            data_dir=tmp_path,
            provider="anthropic",
            kind="auth",
            dyads_done=0,
            dyads_remaining=630,
            cost_so_far=0.0,
            resume_cmd="bws run -- uv run python run_experiment.py --resume",
        )
        content = p.read_text()
        assert "authentication" in content.lower() or "API key" in content


# ---------------------------------------------------------------------------
# append_blocker_log
# ---------------------------------------------------------------------------


class TestAppendBlockerLog:
    def test_creates_jsonl_row(self, tmp_path):
        from provider_errors import append_blocker_log

        append_blocker_log(
            data_dir=tmp_path,
            provider="openai",
            kind="needs_deposit",
            error_summary="OpenAI: insufficient_quota",
            dyads_done=10,
            cost_so_far=0.5,
        )
        log_path = tmp_path / "run_blockers.jsonl"
        assert log_path.exists()
        row = json.loads(log_path.read_text().strip())
        assert row["provider"] == "openai"
        assert row["kind"] == "needs_deposit"
        assert row["dyads_done"] == 10
        assert row["cost_so_far_usd"] == pytest.approx(0.5, abs=1e-5)

    def test_appends_multiple_rows(self, tmp_path):
        from provider_errors import append_blocker_log

        for i in range(3):
            append_blocker_log(
                data_dir=tmp_path,
                provider="openai",
                kind="transient",
                error_summary=f"error {i}",
                dyads_done=i,
                cost_so_far=float(i),
            )
        lines = (tmp_path / "run_blockers.jsonl").read_text().strip().splitlines()
        assert len(lines) == 3


# ---------------------------------------------------------------------------
# is_acceptance — standalone ACCEPT required; prose "accept" must not match
# ---------------------------------------------------------------------------


class TestIsAcceptance:
    """Verify the tightened ACCEPT parser introduced in the harness-correctness fix.

    Key requirement: is_acceptance must return True only for an unambiguous
    standalone ACCEPT signal, not for "accept" embedded in ordinary prose.
    """

    def setup_method(self):
        from negotiation_runner import is_acceptance

        self.fn = is_acceptance

    # --- TRUE positives (should detect as ACCEPT) ---

    def test_bare_accept(self):
        assert self.fn("ACCEPT") is True

    def test_accept_with_newline(self):
        assert self.fn("I agree to the proposed terms.\nACCEPT") is True

    def test_accept_at_end_of_message(self):
        assert self.fn("Your offer works for me.\nACCEPT\n") is True

    def test_accept_lowercase_on_own_line(self):
        assert self.fn("sounds good\naccept") is True

    def test_accept_after_period(self):
        assert self.fn("Let's close this. ACCEPT") is True

    def test_accept_with_period(self):
        assert self.fn("ACCEPT.") is True

    def test_accept_with_exclamation(self):
        assert self.fn("ACCEPT!") is True

    def test_cot_stripped_then_accept_found(self):
        # CoT block mentions "accept" inside but ACCEPT appears after stripping
        text = "<think>Should I accept? Maybe not yet.</think>\nACCEPT"
        assert self.fn(text) is True

    # --- FALSE positives (must NOT be detected as ACCEPT) ---

    def test_cannot_accept_in_prose(self):
        assert self.fn("I cannot accept these terms.") is False

    def test_accept_mid_sentence(self):
        assert self.fn("I will accept only if you lower the price.") is False

    def test_accept_that_clause(self):
        assert self.fn("I accept that rent is high but still disagree.") is False

    def test_accept_your_position_partial(self):
        assert self.fn("I accept your position on lease length.") is False

    def test_unacceptable_in_prose(self):
        assert self.fn("These terms are unacceptable to me.") is False

    def test_offer_with_prose_accept(self):
        # Agent makes an offer while mentioning "accept" in prose — must NOT trigger
        text = (
            "I cannot accept $1900 rent. "
            'OFFER: {"rent_monthly_usd": 1700, "lease_length_months": 12, '
            '"repair_allowance_usd": 600}'
        )
        assert self.fn(text) is False

    def test_mock_accept_message_is_true(self):
        # The mock dyad emits exactly this pattern — must parse as True
        text = "After careful consideration, I agree to the proposed terms.\nACCEPT"
        assert self.fn(text) is True


# ---------------------------------------------------------------------------
# Study 2 wiring — scenario loading, role extraction, grid enumeration
# ---------------------------------------------------------------------------
# All tests make ZERO API calls.  The Study 2 scenarios live in
# scenarios_study2/ relative to the experiment root.
# ---------------------------------------------------------------------------

EXPERIMENT_DIR = Path(__file__).resolve().parents[1]
SCENARIOS_STUDY2_DIR = EXPERIMENT_DIR / "scenarios_study2"


class TestStudy2Wiring:
    """Verify --scenarios-dir / --scenario-ids plumbing without any API calls."""

    def setup_method(self):
        # Clear the scenario cache between tests to avoid cross-contamination
        from run_experiment import _SCENARIO_CACHE

        _SCENARIO_CACHE.clear()

    # --- role extraction from YAML ---

    def test_merger_roles_from_yaml(self):
        from run_experiment import load_scenario, _extract_roles_from_yaml

        s = load_scenario("merger", scenarios_dir=SCENARIOS_STUDY2_DIR)
        role_a, role_b = _extract_roles_from_yaml(s, "merger")
        assert role_a == "acquirer"
        assert role_b == "founder"

    def test_supplier_roles_from_yaml(self):
        from run_experiment import load_scenario, _extract_roles_from_yaml

        s = load_scenario("supplier", scenarios_dir=SCENARIOS_STUDY2_DIR)
        role_a, role_b = _extract_roles_from_yaml(s, "supplier")
        assert role_a == "buyer"
        assert role_b == "supplier"

    def test_salvage_roles_from_yaml(self):
        from run_experiment import load_scenario, _extract_roles_from_yaml

        s = load_scenario("salvage", scenarios_dir=SCENARIOS_STUDY2_DIR)
        role_a, role_b = _extract_roles_from_yaml(s, "salvage")
        assert role_a == "payer"
        assert role_b == "claimant"

    # --- grid enumeration ---

    def test_study2_grid_non_empty(self):
        from run_experiment import build_grid

        grid = build_grid(
            replicates=1,
            scenario_ids=["merger", "supplier", "salvage"],
            scenarios_dir=SCENARIOS_STUDY2_DIR,
        )
        assert len(grid) > 0

    def test_study2_grid_contains_all_three_scenarios(self):
        from run_experiment import build_grid

        grid = build_grid(
            replicates=1,
            scenario_ids=["merger", "supplier", "salvage"],
            scenarios_dir=SCENARIOS_STUDY2_DIR,
        )
        ids_in_grid = {spec["scenario_id"] for spec in grid}
        assert ids_in_grid == {"merger", "supplier", "salvage"}

    def test_study2_grid_role_pairs_correct(self):
        """Every dyad in the grid must use the roles declared in the YAML."""
        from run_experiment import build_grid

        grid = build_grid(
            replicates=1,
            scenario_ids=["merger", "supplier", "salvage"],
            scenarios_dir=SCENARIOS_STUDY2_DIR,
        )
        expected_role_sets = {
            "merger": {"acquirer", "founder"},
            "supplier": {"buyer", "supplier"},
            "salvage": {"payer", "claimant"},
        }
        for spec in grid:
            sid = spec["scenario_id"]
            pair = {spec["role_a"], spec["role_b"]}
            assert pair == expected_role_sets[sid], (
                f"Scenario {sid}: expected roles {expected_role_sets[sid]}, "
                f"got {pair}"
            )

    # --- Study 1 default path is unchanged ---

    def test_study1_default_roles_unchanged(self):
        """build_grid() with no overrides must still use Study 1 role pairs."""
        from run_experiment import build_grid

        grid = build_grid(replicates=1)
        expected = {
            "chair": {"buyer", "seller"},
            "rental": {"tenant", "landlord"},
            "offer": {"candidate", "recruiter"},
        }
        for spec in grid:
            sid = spec["scenario_id"]
            pair = {spec["role_a"], spec["role_b"]}
            assert pair == expected[sid], (
                f"Study 1 regression: scenario {sid} expected {expected[sid]}, "
                f"got {pair}"
            )

    # --- prompt build path runs without error for Study 2 scenario + role ---

    def test_merger_prompt_build_no_error(self):
        """_build_system_prompt must not raise for merger/acquirer."""
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from negotiation_runner import _build_system_prompt
        from run_experiment import load_scenario

        scenario = load_scenario("merger", scenarios_dir=SCENARIOS_STUDY2_DIR)
        # Should not raise for any of the six conditions
        prompt = _build_system_prompt("NEUTRAL", scenario, "acquirer", max_rounds=14)
        assert len(prompt) > 100

    def test_salvage_prompt_build_no_error(self):
        """_build_system_prompt must not raise for salvage/payer (distributive)."""
        from negotiation_runner import _build_system_prompt
        from run_experiment import load_scenario

        scenario = load_scenario("salvage", scenarios_dir=SCENARIOS_STUDY2_DIR)
        prompt = _build_system_prompt("SPEC_NOCOT", scenario, "payer", max_rounds=14)
        assert len(prompt) > 100


# ---------------------------------------------------------------------------
# --conditions flag — subset grid builds correctly
# ---------------------------------------------------------------------------


class TestConditionsFlag:
    """Verify --conditions subset builds the right condition pairs and dyad count.

    All tests are purely in-process: zero API calls, no file I/O beyond the
    already-present Study-1 scenario YAMLs.
    """

    def setup_method(self):
        from run_experiment import _SCENARIO_CACHE

        _SCENARIO_CACHE.clear()

    def test_subset_conditions_fewer_pairs(self):
        """A 4-condition subset must produce 4*(4+1)/2 = 10 unordered pairs."""
        from run_experiment import build_grid

        grid = build_grid(
            replicates=1,
            scenario_ids=["chair"],
            conditions=["NEUTRAL", "COT_ONLY", "SPEC_NOCOT", "SPEC_NOLOGROLL"],
            scenarios_dir=EXPERIMENT_DIR / "scenarios",
        )
        # 10 pairs × 2 role orders × 1 replicate = 20 dyads
        assert len(grid) == 20

    def test_single_condition_self_play_only(self):
        """A 1-condition subset must produce only 1 self-play pair."""
        from run_experiment import build_grid

        grid = build_grid(
            replicates=1,
            scenario_ids=["chair"],
            conditions=["NEUTRAL"],
            scenarios_dir=EXPERIMENT_DIR / "scenarios",
        )
        # 1 pair (self-play) × 2 role orders × 1 replicate = 2 dyads
        assert len(grid) == 2
        for spec in grid:
            assert spec["cond_a"] == "NEUTRAL"
            assert spec["cond_b"] == "NEUTRAL"

    def test_subset_conditions_all_cond_ids_present(self):
        """Every dyad cond_a and cond_b must be within the requested subset."""
        from run_experiment import build_grid

        subset = ["NEUTRAL", "WARMTH", "DOMINANCE"]
        grid = build_grid(
            replicates=1,
            scenario_ids=["chair"],
            conditions=subset,
            scenarios_dir=EXPERIMENT_DIR / "scenarios",
        )
        for spec in grid:
            assert spec["cond_a"] in subset, f"cond_a not in subset: {spec['cond_a']}"
            assert spec["cond_b"] in subset, f"cond_b not in subset: {spec['cond_b']}"

    def test_default_no_conditions_flag_is_unchanged(self):
        """build_grid() with no conditions override must return the 6-condition grid."""
        from run_experiment import build_grid, CONDITIONS

        grid = build_grid(
            replicates=1,
            scenario_ids=["chair"],
            scenarios_dir=EXPERIMENT_DIR / "scenarios",
        )
        # 6*(6+1)/2 = 21 pairs × 2 role orders × 1 replicate = 42 dyads
        assert len(grid) == 42
        conds_in_grid = {spec["cond_a"] for spec in grid} | {
            spec["cond_b"] for spec in grid
        }
        assert conds_in_grid == set(CONDITIONS)

    def test_two_condition_subset_dyad_count(self):
        """2 conditions → 3 pairs (AB, AA, BB) × 2 orders × R reps."""
        from run_experiment import build_grid

        grid = build_grid(
            replicates=2,
            scenario_ids=["chair"],
            conditions=["NEUTRAL", "WARMTH"],
            scenarios_dir=EXPERIMENT_DIR / "scenarios",
        )
        # 3 pairs × 2 role orders × 2 reps = 12
        assert len(grid) == 12


# ---------------------------------------------------------------------------
# --opponent flag — focal × fixed-opponent pairing
# ---------------------------------------------------------------------------


class TestOpponentFlag:
    """Verify --opponent builds focal×opponent pairs only (no full round-robin).

    Zero API calls.
    """

    def setup_method(self):
        from run_experiment import _SCENARIO_CACHE

        _SCENARIO_CACHE.clear()

    def test_focal_vs_opponent_dyad_count(self):
        """3 focal conditions × 1 scenario × 2 role orders × 1 rep = 6 dyads."""
        from run_experiment import build_grid

        grid = build_grid(
            replicates=1,
            scenario_ids=["chair"],
            conditions=["NEUTRAL", "WARMTH", "DOMINANCE"],
            opponent="NEUTRAL",
            scenarios_dir=EXPERIMENT_DIR / "scenarios",
        )
        # 3 focal conditions × 2 role orders × 1 replicate = 6 dyads
        assert len(grid) == 6

    def test_opponent_is_always_cond_b(self):
        """Every dyad must have opponent==NEUTRAL as cond_a or cond_b.

        The focal × fixed-opponent design means NEUTRAL appears in every dyad.
        """
        from run_experiment import build_grid

        grid = build_grid(
            replicates=1,
            scenario_ids=["chair"],
            conditions=["WARMTH", "SPEC_NOCOT"],
            opponent="NEUTRAL",
            scenarios_dir=EXPERIMENT_DIR / "scenarios",
        )
        for spec in grid:
            assert "NEUTRAL" in (
                spec["cond_a"],
                spec["cond_b"],
            ), f"NEUTRAL not found in dyad: {spec}"

    def test_no_non_opponent_pairings(self):
        """In focal×opponent mode, no dyad should pair two non-opponent conditions."""
        from run_experiment import build_grid

        grid = build_grid(
            replicates=1,
            scenario_ids=["chair"],
            conditions=["WARMTH", "DOMINANCE", "SPEC_NOCOT"],
            opponent="NEUTRAL",
            scenarios_dir=EXPERIMENT_DIR / "scenarios",
        )
        for spec in grid:
            pair = {spec["cond_a"], spec["cond_b"]}
            # Every pair must include NEUTRAL
            assert (
                "NEUTRAL" in pair
            ), f"Dyad has no NEUTRAL: cond_a={spec['cond_a']}, cond_b={spec['cond_b']}"

    def test_opponent_flag_absent_gives_round_robin(self):
        """Without --opponent, two conditions produce a round-robin (3 pairs)."""
        from run_experiment import build_grid

        grid_rr = build_grid(
            replicates=1,
            scenario_ids=["chair"],
            conditions=["NEUTRAL", "WARMTH"],
            scenarios_dir=EXPERIMENT_DIR / "scenarios",
        )
        grid_opp = build_grid(
            replicates=1,
            scenario_ids=["chair"],
            conditions=["NEUTRAL", "WARMTH"],
            opponent="NEUTRAL",
            scenarios_dir=EXPERIMENT_DIR / "scenarios",
        )
        # Round-robin: 3 pairs × 2 orders × 1 rep = 6; focal: 2 × 2 × 1 = 4
        assert len(grid_rr) == 6
        assert len(grid_opp) == 4


# ---------------------------------------------------------------------------
# Grok provider routing — verified via mock/patch (zero real API calls)
# ---------------------------------------------------------------------------


class TestGrokRouting:
    """Verify that grok model names route to the xAI branch (not OpenAI/Anthropic).

    All tests patch the client constructor and make ZERO real API calls.
    """

    def test_grok_model_routes_to_grok_branch(self):
        """_call_model dispatches grok-4.3 to _call_grok, not _call_openai."""
        import unittest.mock as mock

        import negotiation_runner

        with (
            mock.patch.object(
                negotiation_runner, "_call_grok", return_value="grok-response"
            ) as mock_grok,
            mock.patch.object(
                negotiation_runner, "_call_openai", return_value="openai-response"
            ) as mock_openai,
            mock.patch.object(
                negotiation_runner, "_call_anthropic", return_value="anthropic-response"
            ) as mock_anthropic,
        ):
            result = negotiation_runner._call_model(
                model="grok-4.3",
                system_prompt="test system",
                messages=[{"role": "user", "content": "hi"}],
                temperature=0.2,
                dyad_id="test_dyad",
                turn_num=1,
                role="buyer",
                logs_dir=Path("/tmp"),
            )
            assert result == "grok-response"
            mock_grok.assert_called_once()
            mock_openai.assert_not_called()
            mock_anthropic.assert_not_called()

    def test_grok_startswith_prefix_routes_correctly(self):
        """Any model name starting with 'grok' routes to the xAI branch."""
        import unittest.mock as mock

        import negotiation_runner

        with mock.patch.object(
            negotiation_runner, "_call_grok", return_value="ok"
        ) as mock_grok:
            negotiation_runner._call_model(
                model="grok-future-version",
                system_prompt="s",
                messages=[{"role": "user", "content": "hi"}],
                temperature=0.2,
                dyad_id="d",
                turn_num=1,
                role="buyer",
                logs_dir=Path("/tmp"),
            )
            mock_grok.assert_called_once()

    def test_gpt_model_does_not_route_to_grok(self):
        """gpt-4o-mini must NOT hit the grok branch."""
        import unittest.mock as mock

        import negotiation_runner

        with (
            mock.patch.object(
                negotiation_runner, "_call_grok", return_value="should-not-happen"
            ) as mock_grok,
            mock.patch.object(negotiation_runner, "_call_openai", return_value="ok"),
        ):
            negotiation_runner._call_model(
                model="gpt-4o-mini",
                system_prompt="s",
                messages=[{"role": "user", "content": "hi"}],
                temperature=0.2,
                dyad_id="d",
                turn_num=1,
                role="buyer",
                logs_dir=Path("/tmp"),
            )
            mock_grok.assert_not_called()

    def test_claude_model_does_not_route_to_grok(self):
        """claude-haiku-4-5 must NOT hit the grok branch."""
        import unittest.mock as mock

        import negotiation_runner

        with (
            mock.patch.object(
                negotiation_runner, "_call_grok", return_value="should-not-happen"
            ) as mock_grok,
            mock.patch.object(negotiation_runner, "_call_anthropic", return_value="ok"),
        ):
            negotiation_runner._call_model(
                model="claude-haiku-4-5",
                system_prompt="s",
                messages=[{"role": "user", "content": "hi"}],
                temperature=0.2,
                dyad_id="d",
                turn_num=1,
                role="buyer",
                logs_dir=Path("/tmp"),
            )
            mock_grok.assert_not_called()

    def test_grok_uses_xai_base_url_and_env_key(self):
        """_call_grok must construct OpenAI client with GROK_BASE_URL + GROK_API_KEY.

        openai is not installed in the test venv, so we inject a fake module into
        sys.modules before importing negotiation_runner's local ``import openai``
        statement fires.  The fake module's OpenAI constructor is a MagicMock that
        records the call kwargs — we assert on base_url and api_key after the call.
        """
        import importlib
        import types
        import unittest.mock as mock

        import negotiation_runner

        # Build a minimal fake openai module with a controllable OpenAI class
        fake_client = MagicMock()
        fake_response = MagicMock()
        fake_response.choices = [MagicMock()]
        fake_response.choices[0].message.content = "xai-reply"
        fake_client.chat.completions.create.return_value = fake_response

        mock_openai_cls = MagicMock(return_value=fake_client)

        fake_openai_mod = types.ModuleType("openai")
        fake_openai_mod.OpenAI = mock_openai_cls  # type: ignore[attr-defined]

        # Set up a fake log_call context manager that does nothing
        mock_logger = MagicMock()
        mock_log_call = MagicMock()
        mock_log_call.return_value.__enter__ = MagicMock(return_value=mock_logger)
        mock_log_call.return_value.__exit__ = MagicMock(return_value=False)

        with (
            mock.patch.dict("sys.modules", {"openai": fake_openai_mod}),
            mock.patch("llm_call_logger.log_call", mock_log_call),
            mock.patch.dict("os.environ", {"GROK_API_KEY": "test-key-xai"}),
        ):
            negotiation_runner._call_grok(
                model="grok-4.3",
                system_prompt="sys",
                messages=[{"role": "user", "content": "hi"}],
                temperature=0.2,
                dyad_id="d",
                turn_num=1,
                role="buyer",
                logs_dir=Path("/tmp"),
            )

        # Verify the OpenAI client was constructed with the xAI base URL and key
        mock_openai_cls.assert_called_once()
        call_kwargs = mock_openai_cls.call_args
        assert call_kwargs.kwargs.get("base_url") == negotiation_runner.GROK_BASE_URL
        assert call_kwargs.kwargs.get("api_key") == "test-key-xai"


# ---------------------------------------------------------------------------
# Default (no new flags) grid is unchanged
# ---------------------------------------------------------------------------


class TestDefaultGridUnchanged:
    """Regression: default build_grid() (no new flags) must be identical to
    the pre-extension baseline.

    These tests confirm that the addition of the conditions/opponent parameters
    to build_grid does not change output when neither is provided.
    """

    def setup_method(self):
        from run_experiment import _SCENARIO_CACHE

        _SCENARIO_CACHE.clear()

    def test_default_grid_size_study1(self):
        """Full Study-1 grid: 21 pairs × 3 scenarios × 2 orders × 5 reps = 630."""
        from run_experiment import build_grid

        grid = build_grid()  # all defaults
        assert len(grid) == 630

    def test_default_grid_conditions_are_all_six(self):
        """All 6 default conditions must appear in the default grid."""
        from run_experiment import build_grid, CONDITIONS

        grid = build_grid()
        conds = {spec["cond_a"] for spec in grid} | {spec["cond_b"] for spec in grid}
        assert conds == set(CONDITIONS)

    def test_default_grid_scenario_ids(self):
        """Default grid must cover exactly chair, rental, offer."""
        from run_experiment import build_grid

        grid = build_grid()
        ids = {spec["scenario_id"] for spec in grid}
        assert ids == {"chair", "rental", "offer"}

    def test_conditions_none_equals_conditions_explicit_full(self):
        """Passing conditions=CONDITIONS explicitly must give the same dyad count as None."""
        from run_experiment import build_grid, CONDITIONS

        grid_default = build_grid(replicates=1, scenario_ids=["chair"])
        grid_explicit = build_grid(
            replicates=1,
            scenario_ids=["chair"],
            conditions=list(CONDITIONS),
        )
        assert len(grid_default) == len(grid_explicit)
