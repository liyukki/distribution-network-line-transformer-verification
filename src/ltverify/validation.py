"""Static power-flow validation for the verification network.

Checks convergence, voltage limits, power balance and transformer loading.
Violations are collected, never silently dropped.
"""

from dataclasses import dataclass

import pandapower as pp

from ltverify.config import ValidationConfig
from ltverify.network import NetworkArtifacts


@dataclass(frozen=True)
class PowerFlowValidation:
    converged: bool
    voltage_min_pu: float
    voltage_max_pu: float
    absolute_power_balance_error_mw: float
    violations: tuple[str, ...]


def run_static_validation(
    artifacts: NetworkArtifacts, cfg: ValidationConfig
) -> PowerFlowValidation:
    """Run one static power flow and report physical consistency.

    Power direction convention: supply (external grid plus sgen output)
    must equal demand plus line and transformer losses within 1e-6 MW.
    """
    net = artifacts.net
    violations: list[str] = []
    try:
        pp.runpp(net, calculate_voltage_angles=False, init="auto")
    except pp.LoadflowNotConverged:
        return PowerFlowValidation(
            converged=False,
            voltage_min_pu=float("nan"),
            voltage_max_pu=float("nan"),
            absolute_power_balance_error_mw=float("nan"),
            violations=("power flow did not converge",),
        )

    voltage_min_pu = float(net.res_bus.vm_pu.min())
    voltage_max_pu = float(net.res_bus.vm_pu.max())
    if voltage_min_pu < cfg.voltage_min_pu:
        violations.append(
            f"voltage below {cfg.voltage_min_pu} p.u.: "
            f"minimum {voltage_min_pu:.4f} p.u."
        )
    if voltage_max_pu > cfg.voltage_max_pu:
        violations.append(
            f"voltage above {cfg.voltage_max_pu} p.u.: "
            f"maximum {voltage_max_pu:.4f} p.u."
        )

    supply = net.res_ext_grid.p_mw.sum() + net.res_sgen.p_mw.sum()
    demand_and_losses = (
        net.res_load.p_mw.sum()
        + net.res_line.pl_mw.sum()
        + net.res_trafo.pl_mw.sum()
    )
    balance_error = abs(float(supply - demand_and_losses))
    if balance_error >= 1e-6:
        violations.append(
            f"power balance error {balance_error:.3e} MW at or above 1e-6 MW"
        )

    overloaded = net.res_trafo[net.res_trafo.loading_percent > 100.0]
    for index, loading in zip(overloaded.index, overloaded.loading_percent):
        violations.append(f"transformer overload: trafo {int(index)} at {loading:.1f}%")

    return PowerFlowValidation(
        converged=True,
        voltage_min_pu=voltage_min_pu,
        voltage_max_pu=voltage_max_pu,
        absolute_power_balance_error_mw=balance_error,
        violations=tuple(violations),
    )
