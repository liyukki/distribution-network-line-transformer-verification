from pathlib import Path

from ltverify.experiments import (
    ABLATION_FEATURES,
    FAMILY_CONFIG_PATHS,
    expand_experiment_grid,
)


def test_grid_expansion_produces_130_unique_cases() -> None:
    cases = expand_experiment_grid(Path("configs/robustness.yaml"))
    assert len(cases) == 130
    case_ids = [case.case_id for case in cases]
    assert len(set(case_ids)) == 130
    assert all("seed" in case_id for case_id in case_ids)
    assert sum(1 for case in cases if case.family == "ablation") == 30
    sample = next(case for case in cases if case.family == "ledger_error_rate")
    assert sample.case_id.startswith("ledger_error_rate-")
    assert "seed" in sample.case_id
    assert sample.config_overrides == {"corruption.ledger_error_rate": 0.05}


def test_ablation_maps_to_score_weight_fields() -> None:
    all_fields = set(ABLATION_FEATURES["full"])
    assert all_fields == {
        "raw_corr",
        "residual_corr",
        "diff_corr",
        "rolling_corr_median",
        "rolling_corr_q10",
        "event_match",
        "active_power_corr",
    }
    assert "diff_corr" not in ABLATION_FEATURES["without_difference"]
    assert "residual_corr" not in ABLATION_FEATURES["without_residual"]
    assert "rolling_corr_median" not in ABLATION_FEATURES["without_rolling"]
    assert "rolling_corr_q10" not in ABLATION_FEATURES["without_rolling"]
    assert "event_match" not in ABLATION_FEATURES["without_events"]
    assert "active_power_corr" not in ABLATION_FEATURES["without_power"]


def test_family_paths_cover_all_experiment_families() -> None:
    assert set(FAMILY_CONFIG_PATHS) == {
        "ledger_error_rate",
        "voltage_noise_std_pu",
        "missing_rate",
        "time_shift_steps",
        "pv_scale",
    }


def test_case_with_simulation_failure_is_not_completed(
    monkeypatch, tmp_path: Path
) -> None:
    import pandas as pd

    from ltverify.config import NetworkConfig, ProfileConfig, ValidationConfig
    from ltverify.experiments import run_experiments
    from ltverify.network import build_network
    from ltverify.profiles import generate_profiles
    from ltverify.simulation import SimulationResult, simulate_time_series

    artifacts = build_network(NetworkConfig(transformers_per_feeder=3))
    profiles = generate_profiles(
        artifacts, ProfileConfig(days=1, interval_minutes=360), seed=42
    )
    good = simulate_time_series(artifacts, profiles, ValidationConfig())

    def failing_simulate(*args: object, **kwargs: object) -> SimulationResult:
        return SimulationResult(
            transformer_measurements=good.transformer_measurements.copy(),
            feeder_measurements=good.feeder_measurements.copy(),
            failures=pd.DataFrame(
                [
                    {
                        "timestamp": pd.Timestamp("2026-01-01 00:00"),
                        "error_type": "non_convergence",
                        "message": "forced failure",
                    }
                ]
            ),
        )

    monkeypatch.setattr(
        "ltverify.experiments.simulate_time_series", failing_simulate
    )
    base = tmp_path / "small_base.yaml"
    base.write_text(
        f"""random_seed: 42
network:
  feeder_count: 3
  transformers_per_feeder: 3
  hv_kv: 110.0
  mv_kv: 10.0
  lv_kv: 0.4
profiles:
  start: "2026-01-01"
  days: 1
  interval_minutes: 360
  power_factor: 0.95
  pv_scale: 1.0
validation:
  voltage_min_pu: 0.90
  voltage_max_pu: 1.10
corruption:
  ledger_error_rate: 0.10
  voltage_noise_std_pu: 0.0005
  missing_rate: 0.01
  spike_rate: 0.001
  time_shift_steps: 0
  time_shift_device_rate: 0.10
scoring:
  current_score_threshold: 0.70
  margin_threshold: 0.08
  minimum_coverage: 0.80
output_root: {tmp_path.as_posix()}
""",
        encoding="utf-8",
    )
    robustness = tmp_path / "robustness.yaml"
    robustness.write_text(
        f"base_config: {base.as_posix()}\n"
        "experiments:\n"
        "  ledger_error_rate: [0.10]\n"
        "ablation_features: []\n"
        "seeds: [42]\n",
        encoding="utf-8",
    )
    output_dir = tmp_path / "out"
    run_experiments(robustness, output_dir)
    summary = pd.read_csv(output_dir / "experiment_summary.csv")
    assert len(summary) == 1
    assert (summary["status"] == "failed").all()


