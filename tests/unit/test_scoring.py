from dataclasses import asdict

import numpy as np
import pandas as pd
import pytest

from ltverify.config import ScoringConfig
from ltverify.scoring import ScoreWeights, diagnose, score_candidates


def scored_candidate_fixture() -> tuple[pd.DataFrame, pd.DataFrame]:
    scored = pd.DataFrame(
        {
            "transformer_id": [
                "T001", "T001", "T001",
                "T002", "T002", "T002",
                "T003", "T003", "T003",
            ],
            "candidate_feeder_id": ["F01", "F02", "F03"] * 3,
            "peer_count": [2] * 9,
            "raw_corr": [0.4, 0.9, 0.5, 0.9, 0.85, 0.3, 0.5, 0.4, 0.6],
            "residual_corr": [0.0] * 9,
            "diff_corr": [0.0] * 9,
            "rolling_corr_median": [0.0] * 9,
            "rolling_corr_q10": [0.0] * 9,
            "event_match": [0.0] * 9,
            "active_power_corr": [0.0] * 9,
            "coverage": [1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 0.5, 0.5, 0.5],
            "baseline_score": [0.4, 0.9, 0.5, 0.9, 0.85, 0.3, 0.5, 0.4, 0.6],
            "enhanced_score": [0.40, 0.90, 0.45, 0.90, 0.85, 0.35, 0.40, 0.50, 0.30],
        }
    )
    ledger = pd.DataFrame(
        {
            "transformer_id": ["T001", "T002", "T003"],
            "reported_feeder_id": ["F01", "F01", "F02"],
        }
    )
    return scored, ledger


def test_default_weights_sum_to_one() -> None:
    assert sum(asdict(ScoreWeights()).values()) == pytest.approx(1.0)


def test_diagnosis_flags_wrong_ledger_and_recommends_best_feeder() -> None:
    scored, ledger = scored_candidate_fixture()
    predictions = diagnose(
        scored,
        ledger,
        ScoringConfig(current_score_threshold=0.70, margin_threshold=0.08),
    )
    row = predictions.set_index("transformer_id").loc["T001"]
    assert bool(row["predicted_is_mislinked"]) is True
    assert row["recommended_feeder_id"] == "F02"
    assert row["decision"] == "automatic_recommendation"


def test_low_coverage_refuses_automatic_recommendation() -> None:
    scored, ledger = scored_candidate_fixture()
    predictions = diagnose(scored, ledger, ScoringConfig())
    row = predictions.set_index("transformer_id").loc["T003"]
    assert row["decision"] == "insufficient_data"
    assert bool(row["predicted_is_mislinked"]) is False


def test_stable_ledger_stays_unchanged_when_candidate_is_close() -> None:
    scored, ledger = scored_candidate_fixture()
    predictions = diagnose(
        scored,
        ledger,
        ScoringConfig(current_score_threshold=0.70, margin_threshold=0.08),
    )
    row = predictions.set_index("transformer_id").loc["T002"]
    assert row["decision"] == "no_change"
    assert row["recommended_feeder_id"] == "F01"
    assert bool(row["predicted_is_mislinked"]) is False


def test_enhanced_score_renormalizes_over_available_features() -> None:
    features = pd.DataFrame(
        [
            {
                "transformer_id": "T001",
                "candidate_feeder_id": "F01",
                "raw_corr": 1.0,
                "residual_corr": np.nan,
                "diff_corr": np.nan,
                "rolling_corr_median": np.nan,
                "rolling_corr_q10": np.nan,
                "event_match": np.nan,
                "active_power_corr": np.nan,
            },
            {
                "transformer_id": "T002",
                "candidate_feeder_id": "F01",
                "raw_corr": 0.0,
                "residual_corr": np.nan,
                "diff_corr": np.nan,
                "rolling_corr_median": np.nan,
                "rolling_corr_q10": np.nan,
                "event_match": 1.0,
                "active_power_corr": np.nan,
            },
        ]
    )
    scored = score_candidates(features, ScoreWeights())
    assert scored.loc[0, "baseline_score"] == pytest.approx(1.0)
    assert scored.loc[0, "enhanced_score"] == pytest.approx(1.0)
    assert scored.loc[1, "enhanced_score"] == pytest.approx(0.75)
