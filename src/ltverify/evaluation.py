"""Leakage-safe evaluation and grouped scenario splitting.

This is the only module allowed to merge the physical truth into
predictions. Detection metrics use precision/recall/F1/PR-AUC (never
Accuracy as the headline). PR-AUC always consumes the continuous
anomaly_score, never the binary prediction. Top-k correction rates are
reported only when strictly more than k legal candidate feeders exist;
otherwise they are marked not_applicable. The scenario split keeps whole
scenarios inside a single partition so no time point leaks across sets.
"""

from dataclasses import dataclass

import numpy as np
import pandas as pd
from sklearn.metrics import (
    average_precision_score,
    confusion_matrix,
    precision_recall_fscore_support,
)


@dataclass(frozen=True)
class EvaluationResult:
    metrics: dict[str, object]
    confusion_matrix: pd.DataFrame
    labeled_predictions: pd.DataFrame


def evaluate_predictions(
    predictions: pd.DataFrame,
    truth: pd.DataFrame,
    ledger: pd.DataFrame,
    candidate_scores: pd.DataFrame,
    evidence_weight_threshold: float = 0.0,
) -> EvaluationResult:
    """Evaluate detection and feeder correction against the physical truth."""
    merged = predictions.merge(truth, on="transformer_id", how="left", validate="one_to_one")
    if "reported_feeder_id" not in predictions.columns:
        reported = ledger[["transformer_id", "reported_feeder_id"]]
        merged = merged.merge(reported, on="transformer_id", how="left", validate="one_to_one")
    actual = merged["reported_feeder_id"] != merged["physical_feeder_id"]
    predicted = merged["predicted_is_mislinked"].astype(bool)

    precision, recall, f1, _ = precision_recall_fscore_support(
        actual, predicted, average="binary", zero_division=0
    )
    if "anomaly_score" not in merged.columns:
        raise ValueError("predictions must contain a continuous anomaly_score column")
    anomaly_score = merged["anomaly_score"].astype(float)
    n_actual_errors = int(actual.sum())
    n_actual_correct = int((~actual).sum())
    classes = sorted(set(actual.dropna().astype(bool).tolist()))
    if len(classes) == 2:
        pr_auc = float(average_precision_score(actual.astype(int), anomaly_score))
        pr_auc_applicable = True
        pr_auc_unavailable_reason = None
    else:
        pr_auc = None
        pr_auc_applicable = False
        pr_auc_unavailable_reason = (
            "single_class_all_positive" if classes == [True] else "single_class_all_negative"
        )
    scored_mask = merged["decision"] != "insufficient_data"
    scored_classes = sorted(set(actual[scored_mask].dropna().astype(bool).tolist()))
    if scored_mask.any() and len(scored_classes) == 2:
        pr_auc_scored = float(
            average_precision_score(
                actual[scored_mask].astype(int),
                anomaly_score[scored_mask],
            )
        )
        pr_auc_scored_applicable = True
        pr_auc_scored_unavailable_reason = None
    else:
        pr_auc_scored = None
        pr_auc_scored_applicable = False
        pr_auc_scored_unavailable_reason = "single_class" if scored_classes else "no_scored_samples"
    matrix = confusion_matrix(actual, predicted, labels=[False, True])

    candidate_feeders = sorted(candidate_scores["candidate_feeder_id"].unique().tolist())
    candidate_count = len(candidate_feeders)
    topk: dict[str, float | int | None] = {}
    topk_applicable: dict[str, bool] = {}
    error_rows = merged[actual]
    for k in (1, 2, 3):
        applicable = candidate_count > k
        topk_applicable[f"top{k}"] = applicable
        if not applicable:
            topk[f"top{k}_correction_rate"] = None
            topk[f"top{k}_evaluated_count"] = 0
            topk[f"top{k}_evaluation_coverage"] = None
            continue
        hits = 0
        evaluated = 0
        excluded_total = 0
        for transformer_id in error_rows["transformer_id"]:
            rows = candidate_scores[candidate_scores["transformer_id"] == transformer_id].copy()
            finite_scores = pd.to_numeric(rows["enhanced_score"], errors="coerce").apply(
                lambda value: np.isfinite(value)
            )
            if "available_feature_weight" in rows.columns:
                raw_weights = pd.to_numeric(rows["available_feature_weight"], errors="coerce")
                eligible_mask = (
                    finite_scores
                    & raw_weights.apply(lambda value: np.isfinite(value))
                    & (raw_weights >= evidence_weight_threshold)
                )
            else:
                eligible_mask = finite_scores
            excluded_total += int((~eligible_mask).sum())
            eligible = rows[eligible_mask]
            if len(eligible) < k:
                # 有效候选不足 k，该设备对 Top-k 不可评价
                continue
            ranked = eligible.sort_values(
                ["enhanced_score", "candidate_feeder_id"],
                ascending=[False, True],
            )
            physical = truth.loc[
                truth["transformer_id"] == transformer_id,
                "physical_feeder_id",
            ].iloc[0]
            evaluated += 1
            if physical in ranked["candidate_feeder_id"].head(k).tolist():
                hits += 1
        if evaluated == 0:
            topk[f"top{k}_correction_rate"] = None
        else:
            topk[f"top{k}_correction_rate"] = hits / evaluated
        topk[f"top{k}_evaluated_count"] = evaluated
        topk[f"top{k}_evaluation_coverage"] = (
            evaluated / len(error_rows) if len(error_rows) else None
        )

    metrics: dict[str, object] = {
        "precision": float(precision),
        "recall": float(recall),
        "f1": float(f1),
        "pr_auc": pr_auc,
        "pr_auc_applicable": pr_auc_applicable,
        "pr_auc_unavailable_reason": pr_auc_unavailable_reason,
        "pr_auc_scored": pr_auc_scored,
        "pr_auc_scored_applicable": pr_auc_scored_applicable,
        "pr_auc_scored_unavailable_reason": pr_auc_scored_unavailable_reason,
        **topk,
        "topk_applicable": topk_applicable,
        "excluded_candidate_count": excluded_total,
        "candidate_feeder_count": candidate_count,
        "n_total": len(merged),
        "n_actual_errors": n_actual_errors,
        "n_actual_correct": n_actual_correct,
        "n_predicted": int(predicted.sum()),
        "automatic_coverage": float((merged["decision"] == "automatic_recommendation").mean()),
        "insufficient_data_rate": float((merged["decision"] == "insufficient_data").mean()),
        "scored_coverage": float((merged["decision"] != "insufficient_data").mean()),
    }
    labeled = merged.copy()
    labeled["actual_is_mislinked"] = actual
    return EvaluationResult(
        metrics=metrics,
        confusion_matrix=pd.DataFrame(matrix, index=[False, True], columns=[False, True]),
        labeled_predictions=labeled,
    )


def grouped_scenario_split(metadata: pd.DataFrame, seed: int = 42) -> dict[str, set[str]]:
    """Assign whole scenarios to train/validation/test (60/20/20)."""
    scenario_ids = sorted(metadata["scenario_id"].unique().tolist())
    rng = np.random.default_rng(seed)
    order = rng.permutation(scenario_ids)
    n_train = round(0.6 * len(order))
    n_validation = round(0.2 * len(order))
    return {
        "train": set(order[:n_train].tolist()),
        "validation": set(order[n_train : n_train + n_validation].tolist()),
        "test": set(order[n_train + n_validation :].tolist()),
    }
