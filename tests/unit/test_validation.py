import math

import pandapower as pp
import pytest

from ltverify.config import NetworkConfig, ValidationConfig
from ltverify.network import build_network
from ltverify.validation import run_static_validation

_OVERLOAD_LOAD_MW = 0.08 * 8  # 0.64 MW per transformer, about 160% of 0.4 MVA rating


def test_static_case_converges_and_balances_power() -> None:
    artifacts = build_network(NetworkConfig())
    result = run_static_validation(artifacts, ValidationConfig())
    assert result.converged is True
    assert result.voltage_min_pu >= 0.90
    assert result.voltage_max_pu <= 1.10
    assert result.absolute_power_balance_error_mw < 1e-6
    assert result.violations == ()


def test_intentional_overload_is_detected() -> None:
    artifacts = build_network(NetworkConfig())
    artifacts.net.load["p_mw"] = _OVERLOAD_LOAD_MW
    result = run_static_validation(artifacts, ValidationConfig(voltage_min_pu=0.95))
    assert any(
        message.startswith(("voltage below", "transformer overload"))
        for message in result.violations
    )


def test_non_convergence_is_reported_not_silent(monkeypatch: pytest.MonkeyPatch) -> None:
    artifacts = build_network(NetworkConfig())

    def raise_not_converged(*args: object, **kwargs: object) -> None:
        raise pp.LoadflowNotConverged("forced failure")

    monkeypatch.setattr("pandapower.runpp", raise_not_converged)
    result = run_static_validation(artifacts, ValidationConfig())
    assert result.converged is False
    assert math.isnan(result.voltage_min_pu)
    assert math.isnan(result.voltage_max_pu)
    assert math.isnan(result.absolute_power_balance_error_mw)
    assert result.violations == ("power flow did not converge",)
