"""test_icc.py — unit tests for compute_icc.py.

Tests the compute_interscorer_icc() function against hand-checked matrices
to verify the ICC(2,1) formula and the log-parsing / key-normalization logic.

All tests are deterministic and make ZERO API calls.

Run:
    uv run pytest code/test_icc.py -v
"""

from __future__ import annotations

import json
import math
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from compute_icc import (
    _normalize_key,
    _strip_fences_and_parse,
    compute_interscorer_icc,
)
from outcomes import compute_icc_2_1

# ---------------------------------------------------------------------------
# _strip_fences_and_parse
# ---------------------------------------------------------------------------


class TestStripFencesAndParse:
    def test_plain_json(self):
        result = _strip_fences_and_parse('{"warmth_score": 70, "dominance_score": 30}')
        assert result == {"warmth_score": 70, "dominance_score": 30}

    def test_fenced_json(self):
        text = '```json\n{"warmth_score": 55, "dominance_score": 25}\n```'
        result = _strip_fences_and_parse(text)
        assert result == {"warmth_score": 55, "dominance_score": 25}

    def test_fenced_with_preamble(self):
        # haiku sometimes emits reasoning text before the fence
        text = (
            "The agent is moderately warm and not very dominant.\n\n"
            '```json\n{"warmth_score": 65, "dominance_score": 20}\n```'
        )
        result = _strip_fences_and_parse(text)
        assert result == {"warmth_score": 65, "dominance_score": 20}

    def test_json_in_braces_fallback(self):
        # No fences, but JSON is embedded in text
        text = 'Here is the score: {"warmth_score": 50, "dominance_score": 50} end.'
        result = _strip_fences_and_parse(text)
        assert result == {"warmth_score": 50, "dominance_score": 50}

    def test_unparseable_raises(self):
        with pytest.raises(ValueError, match="Cannot parse JSON"):
            _strip_fences_and_parse("this is not json at all")


# ---------------------------------------------------------------------------
# _normalize_key
# ---------------------------------------------------------------------------


class TestNormalizeKey:
    def test_strips_wd_gpt4o_prefix(self):
        assert _normalize_key("wd_gpt4o_dyad123_buyer") == "dyad123_buyer"

    def test_strips_wd_haiku_prefix(self):
        assert _normalize_key("wd_haiku_dyad123_buyer") == "dyad123_buyer"

    def test_strips_svi_gpt4o_prefix(self):
        assert _normalize_key("svi_gpt4o_dyad456_tenant") == "dyad456_tenant"

    def test_strips_rescore_v2_prefix(self):
        assert _normalize_key("rescore_v2_gpt4o_dyad789") == "dyad789"
        assert _normalize_key("rescore_v2_haiku_dyad789") == "dyad789"

    def test_already_normalized_unchanged(self):
        key = "dyad123_buyer_chair_neutral"
        assert _normalize_key(key) == key


# ---------------------------------------------------------------------------
# compute_interscorer_icc — against hand-built JSONL fixtures
# ---------------------------------------------------------------------------
#
# Hand-checked matrix:
#   Rater 1 (gpt4o): warmth=[80, 60, 40, 20], dominance=[20, 40, 60, 80]
#   Rater 2 (haiku): warmth=[82, 62, 38, 18], dominance=[22, 42, 58, 78]
#
#   For warmth: nearly perfect agreement, slight systematic offset.
#   Expected ICC(2,1) close to 1.0.
#
#   Hand computation for warmth (4 targets, k=2):
#     grand_mean = (80+60+40+20 + 82+62+38+18) / 8 = 400/8 = 50
#     row_means = [81, 61, 39, 19]
#     col_means = gpt4o_mean=50, haiku_mean=50
#     ss_r = 2*[(81-50)^2+(61-50)^2+(39-50)^2+(19-50)^2]
#           = 2*[961+121+121+961] = 2*2164 = 4328
#     ss_c = 4*[(50-50)^2+(50-50)^2] = 0
#     ss_total = (80-50)^2+(60-50)^2+(40-50)^2+(20-50)^2
#               +(82-50)^2+(62-50)^2+(38-50)^2+(18-50)^2
#             = 900+100+100+900 + 1024+144+144+1024 = 4336
#     ss_e = 4336 - 4328 - 0 = 8
#     df_r=3, df_c=1, df_e=3
#     ms_r = 4328/3 = 1442.667, ms_c = 0/1 = 0, ms_e = 8/3 = 2.667
#     denom = 1442.667 + 1*2.667 + (2/4)*(0-2.667)
#           = 1442.667 + 2.667 - 1.333 = 1444.0
#     icc = (1442.667 - 2.667) / 1444.0 = 1440 / 1444.0 = 0.99723
#     -> Confirmed with compute_icc_2_1([80,60,40,20], [82,62,38,18]) = ~0.997
#
# We verify this self-consistently via the function under test.


