import numpy as np
import pandas as pd
import pytest

from ltverify.contracts import DataContractError
from ltverify.preprocessing import prepare_measurements

SHORT_GAP_TIME = pd.Timestamp("2026-01-01 02:00:00")
LONG_GAP_START = pd.Timestamp("2026-01-01 04:15:00")
LONG_GAP_END = pd.Timestamp("2026-01-01 05:00:00")
LONG_GAP_MIDDLE = pd.Timestamp("2026-01-01 05:00:00")


def measurement_fixture_with_one_and_four_step_gaps() -> pd.DataFrame:
    index = pd.date_range("2026-01-01 00:00", periods=25, freq="15min")
    rows = []
    for transformer_id in ("T001", "T002"):
        for timestamp in index:
            voltage = 1.0
            if transformer_id == "T001" and timestamp == SHORT_GAP_TIME:
                voltage = np.nan
            if transformer_id == "T002" and LONG_GAP_START <= timestamp <= LONG_GAP_END:
                voltage = np.nan
            rows.append(
                {
                    "timestamp": timestamp,
                    "transformer_id": transformer_id,
                    "voltage_pu": voltage,
                    "p_mw": 0.1,
                    "q_mvar": 0.03,
                    "data_quality_flag": "clean",
                }
            )
    return pd.DataFrame(rows)


def test_preprocessing_interpolates_short_gap_and_retains_long_gap() -> None:
    frame = measurement_fixture_with_one_and_four_step_gaps()
    prepared = prepare_measurements(
        frame,
        interval_minutes=15,
        interpolation_limit=2,
        minimum_coverage=0.75,
    )
    assert prepared.voltage_wide.loc[SHORT_GAP_TIME, "T001"] == pytest.approx(1.0)
    assert pd.isna(prepared.voltage_wide.loc[LONG_GAP_MIDDLE, "T002"])
    assert np.nanmax(np.abs(prepared.residual_voltage_wide.median(axis=1))) < 1e-12
    assert "physical_feeder_id" not in prepared.long_form.columns
    # q_wide belongs to the prepared-data contract (planned reactive-power
    # extension); it must stay aligned with the other wide frames.
    assert list(prepared.q_wide.columns) == ["T001", "T002"]
    assert prepared.q_wide.shape == prepared.voltage_wide.shape


def test_duplicate_pairs_raise_domain_error() -> None:
    frame = measurement_fixture_with_one_and_four_step_gaps()
    duplicated = pd.concat([frame, frame.iloc[[0]]], ignore_index=True)
    with pytest.raises(DataContractError, match="duplicate timestamp-transformer pairs"):
        prepare_measurements(duplicated, 15, 2, 0.75)


def test_low_coverage_device_is_retained_but_flagged() -> None:
    frame = measurement_fixture_with_one_and_four_step_gaps()
    mask = (frame["transformer_id"] == "T002") & (
        frame["timestamp"] <= pd.Timestamp("2026-01-01 03:00:00")
    )
    frame.loc[mask, "voltage_pu"] = np.nan
    prepared = prepare_measurements(frame, 15, 2, 0.75)
    assert "T002" in prepared.voltage_wide.columns
    assert prepared.coverage["T002"] < 0.75
