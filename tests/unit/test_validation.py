from ltverify.config import NetworkConfig, ValidationConfig
from ltverify.network import build_network
from ltverify.validation import run_static_validation


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
    artifacts.net.load["p_mw"] = 0.08 * 8
    result = run_static_validation(artifacts, ValidationConfig(voltage_min_pu=0.95))
    assert any(
        message.startswith(("voltage below", "transformer overload"))
        for message in result.violations
    )