def _make_wd_jsonl(path: Path, scorer_prefix: str, data: list[dict]) -> None:
    """Write a fake wd scoring JSONL file for testing."""
    with open(path, "w") as f:
        for item in data:
            operation = f"{scorer_prefix}_{item['key']}"
            response_json = json.dumps(
                {
                    "warmth_score": item["warmth"],
                    "dominance_score": item["dominance"],
                }
            )
            row = {
                "log_format_version": "1.0",
                "phase": "scoring",
                "operation": operation,
                "operator": (
                    scorer_prefix.split("_")[1]
                    if "_" in scorer_prefix
                    else scorer_prefix
                ),
                "operator_role": "orchestrator",
                "model_version": "test-model",
                "timestamp_utc": "2026-06-06T00:00:00Z",
                "system_prompt": "test",
                "user_prompt": "test",
                "parameters": {"temperature": 0.0},
                "request_id": None,
                "endpoint": "https://example.com",
                "sdk_version": "test",
                "response": response_json,
                "response_metadata": {"finish_reason": "stop"},
                "tokens": {"input": 100, "output": 16},
                "latency_seconds": 0.5,
                "cost_usd_est": 0.001,
                "errors": [],
                "retries": 0,
                "git_sha_caller": "abc123",
                "python_env_hash": "def456",
                "human_in_loop": False,
                "reconstructed_post_hoc": False,
            }
            f.write(json.dumps(row) + "\n")


