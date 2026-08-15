"""Candidate feeder feature engineering.

Builds one row per transformer-candidate-feeder pair with explainable
similarity features. The legal candidate set comes from the feeder
measurements; the reported ledger only defines peer groups. Peer centers
always exclude the candidate transformer itself, and the physical truth is
never read or aggregated here.
"""

import numpy as np
import pandas as pd

from ltverify.contracts import DataContractError
from ltverify.preprocessing import PreparedMeasurements

FEATURE_COLUMNS = [
    "transformer_id",
    "reported_feeder_id",
    "candidate_feeder_id",
    "peer_count",
    "raw_corr",
    "residual_corr",
    "diff_corr",
    "rolling_corr_median",
    "rolling_corr_q10",
    "event_match",
    "active_power_corr",
    "coverage",
]


def safe_corr(left: pd.Series, right: pd.Series, minimum_pairs: int = 16) -> float:
    """Pearson correlation over common valid points, NaN when unreliable."""
    paired = pd.concat([left, right], axis=1).dropna()
    if (
        len(paired) < minimum_pairs
        or paired.iloc[:, 0].std() == 0
        or paired.iloc[:, 1].std() == 0
    ):
        return float("nan")
    return float(paired.iloc[:, 0].corr(paired.iloc[:, 1]))


def _event_mask(series: pd.Series, quantile: float) -> pd.Series:
    differences = series.diff().abs()
    threshold = differences.quantile(quantile)
    return differences > threshold


def _jaccard(left: pd.Series, right: pd.Series) -> float:
    left_bool = left.fillna(False).astype(bool)
    right_bool = right.fillna(False).astype(bool)
    union = int((left_bool | right_bool).sum())
    if union == 0:
        return float("nan")
    return float(int((left_bool & right_bool).sum()) / union)


def _peer_features(
    candidate: pd.Series,
    residual: pd.Series,
    diff: pd.Series,
    center: pd.Series,
    residual_center: pd.Series,
    diff_center: pd.Series,
    rolling_window: int,
    event_quantile: float,
    minimum_pairs: int,
) -> dict[str, float]:
    rolling = candidate.rolling(
        rolling_window, min_periods=rolling_window // 2
    ).corr(diff_center)
    valid_rolling = rolling.dropna()
    return {
        "raw_corr": safe_corr(candidate, center, minimum_pairs=minimum_pairs),
        "residual_corr": safe_corr(
            residual, residual_center, minimum_pairs=minimum_pairs
        ),
        "diff_corr": safe_corr(diff, diff_center, minimum_pairs=minimum_pairs),
        "rolling_corr_median": float(valid_rolling.median())
        if len(valid_rolling)
        else float("nan"),
        "rolling_corr_q10": float(valid_rolling.quantile(0.1))
        if len(valid_rolling)
        else float("nan"),
        "event_match": _jaccard(
            _event_mask(candidate, event_quantile),
            _event_mask(center, event_quantile),
        ),
    }


def build_candidate_features(
    prepared: PreparedMeasurements,
    ledger: pd.DataFrame,
    feeder_measurements: pd.DataFrame,
    rolling_window: int,
    event_quantile: float,
    minimum_pairs: int = 16,
) -> pd.DataFrame:
    """Return one feature row per transformer-candidate-feeder pair.

    Candidate feeders are the legal feeders present in feeder_measurements;
    a corrupted ledger can therefore never remove a legal feeder from the
    candidate set. Voltage shape features require at least two ledger peers,
    while active_power_corr is computed whenever a legal feeder measurement
    exists.
    """
    duplicated = feeder_measurements.duplicated(
        subset=["timestamp", "feeder_id"], keep=False
    )
    if duplicated.any():
        examples = feeder_measurements.loc[
            duplicated, ["timestamp", "feeder_id"]
        ].head(3).to_dict("records")
        raise DataContractError(f"duplicate timestamp-feeder pairs: {examples}")

    voltage = prepared.voltage_wide
    residual = prepared.residual_voltage_wide
    diff = prepared.voltage_diff_wide
    p_wide = prepared.p_wide
    feeder_p = feeder_measurements.pivot_table(
        index="timestamp", columns="feeder_id", values="p_mw", aggfunc="first"
    )
    candidate_feeders = sorted(
        feeder_measurements["feeder_id"].unique().tolist()
    )

    rows: list[dict[str, object]] = []
    for transformer_id in ledger["transformer_id"]:
        reported = ledger.loc[
            ledger["transformer_id"] == transformer_id, "reported_feeder_id"
        ].iloc[0]
        coverage = float(prepared.coverage.get(transformer_id, np.nan))
        for candidate in candidate_feeders:
            members = ledger.loc[
                ledger["reported_feeder_id"] == candidate, "transformer_id"
            ].tolist()
            peers = [member for member in members if member != transformer_id]
            peer_count = len(peers)
            if candidate in feeder_p.columns:
                active_power_corr = safe_corr(
                    p_wide[transformer_id],
                    feeder_p[candidate],
                    minimum_pairs=minimum_pairs,
                )
            else:
                active_power_corr = float("nan")
            if peer_count >= 2:
                center = voltage[peers].median(axis=1)
                residual_center = residual[peers].median(axis=1)
                diff_center = diff[peers].median(axis=1)
                computed = _peer_features(
                    voltage[transformer_id],
                    residual[transformer_id],
                    diff[transformer_id],
                    center,
                    residual_center,
                    diff_center,
                    rolling_window,
                    event_quantile,
                    minimum_pairs,
                )
            else:
                computed = {
                    "raw_corr": float("nan"),
                    "residual_corr": float("nan"),
                    "diff_corr": float("nan"),
                    "rolling_corr_median": float("nan"),
                    "rolling_corr_q10": float("nan"),
                    "event_match": float("nan"),
                }
            rows.append(
                {
                    "transformer_id": transformer_id,
                    "reported_feeder_id": reported,
                    "candidate_feeder_id": candidate,
                    "peer_count": peer_count,
                    **computed,
                    "active_power_corr": active_power_corr,
                    "coverage": coverage,
                }
            )

    return pd.DataFrame(rows, columns=FEATURE_COLUMNS)
