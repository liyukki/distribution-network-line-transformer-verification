import numpy as np
import pandas as pd
import pytest

from ltverify.features import build_candidate_features, safe_corr
from ltverify.preprocessing import PreparedMeasurements


def candidate_feature_fixture():
    index = pd.date_range("2026-01-01", periods=192, freq="15min")
    steps = np.arange(192)
    common = 0.02 * np.sin(2 * np.pi * steps / 96.0)
    f01_pattern = 0.03 * np.where((steps // 12) % 2 == 0, 1.0, -1.0)
    f02_pattern = 0.004 * np.sin(2 * np.pi * steps / 48.0 + 0.3)
    rng = np.random.default_rng(7)
    noise = rng.normal(0.0, 0.002, size=(192, 6))
    transformers = ["T001", "T002", "T003", "T004", "T005", "T006"]
    voltage: dict[str, np.ndarray] = {}
    active_power: dict[str, np.ndarray] = {}
    for column, transformer_id in enumerate(transformers):
        pattern = f01_pattern if column < 3 else f02_pattern
        voltage[transformer_id] = common + pattern + noise[:, column]
        active_power[transformer_id] = common + pattern + 0.5 * noise[:, column]
    voltage_wide = pd.DataFrame(voltage, index=index)
    p_wide = pd.DataFrame(active_power, index=index)
    residual_voltage_wide = voltage_wide.sub(voltage_wide.median(axis=1), axis=0)
    prepared = PreparedMeasurements(
        long_form=pd.DataFrame(),
        voltage_wide=voltage_wide,
        residual_voltage_wide=residual_voltage_wide,
        voltage_diff_wide=voltage_wide.diff(),
        p_wide=p_wide,
        q_wide=p_wide * 0.3,
        coverage=pd.Series(1.0, index=transformers),
    )
    ledger = pd.DataFrame(
        {
            "transformer_id": transformers,
            "reported_feeder_id": ["F01", "F01", "F01", "F02", "F02", "F02"],
        }
    )
    feeder_rows = []
    for feeder_id, pattern in [("F01", f01_pattern), ("F02", f02_pattern)]:
        for timestamp, value in zip(index, common + pattern):
            feeder_rows.append(
                {
                    "timestamp": timestamp,
                    "feeder_id": feeder_id,
                    "head_voltage_pu": 1.0,
                    "p_mw": value,
                    "q_mvar": 0.3 * value,
                }
            )
    feeder_measurements = pd.DataFrame(feeder_rows)
    return prepared, ledger, feeder_measurements


def test_candidate_features_favor_matching_feeder() -> None:
    prepared, ledger, feeder_measurements = candidate_feature_fixture()
    features = build_candidate_features(
        prepared,
        ledger,
        feeder_measurements,
        rolling_window=24,
        event_quantile=0.90,
    )
    t1 = features.query("transformer_id == 'T001'").set_index("candidate_feeder_id")
    assert t1.loc["F01", "diff_corr"] > t1.loc["F02", "diff_corr"]
    assert t1.loc["F01", "event_match"] > t1.loc["F02", "event_match"]


def test_one_device_group_yields_zero_peers_and_nan_features() -> None:
    prepared, _, feeder_measurements = candidate_feature_fixture()
    ledger = pd.DataFrame(
        {
            "transformer_id": ["T001", "T002"],
            "reported_feeder_id": ["F01", "F02"],
        }
    )
    features = build_candidate_features(
        prepared,
        ledger,
        feeder_measurements,
        rolling_window=24,
        event_quantile=0.90,
    )
    t1 = features.query("transformer_id == 'T001'").set_index("candidate_feeder_id")
    assert t1.loc["F01", "peer_count"] == 0
    assert pd.isna(t1.loc["F01", "raw_corr"])
    assert pd.isna(t1.loc["F01", "diff_corr"])
    assert pd.isna(t1.loc["F01", "event_match"])


def test_features_never_contain_truth_columns() -> None:
    prepared, ledger, feeder_measurements = candidate_feature_fixture()
    features = build_candidate_features(
        prepared,
        ledger,
        feeder_measurements,
        rolling_window=24,
        event_quantile=0.90,
    )
    forbidden = {"physical_feeder_id", "is_mislinked", "seed"}
    assert not forbidden & set(features.columns)


def test_safe_corr_requires_minimum_pairs() -> None:
    left = pd.Series([1.0, 2.0, 3.0])
    right = pd.Series([1.0, 2.0, 3.0])
    assert pd.isna(safe_corr(left, right, minimum_pairs=16))
    assert safe_corr(left, right, minimum_pairs=3) == pytest.approx(1.0)


def test_legal_feeder_without_ledger_members_stays_in_features() -> None:
    prepared, ledger, feeder_measurements = candidate_feature_fixture()
    trimmed = ledger[ledger["reported_feeder_id"] != "F02"]
    features = build_candidate_features(
        prepared, trimmed, feeder_measurements, rolling_window=24, event_quantile=0.90
    )
    assert "F02" in set(features["candidate_feeder_id"])
    f02_rows = features[
        (features["transformer_id"] == "T001")
        & (features["candidate_feeder_id"] == "F02")
    ]
    assert f02_rows["peer_count"].iloc[0] == 0
    assert pd.isna(f02_rows["raw_corr"].iloc[0])
    assert np.isfinite(f02_rows["active_power_corr"].iloc[0])


def test_features_include_evidence_weight() -> None:
    prepared, ledger, feeder_measurements = candidate_feature_fixture()
    features = build_candidate_features(
        prepared, ledger, feeder_measurements, rolling_window=24, event_quantile=0.90
    )
    assert "available_feature_weight" in features.columns
    assert features["available_feature_weight"].between(0.0, 1.0).all()
