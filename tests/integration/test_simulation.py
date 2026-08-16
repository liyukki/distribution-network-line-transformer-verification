import pandas as pd

from ltverify.config import NetworkConfig, ProfileConfig, ValidationConfig
from ltverify.network import build_network
from ltverify.profiles import generate_profiles
from ltverify.simulation import simulate_time_series


def test_short_simulation_emits_transformer_and_feeder_measurements() -> None:
    artifacts = build_network(NetworkConfig())
    profiles = generate_profiles(
        artifacts,
        ProfileConfig(days=1, interval_minutes=360),
        seed=42,
    )
    result = simulate_time_series(artifacts, profiles, ValidationConfig())
    assert len(result.transformer_measurements) == 4 * 24
    assert len(result.feeder_measurements) == 4 * 3
    assert result.failures.empty
    assert result.transformer_measurements["voltage_pu"].between(0.90, 1.10).all()


def test_simulation_is_repeatable() -> None:
    artifacts = build_network(NetworkConfig())
    profiles = generate_profiles(
        artifacts,
        ProfileConfig(days=1, interval_minutes=360),
        seed=42,
    )
    first = simulate_time_series(artifacts, profiles, ValidationConfig())
    second = simulate_time_series(artifacts, profiles, ValidationConfig())
    pd.testing.assert_frame_equal(first.transformer_measurements, second.transformer_measurements)
    pd.testing.assert_frame_equal(first.feeder_measurements, second.feeder_measurements)


def test_high_pv_scenario_produces_reverse_power() -> None:
    artifacts = build_network(NetworkConfig())
    profiles = generate_profiles(
        artifacts,
        ProfileConfig(days=1, interval_minutes=360, pv_scale=6.0),
        seed=42,
    )
    profiles.load_p_mw.iloc[:, :] = profiles.load_p_mw * 0.2
    profiles.load_q_mvar.iloc[:, :] = profiles.load_q_mvar * 0.2
    result = simulate_time_series(artifacts, profiles, ValidationConfig())
    assert result.failures.empty
    assert (result.transformer_measurements["p_mw"] < 0).any()


def test_simulation_records_per_timestep_validation() -> None:
    artifacts = build_network(NetworkConfig())
    profiles = generate_profiles(artifacts, ProfileConfig(days=1, interval_minutes=360), seed=42)
    result = simulate_time_series(artifacts, profiles, ValidationConfig())
    assert len(result.validation) == 4
    required = {
        "timestamp",
        "converged",
        "voltage_min_pu",
        "voltage_max_pu",
        "maximum_transformer_loading_percent",
        "absolute_power_balance_error_mw",
        "violation_type",
        "message",
        "severity",
    }
    assert required <= set(result.validation.columns)
    assert result.validation["converged"].all()


def test_init_falls_back_to_auto_after_non_convergence(monkeypatch) -> None:
    import pandapower as pp

    from ltverify import simulation as simulation_module

    artifacts = build_network(NetworkConfig())
    profiles = generate_profiles(artifacts, ProfileConfig(days=1, interval_minutes=360), seed=42)
    original = pp.runpp
    calls: list[str | None] = []

    def counting_runpp(net, **kwargs):
        init = kwargs.get("init")
        calls.append(init)
        if len(calls) == 3:
            raise pp.LoadflowNotConverged("forced")
        return original(net, **kwargs)

    monkeypatch.setattr(simulation_module.pp, "runpp", counting_runpp)
    result = simulate_time_series(artifacts, profiles, ValidationConfig())
    assert len(result.failures) == 1
    assert calls == ["auto", "results", "results", "auto"]