def test_case_with_critical_violation_is_not_completed(
    monkeypatch, tmp_path: Path
) -> None:
    import pandas as pd

    from ltverify.config import NetworkConfig, ProfileConfig, ValidationConfig
    from ltverify.experiments import run_experiments
    from ltverify.network import build_network
    from ltverify.profiles import generate_profiles
    from ltverify.simulation import SimulationResult, simulate_time_series

    artifacts = build_network(NetworkConfig(transformers_per_feeder=3))
    profiles = generate_profiles(
        artifacts, ProfileConfig(days=1, interval_minutes=360), seed=42
    )
    good = simulate_time_series(artifacts, profiles, ValidationConfig())

    def violating_simulate(*args: object, **kwargs: object) -> SimulationResult:
        return SimulationResult(
            transformer_measurements=good.transformer_measurements.copy(),
            feeder_measurements=good.feeder_measurements.copy(),
            failures=pd.DataFrame(),
            validation=pd.DataFrame(
                [
                    {
                        "timestamp": pd.Timestamp("2026-01-01 00:00"),
                        "converged": True,
                        "voltage_min_pu": 0.85,
                        "voltage_max_pu": 1.0,
                        "maximum_transformer_loading_percent": 150.0,
                        "absolute_power_balance_error_mw": 1e-9,
                        "violation_type": "voltage_out_of_bounds|transformer_overload",
                        "message": "voltage below 0.90 p.u.",
                        "severity": "critical",
                    }
                ]
            ),
        )

    monkeypatch.setattr(
        "ltverify.experiments.simulate_time_series", violating_simulate
    )
    base = tmp_path / "small_base.yaml"
    base.write_text(
        f"""random_seed: 42
network:
  feeder_count: 3
  transformers_per_feeder: 3
  hv_kv: 110.0
  mv_kv: 10.0
  lv_kv: 0.4
profiles:
  start: "2026-01-01"
  days: 1
  interval_minutes: 360
  power_factor: 0.95
  pv_scale: 1.0
validation:
  voltage_min_pu: 0.90
  voltage_max_pu: 1.10
  power_balance_tolerance_mw: 0.000001
  transformer_loading_limit_percent: 100.0
  terminate_on_critical: true
corruption:
  ledger_error_rate: 0.10
  voltage_noise_std_pu: 0.0005
  missing_rate: 0.01
  spike_rate: 0.001
  time_shift_steps: 0
  time_shift_device_rate: 0.10
scoring:
  current_score_threshold: 0.70
  margin_threshold: 0.08
  minimum_coverage: 0.80
output_root: {tmp_path.as_posix()}
""",
        encoding="utf-8",
    )
    robustness = tmp_path / "robustness.yaml"
    robustness.write_text(
        f"""base_config: {base.as_posix()}
experiments:
  ledger_error_rate: [0.10]
ablation_features: []
seeds: [42]
""",
        encoding="utf-8",
    )
    run_experiments(robustness, tmp_path / "out2")
    summary = pd.read_csv(tmp_path / "out2" / "experiment_summary.csv")
    assert len(summary) == 1
    assert (summary["status"] == "failed").all()
