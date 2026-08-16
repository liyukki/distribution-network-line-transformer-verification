"""Deterministic load and photovoltaic profile generation.

Every profile is built from an explicit random seed. Load profiles combine a
customer-type daily shape, a weekday/weekend factor, a feeder-level
sinusoid, a per-transformer scale sampled once and clipped AR(1) noise.
Photovoltaic output uses a daylight sine curve (06:00-18:00) with a daily
cloud factor; transformers without a PV sgen keep a zero column.
"""

from dataclasses import dataclass

import numpy as np
import pandas as pd

from ltverify.config import ProfileConfig
from ltverify.network import NetworkArtifacts

_BASE_LOAD_PEAK_MW = 0.15
_WEEKEND_FACTOR = 0.85
_FEEDER_SINUSOID_AMPLITUDE = 0.08
_AR1_COEFFICIENT = 0.85
_NOISE_STD = 0.02
_NOISE_CLIP = 0.06
_TRANSFORMER_SCALE_LOW = 0.8
_TRANSFORMER_SCALE_HIGH = 1.2
_PV_NAMEPLATE_MW = 0.12
_PV_CLOUD_LOW = 0.65
_PV_CLOUD_HIGH = 1.0
_PV_SUNRISE_HOUR = 6.0
_PV_SUNSET_HOUR = 18.0


@dataclass(frozen=True)
class TimeSeriesProfiles:
    index: pd.DatetimeIndex
    load_p_mw: pd.DataFrame
    load_q_mvar: pd.DataFrame
    pv_p_mw: pd.DataFrame


def _hour_of_day(index: pd.DatetimeIndex) -> np.ndarray:
    return index.hour.to_numpy() + index.minute.to_numpy() / 60.0


def _residential_shape(hour: np.ndarray) -> np.ndarray:
    morning = np.exp(-0.5 * ((hour - 7.5) / 1.5) ** 2)
    evening = np.exp(-0.5 * ((hour - 20.0) / 2.0) ** 2)
    return morning + 0.8 * evening


def _commercial_shape(hour: np.ndarray) -> np.ndarray:
    rise = np.clip((hour - 8.0) / 1.5, 0.0, 1.0)
    fall = np.clip((19.0 - hour) / 1.5, 0.0, 1.0)
    return 0.25 + 0.75 * np.minimum(rise, fall)


def _mixed_shape(hour: np.ndarray) -> np.ndarray:
    return 0.5 * (_residential_shape(hour) + _commercial_shape(hour))


_SHAPE_BY_TYPE = {
    "residential": _residential_shape,
    "commercial": _commercial_shape,
    "mixed": _mixed_shape,
}


def _daylight_factor(hour: np.ndarray) -> np.ndarray:
    daylight = np.sin(np.pi * (hour - _PV_SUNRISE_HOUR) / (_PV_SUNSET_HOUR - _PV_SUNRISE_HOUR))
    return np.where(
        (hour >= _PV_SUNRISE_HOUR) & (hour <= _PV_SUNSET_HOUR),
        np.clip(daylight, 0.0, None),
        0.0,
    )


def _ar1_noise(rng: np.random.Generator, steps: int, columns: int) -> np.ndarray:
    noise = np.zeros((steps, columns))
    innovations = rng.normal(0.0, _NOISE_STD, size=(steps, columns))
    noise[0] = innovations[0]
    for step in range(1, steps):
        noise[step] = _AR1_COEFFICIENT * noise[step - 1] + innovations[step]
    return np.clip(noise, -_NOISE_CLIP, _NOISE_CLIP)


def generate_profiles(
    artifacts: NetworkArtifacts, cfg: ProfileConfig, seed: int = 42
) -> TimeSeriesProfiles:
    """Generate deterministic load and PV profiles for every transformer."""
    asset_table = artifacts.asset_table
    transformer_ids = asset_table["transformer_id"].tolist()
    minutes_per_day = 24 * 60
    if minutes_per_day % cfg.interval_minutes != 0:
        raise ValueError(
            "interval_minutes must divide one day exactly (1440 minutes); "
            f"got {cfg.interval_minutes}"
        )
    periods = cfg.days * minutes_per_day // cfg.interval_minutes
    index = pd.date_range(
        start=cfg.start,
        periods=periods,
        freq=pd.Timedelta(minutes=cfg.interval_minutes),
    )
    rng = np.random.default_rng(seed)
    hour = _hour_of_day(index)
    weekday = np.where(index.dayofweek.to_numpy() >= 5, _WEEKEND_FACTOR, 1.0)

    transformer_scales = rng.uniform(
        _TRANSFORMER_SCALE_LOW, _TRANSFORMER_SCALE_HIGH, size=len(transformer_ids)
    )
    feeder_numbers = {
        transformer_id: int(feeder_id[1:]) - 1
        for transformer_id, feeder_id in zip(
            asset_table["transformer_id"], asset_table["physical_feeder_id"]
        )
    }
    noise = _ar1_noise(rng, periods, len(transformer_ids))

    load_p = np.empty((periods, len(transformer_ids)))
    for column, transformer_id in enumerate(transformer_ids):
        feeder_number = feeder_numbers[transformer_id]
        customer_type = asset_table.loc[
            asset_table["transformer_id"] == transformer_id, "customer_type"
        ].iloc[0]
        shape = _SHAPE_BY_TYPE[customer_type](hour)
        shape = shape / shape.max()
        feeder_count = len(feeder_numbers)
        feeder_factor = 1.0 + _FEEDER_SINUSOID_AMPLITUDE * np.sin(
            2.0 * np.pi * hour / 24.0 + 2.0 * np.pi * feeder_number / feeder_count
        )
        column_profile = (
            _BASE_LOAD_PEAK_MW
            * weekday
            * feeder_factor
            * transformer_scales[column]
            * shape
            * (1.0 + noise[:, column])
        )
        load_p[:, column] = np.maximum(column_profile, 0.0)

    q_factor = np.tan(np.arccos(cfg.power_factor))
    load_q = load_p * q_factor

    pv_ids = asset_table.loc[asset_table["pv_index"].notna(), "transformer_id"].tolist()
    pv_p = np.zeros((periods, len(transformer_ids)))
    daylight = _daylight_factor(hour)
    day_starts = index.normalize().unique()
    for transformer_id in pv_ids:
        column = transformer_ids.index(transformer_id)
        clouds = rng.uniform(_PV_CLOUD_LOW, _PV_CLOUD_HIGH, size=len(day_starts))
        cloud_by_step = pd.Series(clouds, index=day_starts).reindex(index.normalize()).to_numpy()
        pv_p[:, column] = _PV_NAMEPLATE_MW * cfg.pv_scale * daylight * cloud_by_step

    return TimeSeriesProfiles(
        index=index,
        load_p_mw=pd.DataFrame(load_p, index=index, columns=transformer_ids),
        load_q_mvar=pd.DataFrame(load_q, index=index, columns=transformer_ids),
        pv_p_mw=pd.DataFrame(pv_p, index=index, columns=transformer_ids),
    )