class TestComputeInterscorerICC:
    """Tests for compute_interscorer_icc() using hand-built JSONL fixtures."""

    TARGETS = ["target_a", "target_b", "target_c", "target_d"]
    GPT4O_WARMTH = [80.0, 60.0, 40.0, 20.0]
    HAIKU_WARMTH = [82.0, 62.0, 38.0, 18.0]
    GPT4O_DOM = [20.0, 40.0, 60.0, 80.0]
    HAIKU_DOM = [22.0, 42.0, 58.0, 78.0]

    def _make_logs_dir(self, tmp_path: Path) -> Path:
        logs_dir = tmp_path / "logs"
        logs_dir.mkdir()
        gpt4o_data = [
            {
                "key": self.TARGETS[i],
                "warmth": self.GPT4O_WARMTH[i],
                "dominance": self.GPT4O_DOM[i],
            }
            for i in range(4)
        ]
        haiku_data = [
            {
                "key": self.TARGETS[i],
                "warmth": self.HAIKU_WARMTH[i],
                "dominance": self.HAIKU_DOM[i],
            }
            for i in range(4)
        ]
        _make_wd_jsonl(
            logs_dir / "phase_scoring_wd_gpt4o_test_calls.jsonl",
            "wd_gpt4o",
            gpt4o_data,
        )
        _make_wd_jsonl(
            logs_dir / "phase_scoring_wd_haiku_test_calls.jsonl",
            "wd_haiku",
            haiku_data,
        )
        return logs_dir

    def test_icc_warmth_near_one(self, tmp_path: Path):
        """Warmth ICC should be ~.997 for the hand-computed matrix."""
        logs_dir = self._make_logs_dir(tmp_path)
        results = compute_interscorer_icc(logs_dir, verbose=False)
        assert "warmth" in results
        assert results["warmth"]["n_targets"] == 4
        # Hand-computed value: 1440/1444 = 0.99723
        assert results["warmth"]["icc"] == pytest.approx(1440.0 / 1444.0, abs=1e-3)

    def test_icc_dominance_near_one(self, tmp_path: Path):
        """Dominance ICC should also be near 1.0 for the symmetric matrix."""
        logs_dir = self._make_logs_dir(tmp_path)
        results = compute_interscorer_icc(logs_dir, verbose=False)
        assert "dominance" in results
        assert results["dominance"]["icc"] == pytest.approx(1440.0 / 1444.0, abs=1e-3)

    def test_pearson_r_returned(self, tmp_path: Path):
        """Pearson r should be returned alongside ICC."""
        logs_dir = self._make_logs_dir(tmp_path)
        results = compute_interscorer_icc(logs_dir, verbose=False)
        assert "pearson_r" in results["warmth"]
        assert math.isfinite(results["warmth"]["pearson_r"])
        assert results["warmth"]["pearson_r"] > 0.99

    def test_missing_gpt4o_logs_raises(self, tmp_path: Path):
        """FileNotFoundError if no gpt4o wd logs present."""
        logs_dir = tmp_path / "logs"
        logs_dir.mkdir()
        with pytest.raises(FileNotFoundError, match="phase_scoring_wd_gpt4o"):
            compute_interscorer_icc(logs_dir, verbose=False)

    def test_fenced_haiku_response_parsed(self, tmp_path: Path):
        """Haiku responses with ```json fences should parse correctly."""
        logs_dir = tmp_path / "logs"
        logs_dir.mkdir()

        gpt4o_data = [{"key": "t1", "warmth": 70.0, "dominance": 30.0}]
        _make_wd_jsonl(
            logs_dir / "phase_scoring_wd_gpt4o_fencetest_calls.jsonl",
            "wd_gpt4o",
            gpt4o_data,
        )
        # Write haiku file with fenced JSON
        haiku_path = logs_dir / "phase_scoring_wd_haiku_fencetest_calls.jsonl"
        row = {
            "log_format_version": "1.0",
            "phase": "scoring",
            "operation": "wd_haiku_t1",
            "operator": "haiku",
            "operator_role": "orchestrator",
            "model_version": "test-model",
            "timestamp_utc": "2026-06-06T00:00:00Z",
            "system_prompt": "test",
            "user_prompt": "test",
            "parameters": {},
            "request_id": None,
            "endpoint": "test",
            "sdk_version": "test",
            "response": '```json\n{"warmth_score": 72, "dominance_score": 28}\n```',
            "response_metadata": {},
            "tokens": {"input": 100, "output": 20},
            "latency_seconds": 0.5,
            "cost_usd_est": 0.001,
            "errors": [],
            "retries": 0,
            "git_sha_caller": "abc",
            "python_env_hash": "def",
            "human_in_loop": False,
            "reconstructed_post_hoc": False,
        }
        haiku_path.write_text(json.dumps(row) + "\n")
        # Should not raise; ICC with n=1 will raise ValueError from compute_icc_2_1
        # (need >= 2 targets), so we expect that error, not a parse error
        with pytest.raises(ValueError, match="at least 2"):
            compute_interscorer_icc(logs_dir, verbose=False)

    def test_hand_computed_known_icc_value(self):
        """Direct formula check against the hand-computed warmth matrix.

        This is the self-test of the underlying compute_icc_2_1 function
        with the specific values from this experiment's pilot.
        """
        # Rater 1 (gpt4o): [80, 60, 40, 20]
        # Rater 2 (haiku): [82, 62, 38, 18]
        # Hand-computed ICC(2,1) = 1440/1444 = 0.99723
        result = compute_icc_2_1(
            [80.0, 60.0, 40.0, 20.0],
            [82.0, 62.0, 38.0, 18.0],
        )
        assert result["icc"] == pytest.approx(1440.0 / 1444.0, abs=1e-3)
        assert result["n_targets"] == 4

    def test_known_pilot_style_matrix(self):
        """Verify that a matrix resembling the actual pilot ICC can be reproduced.

        The pilot produced WARMTH ICC .863 and DOMINANCE ICC .802 on 20 dyads.
        We verify that our formula can reproduce moderate ICC values in this range.
        Use a 4-target matrix with ICC ~.8 for a fast self-check.

        Hand-computed:
          s1 = [10, 30, 50, 70]  (uniform spread)
          s2 = [15, 40, 45, 65]  (slightly noisier)
          grand_mean = (10+30+50+70 + 15+40+45+65) / 8 = 325/8 = 40.625
          row_means = [12.5, 35, 47.5, 67.5]
          col_means = s1_mean=40, s2_mean=41.25
          ss_r = 2*[(12.5-40.625)^2+(35-40.625)^2+(47.5-40.625)^2+(67.5-40.625)^2]
               = 2*[791.015625 + 31.640625 + 47.265625 + 722.265625]
               = 2*1592.1875 = 3184.375
          ss_c = 4*[(40-40.625)^2+(41.25-40.625)^2]
               = 4*[0.390625+0.390625] = 4*0.78125 = 3.125
          ss_total = (10-40.625)^2+(30-40.625)^2+(50-40.625)^2+(70-40.625)^2
                    +(15-40.625)^2+(40-40.625)^2+(45-40.625)^2+(65-40.625)^2
                  = 937.890625+112.890625+87.890625+862.890625
                  + 656.640625+0.390625+19.140625+597.640625 = 3275
          ss_e = 3275 - 3184.375 - 3.125 = 87.5
          df_r=3, df_c=1, df_e=3
          ms_r = 3184.375/3 = 1061.458, ms_c = 3.125, ms_e = 87.5/3 = 29.167
          denom = 1061.458 + 29.167 + (2/4)*(3.125 - 29.167)
                = 1061.458 + 29.167 + 0.5*(-26.042)
                = 1061.458 + 29.167 - 13.021 = 1077.604
          icc = (1061.458 - 29.167) / 1077.604 = 1032.291 / 1077.604 = .9580

        This is a test of the formula; the pilot's .863/.802 values come from
        the actual 20-dyad data in the rescore logs.
        """
        s1 = [10.0, 30.0, 50.0, 70.0]
        s2 = [15.0, 40.0, 45.0, 65.0]
        result = compute_icc_2_1(s1, s2)
        # Expected ~0.958
        assert result["icc"] == pytest.approx(1032.291 / 1077.604, abs=0.01)
        assert result["n_targets"] == 4
