"""Data table contracts: required column sets and domain validation errors.

Column sets follow the core table schemas in the design spec (section 6.2):
transformer measurements, feeder measurements, reported ledger, and truth
topology.
"""

from collections.abc import Collection

import pandas as pd


class DataContractError(ValueError):
    """Raised when a dataframe violates a declared data contract."""


TRANSFORMER_MEASUREMENT_COLUMNS = frozenset(
    {
        "timestamp",
        "transformer_id",
        "voltage_pu",
        "p_mw",
        "q_mvar",
        "data_quality_flag",
    }
)

FEEDER_MEASUREMENT_COLUMNS = frozenset(
    {"timestamp", "feeder_id", "head_voltage_pu", "p_mw", "q_mvar"}
)

LEDGER_COLUMNS = frozenset(
    {
        "transformer_id",
        "reported_feeder_id",
        "transformer_capacity_kva",
        "customer_type",
    }
)

TRUTH_COLUMNS = frozenset({"transformer_id", "physical_feeder_id"})


def validate_columns(frame: pd.DataFrame, required: Collection[str], table_name: str) -> None:
    missing = sorted(set(required) - set(frame.columns))
    if missing:
        raise DataContractError(f"{table_name} missing columns: {', '.join(missing)}")
