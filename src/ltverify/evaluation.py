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
    metrics: dict[str, float | int]
    confusion_matrix: pd.DataFrame
    labeled_predictions: pd.DataFrame


def evaluate_predictions(
    predictions: pd.DataFrame,
    truth: pd.DataFrame,
    ledger: pd.DataFrame,
    candidate_scores: pd.DataFrame,
) -> EvaluationResult:
    """Evaluate detection and feeder correction against the physical truth."""
    merged = predictions.merge(
        truth, on="transformer_id", how="left", validate="one_to_one"
    )
    if "reported_feeder_id" not in predictions.columns:
        reported = ledger[["transformer_id", "reported_feeder_id"]]
        merged = merged.merge(
            reported, on="transformer_id", how="left", validate="one_to_one"
        )
    actual = merged["reported_feeder_id"] != merged["physical_feeder_id"]
    predicted = merged["predicted_is_mislinked"].astype(bool)

    precision, recall, f1, _ = precision_recall_fscore_support(
        actual, predicted, average="binary", zero_division=0
    )
    if "anomaly_score" not in merged.columns:
        raise ValueError(
            "predictions must contain a continuous anomaly_score column"
        )
    anomaly_score = merged["anomaly_score"].astype(float)
    pr_auc = average_precision_score(actual.astype(int), anomaly_score)
    matrix = confusion_matrix(actual, predicted, labels=[False, True])

    candidate_feeders = sorted(
        candidate_scores["candidate_feeder_id"].unique().tolist()
    )
    candidate_count = len(candidate_feeders)
    topk: dict[str, float | None] = {}
    topk_applicable: dict[str, bool] = {}
    error_rows = merged[actual]
    for k in (1, 2, 3):
        applicable = candidate_count > k
        topk_applicable[f"top{k}"] = applicable
        if not applicable:
            topk[f"top{k}_correction_rate"] = None
            continue
        if len(error_rows):
            hits = 0
            for transformer_id in error_rows["transformer_id"]:
                scores = candidate_scores[
                    candidate_scores["transformer_id"] == transformer_id
                ].sort_values("enhanced_score", ascending=False)
                physical = truth.loc[
                    truth["transformer_id"] == transformer_id,
                    "physical_feeder_id",
                ].iloc[0]
                if physical in scores["candidate_feeder_id"].head(k).tolist():
                    hits += 1
            topk[f"top{k}_correction_rate"] = hits / len(error_rows)
        else:
            topk[f"top{k}_correction_rate"] = float("nan")

    metrics: dict[str, float | int | None] = {
        "precision": float(precision),
        "recall": float(recall),
        "f1": float(f1),
        "pr_auc": float(pr_auc),
        **topk,
        "topk_applicable": topk_applicable,
        "candidate_feeder_count": candidate_count,
        "n_total": len(merged),
        "n_actual_errors": int(actual.sum()),
        "n_predicted": int(predicted.sum()),
        "automatic_coverage": float(
            (merged["decision"] == "automatic_recommendation").mean()
        ),
        "insufficient_data_rate": float(
            (merged["decision"] == "insufficient_data").mean()
        ),
        "scored_coverage": float(
            (merged["decision"] != "insufficient_data").mean()
        ),
    }
    labeled = merged.copy()
    labeled["actual_is_mislinked"] = actual
    return EvaluationResult(
        metrics=metrics,
        confusion_matrix=pd.DataFrame(
            matrix, index=[False, True], columns=[False, True]
        ),
        labeled_predictions=labeled,
    )


def grouped_scenario_split(
    metadata: pd.DataFrame, seed: int = 42
) -> dict[str, set[str]]:
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
