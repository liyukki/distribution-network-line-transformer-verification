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
