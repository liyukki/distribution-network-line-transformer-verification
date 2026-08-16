"""Baseline and enhanced candidate scoring with conservative diagnosis.

Baseline score is the raw voltage correlation. Enhanced score is the
weighted mean of correlation features mapped from [-1, 1] to [0, 1] plus
the event-match Jaccard, with weights renormalized over the features that
are actually available. Coverage is a gate for the diagnosis, never a
score component.
"""

from dataclasses import asdict, dataclass

import numpy as np
import pandas as pd

from ltverify.config import ScoringConfig


@dataclass(frozen=True)
class ScoreWeights:
    raw_corr: float = 0.10
    residual_corr: float = 0.20
    diff_corr: float = 0.30
    rolling_corr_median: float = 0.15
    rolling_corr_q10: float = 0.10
    event_match: float = 0.10
    active_power_corr: float = 0.05


_CORRELATION_FEATURES = (
    "raw_corr",
    "residual_corr",
    "diff_corr",
    "rolling_corr_median",
    "rolling_corr_q10",
    "active_power_corr",
)

_ALL_FEATURE_NAMES = _CORRELATION_FEATURES + ("event_match",)

PREDICTION_COLUMNS = [
    "transformer_id",
    "reported_feeder_id",
    "recommended_feeder_id",
    "current_score",
    "best_score",
    "margin",
    "coverage",
    "predicted_is_mislinked",
    "confidence",
    "decision",
    "anomaly_score",
]


def score_candidates(features: pd.DataFrame, weights: ScoreWeights) -> pd.DataFrame:
    """Append baseline and enhanced scores to the candidate feature frame."""
    scored = features.copy()
    weight_map = asdict(weights)

    def enhanced_for_row(row: pd.Series) -> float:
        total = 0.0
        weight_sum = 0.0
        for name in _CORRELATION_FEATURES:
            value = row[name]
            if pd.notna(value):
                total += weight_map[name] * (float(value) + 1.0) / 2.0
                weight_sum += weight_map[name]
        event = row["event_match"]
        if pd.notna(event):
            total += weight_map["event_match"] * float(event)
            weight_sum += weight_map["event_match"]
        return total / weight_sum if weight_sum > 0 else float("nan")

    def evidence_for_row(row: pd.Series) -> float:
        available = 0.0
        total_weight = 0.0
        for name in _ALL_FEATURE_NAMES:
            total_weight += weight_map[name]
            if pd.notna(row[name]):
                available += weight_map[name]
        return available / total_weight if total_weight > 0 else 0.0

    scored["baseline_score"] = scored["raw_corr"]
    scored["enhanced_score"] = scored.apply(enhanced_for_row, axis=1)
    scored["available_feature_weight"] = scored.apply(evidence_for_row, axis=1)
    return scored


def diagnose(scored: pd.DataFrame, ledger: pd.DataFrame, cfg: ScoringConfig) -> pd.DataFrame:
    """Decide per transformer whether the reported feeder is wrong.

    Every key evidence value (coverage, current score, best score, margin,
    evidence weight) must be finite and above its configured gate before a
    decision other than insufficient_data is allowed. The margin is computed
    whenever both scores are finite, independent of the final decision.
    """
    rows: list[dict[str, object]] = []
    for transformer_id, group in scored.groupby("transformer_id", sort=True):
        reported = ledger.loc[
            ledger["transformer_id"] == transformer_id, "reported_feeder_id"
        ].iloc[0]
        current_rows = group[group["candidate_feeder_id"] == reported]
        current_score = (
            float(current_rows["enhanced_score"].iloc[0]) if len(current_rows) else float("nan")
        )
        if "available_feature_weight" in scored.columns and len(current_rows):
            current_weight = float(current_rows["available_feature_weight"].iloc[0])
        else:
            current_weight = 1.0
        others = group[group["candidate_feeder_id"] != reported]
        coverage = float(group["coverage"].iloc[0])
        best_score = float("nan")
        recommended: object = reported
        valid_others = others.dropna(subset=["enhanced_score"])
        if "available_feature_weight" in scored.columns:
            valid_others = valid_others[
                valid_others["available_feature_weight"] >= cfg.evidence_weight_threshold
            ]
        if len(valid_others):
            best_index = valid_others["enhanced_score"].idxmax()
            best_score = float(valid_others.loc[best_index, "enhanced_score"])
            best_candidate = valid_others.loc[best_index, "candidate_feeder_id"]

        margin = (
            best_score - current_score
            if pd.notna(best_score) and pd.notna(current_score)
            else float("nan")
        )
        evidence_complete = (
            pd.notna(coverage)
            and coverage >= cfg.minimum_coverage
            and pd.notna(current_score)
            and pd.notna(best_score)
            and pd.notna(margin)
            and pd.notna(current_weight)
            and current_weight >= cfg.evidence_weight_threshold
        )

        decision = "no_change"
        predicted = False
        confidence = 0.0
        if not evidence_complete:
            decision = "insufficient_data"
        elif current_score < cfg.current_score_threshold and margin > cfg.margin_threshold:
            decision = "automatic_recommendation"
            predicted = True
            recommended = best_candidate
            confidence = coverage * float(
                np.clip(
                    (margin - cfg.margin_threshold) / (1.0 - cfg.margin_threshold),
                    0.0,
                    1.0,
                )
            )

        rows.append(
            {
                "transformer_id": transformer_id,
                "reported_feeder_id": reported,
                "recommended_feeder_id": recommended,
                "current_score": current_score,
                "best_score": best_score,
                "margin": margin,
                "coverage": coverage,
                "predicted_is_mislinked": predicted,
                "confidence": confidence,
                "decision": decision,
            }
        )
    frame = pd.DataFrame(rows, columns=PREDICTION_COLUMNS)
    frame["anomaly_score"] = 0.0
    scored_mask = frame["decision"] != "insufficient_data"
    frame.loc[scored_mask, "anomaly_score"] = frame.loc[scored_mask, "coverage"] * np.minimum(
        1.0 - frame.loc[scored_mask, "current_score"],
        np.maximum(frame.loc[scored_mask, "margin"], 0.0),
    )
    return frame
