from pathlib import Path

import pytest
from pydantic import ValidationError

from ltverify.config import load_config


def test_default_config_has_fixed_first_release_shape() -> None:
    cfg = load_config(Path("configs/default.yaml"))
    assert cfg.network.feeder_count == 3
    assert cfg.network.transformers_per_feeder == 8
    assert cfg.profiles.days == 30
    assert cfg.profiles.interval_minutes == 15
    assert cfg.random_seed == 42


def test_invalid_voltage_limits_are_rejected(tmp_path: Path) -> None:
    path = tmp_path / "bad.yaml"
    path.write_text("validation:\n  voltage_min_pu: 1.1\n  voltage_max_pu: 0.9\n", encoding="utf-8")
    with pytest.raises(ValidationError):
        load_config(path)


def test_unknown_critical_violation_type_rejected(tmp_path: Path) -> None:
    path = tmp_path / "bad.yaml"
    path.write_text(
        "validation:\n  critical_violation_types: [bogus_type]\n",
        encoding="utf-8",
    )
    with pytest.raises(ValidationError):
        load_config(path)


def test_duplicate_critical_types_are_normalized() -> None:
    from ltverify.config import ValidationConfig

    config = ValidationConfig(
        critical_violation_types=(
            "transformer_overload",
            "power_balance",
            "transformer_overload",
        )
    )
    assert config.critical_violation_types == (
        "transformer_overload",
        "power_balance",
    )


def test_non_convergence_error_suggests_migration(tmp_path: Path) -> None:
    path = tmp_path / "legacy.yaml"
    path.write_text(
        "validation:\n  critical_violation_types: [non_convergence]\n",
        encoding="utf-8",
    )
    with pytest.raises(ValidationError) as exc_info:
        load_config(path)
    message = str(exc_info.value)
    assert "non_convergence 已改为无条件硬失败，请从列表中移除" in message
