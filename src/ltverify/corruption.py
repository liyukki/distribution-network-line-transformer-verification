"""Truth isolation, ledger corruption and measurement disturbances.

The physical truth stays in a separate frame that only the evaluation stage
reads. Ledger corruption modifies a copy of the reported assignment, never
the pandapower network. Measurement disturbances deep-copy the clean frame
and add noise, missing values, spikes and per-device time shifts.
"""

import numpy as np
import pandas as pd

from ltverify.config import CorruptionConfig
from ltverify.network import NetworkArtifacts

_TRUTH_COLUMNS = [
    "transformer_id",
    "physical_feeder_id",
    "transformer_capacity_kva",
    "customer_type",
]
_LEDGER_COLUMNS = [
    "transformer_id",
    "reported_feeder_id",
    "transformer_capacity_kva",
    "customer_type",
]
_FLAG_ORDER = ("noisy", "missing", "spike", "shifted")
_SPIKE_MAGNITUDE_PU = 0.05


def build_truth(artifacts: NetworkArtifacts) -> pd.DataFrame:
    """Export the physical topology truth for evaluation only."""
    return artifacts.asset_table[_TRUTH_COLUMNS].copy()


def corrupt_ledger(truth: pd.DataFrame, rate: float, seed: int) -> pd.DataFrame:
    """Corrupt a reported ledger copy; the truth frame is never modified."""
    rng = np.random.default_rng(seed)
    ledger = truth.rename(columns={"physical_feeder_id": "reported_feeder_id"}).copy()
    count = round(rate * len(ledger))
    targets = rng.choice(
        ledger["transformer_id"].to_numpy(), size=count, replace=False
    )
    feeders = sorted(ledger["reported_feeder_id"].unique().tolist())
    for transformer_id in targets:
        physical = truth.loc[
            truth["transformer_id"] == transformer_id, "physical_feeder_id"
        ].iloc[0]
        candidates = [feeder for feeder in feeders if feeder != physical]
        ledger.loc[
            ledger["transformer_id"] == transformer_id, "reported_feeder_id"
        ] = rng.choice(candidates)
    return ledger[_LEDGER_COLUMNS]


def disturb_measurements(
    clean: pd.DataFrame, cfg: CorruptionConfig, seed: int
) -> pd.DataFrame:
    """Add noise, missing values, spikes and time shifts to a deep copy."""
    frame = clean.copy(deep=True).reset_index(drop=True)
    rng = np.random.default_rng(seed)
    row_count = len(frame)
    flags: dict[int, set[str]] = {index: set() for index in range(row_count)}

    if cfg.voltage_noise_std_pu > 0:
        noise = rng.normal(0.0, cfg.voltage_noise_std_pu, size=row_count)
        frame["voltage_pu"] = frame["voltage_pu"] + noise
        for index in range(row_count):
            flags[index].add("noisy")

    missing_indices: np.ndarray = np.array([], dtype=int)
    if cfg.missing_rate > 0:
        missing_count = round(cfg.missing_rate * row_count)
        missing_indices = rng.choice(
            row_count, size=missing_count, replace=False
        )
        frame.loc[missing_indices, ["voltage_pu", "p_mw", "q_mvar"]] = np.nan
        for index in missing_indices:
            flags[int(index)].add("missing")

    if cfg.spike_rate > 0:
        spike_count = round(cfg.spike_rate * row_count)
        missing_set = set(missing_indices.tolist())
        available = np.array(
            [index for index in range(row_count) if index not in missing_set]
        )
        spike_indices = rng.choice(
            available, size=min(spike_count, len(available)), replace=False
        )
        signs = rng.choice([-1.0, 1.0], size=len(spike_indices))
        frame.loc[spike_indices, "voltage_pu"] += (
            signs * _SPIKE_MAGNITUDE_PU
        )
        for index in spike_indices:
            flags[int(index)].add("spike")

    if cfg.time_shift_steps > 0:
        device_count = frame["transformer_id"].nunique()
        shift_count = max(1, round(cfg.time_shift_device_rate * device_count))
        devices = rng.choice(
            frame["transformer_id"].unique(), size=shift_count, replace=False
        )
        value_columns = ["voltage_pu", "p_mw", "q_mvar"]
        for device in devices:
            mask = frame["transformer_id"] == device
            shifted = frame.loc[mask, value_columns].shift(cfg.time_shift_steps)
            frame.loc[mask, value_columns] = shifted.to_numpy()
            for index in frame.index[mask]:
                flags[int(index)].add("shifted")

    for index, tag_set in flags.items():
        if tag_set:
            frame.at[index, "data_quality_flag"] = "|".join(
                name for name in _FLAG_ORDER if name in tag_set
            )
    return frame
