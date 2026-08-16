"""Typed configuration models and YAML loading for the verification project."""

from datetime import datetime
from pathlib import Path

import yaml
from pydantic import BaseModel, Field, model_validator


class NetworkConfig(BaseModel):
    feeder_count: int = Field(default=3, ge=2)
    transformers_per_feeder: int = Field(default=8, ge=3)
    hv_kv: float = 110.0
    mv_kv: float = 10.0
    lv_kv: float = 0.4


class ProfileConfig(BaseModel):
    start: datetime = datetime(2026, 1, 1)
    days: int = Field(default=30, ge=1)
    interval_minutes: int = Field(default=15, ge=1)
    power_factor: float = Field(default=0.95, gt=0.0, le=1.0)
    pv_scale: float = Field(default=1.0, ge=0.0, le=10.0)


class ValidationConfig(BaseModel):
    voltage_min_pu: float = 0.90
    voltage_max_pu: float = 1.10
    power_balance_tolerance_mw: float = Field(default=1e-6, gt=0.0)
    transformer_loading_limit_percent: float = Field(default=100.0, gt=0.0)
    terminate_on_critical: bool = True
    critical_violation_types: tuple[str, ...] = (
        "non_convergence",
        "power_balance",
        "voltage_out_of_bounds",
        "transformer_overload",
    )

    @model_validator(mode="after")
    def ordered_limits(self) -> "ValidationConfig":
        if self.voltage_min_pu >= self.voltage_max_pu:
            raise ValueError("voltage_min_pu must be lower than voltage_max_pu")
        return self


class CorruptionConfig(BaseModel):
    ledger_error_rate: float = Field(default=0.20, ge=0.0, le=1.0)
    voltage_noise_std_pu: float = Field(default=0.0005, ge=0.0)
    missing_rate: float = Field(default=0.01, ge=0.0, le=0.5)
    spike_rate: float = Field(default=0.001, ge=0.0, le=0.1)
    time_shift_steps: int = Field(default=0, ge=0, le=8)
    time_shift_device_rate: float = Field(default=0.10, ge=0.0, le=1.0)


class ScoringConfig(BaseModel):
    current_score_threshold: float = 0.70
    margin_threshold: float = 0.08
    minimum_coverage: float = 0.80
    minimum_pairs: int = Field(default=16, ge=2)
    rolling_window: int = Field(default=24, ge=4)
    event_quantile: float = Field(default=0.90, gt=0.0, lt=1.0)
    interpolation_limit: int = Field(default=2, ge=1)
    evidence_weight_threshold: float = Field(default=0.5, ge=0.0, le=1.0)


class AppConfig(BaseModel):
    random_seed: int = 42
    network: NetworkConfig = NetworkConfig()
    profiles: ProfileConfig = ProfileConfig()
    validation: ValidationConfig = ValidationConfig()
    corruption: CorruptionConfig = CorruptionConfig()
    scoring: ScoringConfig = ScoringConfig()
    output_root: Path = Path("runs")


def load_config(path: Path) -> AppConfig:
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return AppConfig.model_validate(raw)
