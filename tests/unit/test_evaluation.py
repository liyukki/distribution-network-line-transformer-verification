import pandas as pd
import pytest

from ltverify.evaluation import evaluate_predictions, grouped_scenario_split


def evaluation_fixture() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    predictions = pd.DataFrame(
        {
            "transformer_id": ["T001", "T002", "T003"],
            "reported_feeder_id": ["F02", "F03", "F03"],
            "recommended_feeder_id": ["F01", "F01", "F01"],
            "current_score": [0.3, 0.4, 0.5],
            "best_score": [0.9, 0.8, 0.9],
            "margin": [0.6, 0.4, 0.4],
            "coverage": [1.0, 1.0, 1.0],
            "predicted_is_mislinked": [True, True, True],
            "confidence": [0.9, 0.8, 0.8],
            "decision": ["automatic_recommendation"] * 3,
        }
    )
    truth = pd.DataFrame(
        {
            "transformer_id": ["T001", "T002", "T003"],
            "physical_feeder_id": ["F01", "F02", "F03"],
        }
    )
    ledger = pd.DataFrame(
        {
            "transformer_id": ["T001", "T002", "T003"],
            "reported_feeder_id": ["F02", "F03", "F03"],
        }
    )
    candidate_scores = pd.DataFrame(
        {
            "transformer_id": ["T001", "T001", "T001", "T002", "T002", "T002", "T003", "T003", "T003"],
            "candidate_feeder_id": ["F01", "F02", "F03"] * 3,
            "enhanced_score": [0.9, 0.3, 0.4, 0.8, 0.7, 0.3, 0.9, 0.5, 0.8],
        }
    )
    return predictions, truth, ledger, candidate_scores


def test_evaluation_computes_detection_and_correction_metrics() -> None:
    predictions, truth, ledger, candidate_scores = evaluation_fixture()
    result = evaluate_predictions(predictions, truth, ledger, candidate_scores)
    assert result.metrics["precision"] == pytest.approx(2 / 3)
    assert result.metrics["recall"] == pytest.approx(1.0)
    assert result.metrics["f1"] == pytest.approx(0.8)
    assert result.metrics["top1_correction_rate"] == pytest.approx(0.5)
    assert result.metrics["top3_correction_rate"] == pytest.approx(1.0)
    assert result.confusion_matrix.shape == (2, 2)


def test_grouped_scenario_split_partitions_scenarios() -> None:
    metadata = pd.DataFrame({"scenario_id": [f"S{i:02d}" for i in range(10)]})
    split = grouped_scenario_split(metadata, seed=42)
    parts = [split["train"], split["validation"], split["test"]]
    assert len(split["train"]) == 6
    assert len(split["validation"]) == 2
    assert len(split["test"]) == 2
    for index, left in enumerate(parts):
        for right in parts[index + 1 :]:
            assert not left & right
    assert set().union(*parts) == set(metadata["scenario_id"])
    assert grouped_scenario_split(metadata, seed=42) == split
