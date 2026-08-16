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
            "anomaly_score": [0.9, 0.8, 0.7],
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
    assert result.metrics["top2_correction_rate"] == pytest.approx(1.0)
    assert result.metrics["top3_correction_rate"] is None
    assert result.metrics["candidate_feeder_count"] == 3
    assert result.metrics["topk_applicable"]["top3"] is False
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


def test_pr_auc_uses_continuous_anomaly_score() -> None:
    predictions, truth, ledger, candidate_scores = evaluation_fixture()
    base = predictions.assign(anomaly_score=[0.9, 0.8, 0.7])
    flipped = predictions.assign(anomaly_score=[0.1, 0.2, 0.3])
    assert (base["predicted_is_mislinked"] == flipped["predicted_is_mislinked"]).all()
    first = evaluate_predictions(base, truth, ledger, candidate_scores)
    second = evaluate_predictions(flipped, truth, ledger, candidate_scores)
    assert first.metrics["pr_auc"] != second.metrics["pr_auc"]


def test_top3_is_not_applicable_with_only_three_candidates() -> None:
    predictions, truth, ledger, candidate_scores = evaluation_fixture()
    result = evaluate_predictions(predictions, truth, ledger, candidate_scores)
    assert result.metrics["candidate_feeder_count"] == 3
    assert result.metrics["top3_correction_rate"] is None
    assert isinstance(result.metrics["top2_correction_rate"], float)


def _nan_candidate_fixture(order: list[str]):
    predictions = pd.DataFrame(
        {
            "transformer_id": ["T001"],
            "reported_feeder_id": ["F01"],
            "recommended_feeder_id": ["F01"],
            "current_score": [0.5],
            "best_score": [0.6],
            "margin": [0.1],
            "coverage": [1.0],
            "predicted_is_mislinked": [False],
            "confidence": [0.0],
            "decision": ["no_change"],
            "anomaly_score": [0.0],
        }
    )
    truth = pd.DataFrame(
        {"transformer_id": ["T001"], "physical_feeder_id": ["F02"]}
    )
    ledger = pd.DataFrame(
        {"transformer_id": ["T001"], "reported_feeder_id": ["F01"]}
    )
    scores = pd.DataFrame(
        {
            "transformer_id": ["T001"] * 3,
            "candidate_feeder_id": order,
            "enhanced_score": [0.5, float("nan"), float("nan")],
            "available_feature_weight": [1.0, 0.0, 0.0],
        }
    )
    return predictions, truth, ledger, scores


def test_topk_ignores_nan_candidates_and_row_order() -> None:
    first = evaluate_predictions(
        *_nan_candidate_fixture(["F01", "F02", "F03"])
    )
    second = evaluate_predictions(
        *_nan_candidate_fixture(["F03", "F02", "F01"])
    )
    assert first.metrics["top2_correction_rate"] == second.metrics["top2_correction_rate"]
    # 物理馈线 F02 位于 NaN 行，不得进入 Top-2 产生虚假命中；
    # 该设备有效候选 1 个（<2），Top-2 不可评价 → 不计入分母
    assert first.metrics["top2_correction_rate"] is None
    assert first.metrics["top2_evaluated_count"] == 0
    assert first.metrics["top2_evaluation_coverage"] == 0.0


def test_topk_evaluation_coverage_counts_only_eligible_devices() -> None:
    predictions, truth, ledger, candidate_scores = evaluation_fixture()
    # T002（真实错误）只剩一个有限候选（<2），Top-2 不可评价
    candidate_scores.loc[
        (candidate_scores["transformer_id"] == "T002")
        & (candidate_scores["candidate_feeder_id"] != "F01"),
        "enhanced_score",
    ] = float("nan")
    result = evaluate_predictions(predictions, truth, ledger, candidate_scores)
    assert result.metrics["top2_evaluated_count"] == 1
    assert result.metrics["top2_evaluation_coverage"] == 0.5


def test_pr_auc_scored_metric_on_scored_subset() -> None:
    predictions, truth, ledger, candidate_scores = evaluation_fixture()
    result = evaluate_predictions(predictions, truth, ledger, candidate_scores)
    assert result.metrics["pr_auc_scored"] == pytest.approx(1.0)
    # 全部 decision 为 insufficient_data 时 scored 子集为空 → pr_auc_scored 为 null
    all_insufficient = predictions.assign(
        decision=["insufficient_data"] * 3
    )
    result2 = evaluate_predictions(all_insufficient, truth, ledger, candidate_scores)
    assert result2.metrics["pr_auc_scored"] is None
    assert result2.metrics["scored_coverage"] == 0.0


def test_evaluate_applies_evidence_weight_threshold() -> None:
    predictions, truth, ledger, candidate_scores = evaluation_fixture()
    candidate_scores["available_feature_weight"] = 1.0
    candidate_scores.loc[
        (candidate_scores["transformer_id"] == "T001")
        & (candidate_scores["candidate_feeder_id"] == "F01"),
        "available_feature_weight",
    ] = 0.1
    result = evaluate_predictions(
        predictions, truth, ledger, candidate_scores,
        evidence_weight_threshold=0.5,
    )
    # T001 的物理馈线 F01 被证据门槛排除；T002 的 Top-1 是 F01(0.8) 而非物理 F02
    assert result.metrics["top1_correction_rate"] == 0.0


def test_single_class_all_negative_pr_auc_is_null() -> None:
    predictions, truth, ledger, candidate_scores = evaluation_fixture()
    # 所有台账与真值一致 → 实际错误数为 0（单类别）
    ledger_all_correct = truth.rename(
        columns={"physical_feeder_id": "reported_feeder_id"}
    )
    result = evaluate_predictions(
        predictions, truth, ledger_all_correct, candidate_scores
    )
    assert result.metrics["pr_auc"] is None
    assert result.metrics["pr_auc_applicable"] is False
    assert result.metrics["pr_auc_unavailable_reason"] == "single_class_all_negative"
    assert result.metrics["n_actual_errors"] == 0


def test_single_class_all_positive_pr_auc_is_null() -> None:
    predictions, truth, ledger, candidate_scores = evaluation_fixture()
    all_positive = truth.assign(physical_feeder_id=["F02", "F03", "F01"])
    result = evaluate_predictions(
        predictions, truth=all_positive, ledger=ledger, candidate_scores=candidate_scores
    )
    assert result.metrics["n_actual_errors"] == 3
    assert result.metrics["pr_auc"] is None
    assert result.metrics["pr_auc_applicable"] is False
    assert result.metrics["pr_auc_unavailable_reason"] == "single_class_all_positive"


def test_topk_rejects_non_finite_scores_and_weights() -> None:
    predictions, truth, ledger, candidate_scores = evaluation_fixture()
    candidate_scores["available_feature_weight"] = 1.0
    candidate_scores.loc[
        (candidate_scores["transformer_id"] == "T002")
        & (candidate_scores["candidate_feeder_id"] == "F01"),
        "enhanced_score",
    ] = float("inf")
    candidate_scores.loc[
        (candidate_scores["transformer_id"] == "T002")
        & (candidate_scores["candidate_feeder_id"] == "F02"),
        "enhanced_score",
    ] = float("-inf")
    result = evaluate_predictions(predictions, truth, ledger, candidate_scores)
    # T002 只剩 F03 一个有限候选：Top-2 不可评价（排除计数已上报）
    assert result.metrics["top2_evaluated_count"] == 1
    assert "excluded_candidate_count" in result.metrics
    assert result.metrics["excluded_candidate_count"] >= 2
