import pandas as pd
import pytest

from ltverify.config import CorruptionConfig, NetworkConfig
from ltverify.contracts import TRANSFORMER_MEASUREMENT_COLUMNS
from ltverify.corruption import build_truth, corrupt_ledger, disturb_measurements
from ltverify.network import build_network


@pytest.fixture
def clean_measurements() -> pd.DataFrame:
    index = pd.date_range("2026-01-01", periods=96, freq="15min")
    records = []
    for transformer_id in [f"T{i:03d}" for i in range(1, 25)]:
        for timestamp in index:
            records.append(
                {
                    "timestamp": timestamp,
                    "transformer_id": transformer_id,
                    "voltage_pu": 1.0,
                    "p_mw": 0.1,
                    "q_mvar": 0.03,
                    "data_quality_flag": "clean",
                }
            )
    return pd.DataFrame(records)


def test_twenty_percent_ledger_corruption_changes_five_of_twenty_four() -> None:
    truth = build_truth(build_network(NetworkConfig()))
    ledger = corrupt_ledger(truth, rate=0.20, seed=42)
    merged = ledger.merge(truth, on="transformer_id", validate="one_to_one")
    changed = merged["reported_feeder_id"] != merged["physical_feeder_id"]
    assert changed.sum() == 5
    assert "physical_feeder_id" not in ledger.columns
    assert "is_mislinked" not in ledger.columns


def test_disturbance_is_deterministic_and_preserves_schema(
    clean_measurements: pd.DataFrame,
) -> None:
    cfg = CorruptionConfig(missing_rate=0.05, spike_rate=0.01)
    first = disturb_measurements(clean_measurements, cfg, seed=42)
    second = disturb_measurements(clean_measurements, cfg, seed=42)
    pd.testing.assert_frame_equal(first, second)
    assert set(TRANSFORMER_MEASUREMENT_COLUMNS) <= set(first.columns)
    assert first["voltage_pu"].isna().sum() > 0
    assert first["data_quality_flag"].str.contains("missing|spike|noisy").any()
