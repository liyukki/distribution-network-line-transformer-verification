"""Measurement preprocessing and common-mode removal.

Aligns long-form measurements onto the regular sampling grid, interpolates
short gaps only, computes per-device coverage before interpolation, and
removes the row-median common voltage mode so that residual correlations
reflect feeder-local behaviour.
"""

from dataclasses import dataclass

import pandas as pd

from ltverify.contracts import DataContractError


@dataclass(frozen=True)
class PreparedMeasurements:
    long_form: pd.DataFrame
    voltage_wide: pd.DataFrame
    residual_voltage_wide: pd.DataFrame
    voltage_diff_wide: pd.DataFrame
    p_wide: pd.DataFrame
    q_wide: pd.DataFrame
    coverage: pd.Series


def prepare_measurements(
    frame: pd.DataFrame,
    interval_minutes: int,
    interpolation_limit: int,
    minimum_coverage: float,
) -> PreparedMeasurements:
    """Validate, align, interpolate and de-trend long-form measurements.

    minimum_coverage is accepted for interface compatibility with the plan
    contract; the coverage threshold gate itself is applied downstream in
    the diagnosis stage. Devices with low coverage stay in the exported
    data with their coverage value so the diagnosis can refuse automatic
    recommendations instead of silently dropping them.
    """
    if frame.duplicated(subset=["timestamp", "transformer_id"]).any():
        raise DataContractError("duplicate timestamp-transformer pairs")

    long_form = frame.copy().reset_index(drop=True)
    coverage = long_form.groupby("transformer_id")["voltage_pu"].apply(
        lambda series: float(series.notna().mean())
    )

    full_index = pd.date_range(
        start=long_form["timestamp"].min(),
        end=long_form["timestamp"].max(),
        freq=pd.Timedelta(minutes=interval_minutes),
    )

    def to_wide(column: str) -> pd.DataFrame:
        wide = long_form.pivot_table(
            index="timestamp",
            columns="transformer_id",
            values=column,
            aggfunc="first",
        )
        return wide.reindex(full_index)

    voltage_wide = to_wide("voltage_pu")
    p_wide = to_wide("p_mw")
    # q_wide is part of the prepared-data contract for the planned
    # reactive-power extension; it has no consumer in the first release
    # but is kept (with contract tests) instead of being deleted.
    q_wide = to_wide("q_mvar")

    voltage_wide = voltage_wide.interpolate(
        method="time", limit=interpolation_limit, limit_area="inside"
    )
    p_wide = p_wide.interpolate(method="time", limit=interpolation_limit, limit_area="inside")
    q_wide = q_wide.interpolate(method="time", limit=interpolation_limit, limit_area="inside")

    common_mode = voltage_wide.median(axis=1)
    residual_voltage_wide = voltage_wide.sub(common_mode, axis=0)
    voltage_diff_wide = voltage_wide.diff()

    return PreparedMeasurements(
        long_form=long_form,
        voltage_wide=voltage_wide,
        residual_voltage_wide=residual_voltage_wide,
        voltage_diff_wide=voltage_diff_wide,
        p_wide=p_wide,
        q_wide=q_wide,
        coverage=coverage,
    )
