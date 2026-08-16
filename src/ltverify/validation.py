"""Power-flow validation for the verification network.

One reusable solver-agnostic checker inspects an already-solved network
result frame; the static runner solves one base case and the time-series
simulator reuses the same checker for every timestamp so both paths share
exactly one set of physical rules. Violations are collected, never
silently dropped.
"""

from dataclasses import dataclass

import pandapower as pp

from ltverify.config import ValidationConfig
from ltverify.network import NetworkArtifacts

_CRITICAL_VIOLATION_TYPES = ("non_convergence", "power_balance")


@dataclass(frozen=True)
class PowerFlowValidation:
    converged: bool
    voltage_min_pu: float
    voltage_max_pu: float
    absolute_power_balance_error_mw: float
    violations: tuple[str, ...]
    severity: str = "ok"
    violation_types: tuple[str, ...] = ()


@dataclass(frozen=True)
class NetworkResultCheck:
    converged: bool
    voltage_min_pu: float
    voltage_max_pu: float
    maximum_transformer_loading_percent: float
    absolute_power_balance_error_mw: float
    violation_types: tuple[str, ...]
    messages: tuple[str, ...]
    severity: str


def check_solved_network(
    net: object, cfg: ValidationConfig
) -> NetworkResultCheck:
    """Inspect an already-solved network result frame.

    Power direction convention: supply (external grid plus sgen output)
    must equal demand plus line and transformer losses within the
    configured tolerance. severity is the highest of the recorded
    violations; a clean network reports "ok".
    """
    if "res_bus" not in net or len(net.res_bus) == 0:
        return NetworkResultCheck(
            converged=False,
            voltage_min_pu=float("nan"),
            voltage_max_pu=float("nan"),
            maximum_transformer_loading_percent=float("nan"),
            absolute_power_balance_error_mw=float("nan"),
            violation_types=("non_convergence",),
            messages=("power flow did not converge",),
            severity="critical",
        )

    voltage_min_pu = float(net.res_bus.vm_pu.min())
    voltage_max_pu = float(net.res_bus.vm_pu.max())
    maximum_loading = float(net.res_trafo.loading_percent.max())
    supply = net.res_ext_grid.p_mw.sum() + net.res_sgen.p_mw.sum()
    demand_and_losses = (
        net.res_load.p_mw.sum()
        + net.res_line.pl_mw.sum()
        + net.res_trafo.pl_mw.sum()
    )
    balance_error = abs(float(supply - demand_and_losses))

    violation_types: list[str] = []
    messages: list[str] = []
    severities: list[str] = []

    def record(violation_type: str, message: str) -> None:
        violation_types.append(violation_type)
        messages.append(message)
        severities.append(
            "critical"
            if violation_type in cfg.critical_violation_types
            else "warning"
        )

    if voltage_min_pu < cfg.voltage_min_pu:
        record(
            "voltage_out_of_bounds",
            f"voltage below {cfg.voltage_min_pu} p.u.: "
            f"minimum {voltage_min_pu:.4f} p.u.",
        )
    if voltage_max_pu > cfg.voltage_max_pu:
        record(
            "voltage_out_of_bounds",
            f"voltage above {cfg.voltage_max_pu} p.u.: "
            f"maximum {voltage_max_pu:.4f} p.u.",
        )
    if balance_error >= cfg.power_balance_tolerance_mw:
        record(
            "power_balance",
            f"power balance error {balance_error:.3e} MW at or above "
            f"{cfg.power_balance_tolerance_mw:g} MW",
        )
    overloaded = net.res_trafo[
        net.res_trafo.loading_percent > cfg.transformer_loading_limit_percent
    ]
    for index, loading in zip(overloaded.index, overloaded.loading_percent):
        record(
            "transformer_overload",
            f"transformer overload: trafo {int(index)} at {loading:.1f}%",
        )

    if "critical" in severities:
        severity = "critical"
    elif severities:
        severity = "warning"
    else:
        severity = "ok"

    deduplicated_types = tuple(dict.fromkeys(violation_types))
    return NetworkResultCheck(
        converged=True,
        voltage_min_pu=voltage_min_pu,
        voltage_max_pu=voltage_max_pu,
        maximum_transformer_loading_percent=maximum_loading,
        absolute_power_balance_error_mw=balance_error,
        violation_types=deduplicated_types,
        messages=tuple(messages),
        severity=severity,
    )


def run_static_validation(
    artifacts: NetworkArtifacts, cfg: ValidationConfig
) -> PowerFlowValidation:
    """Solve one base-case power flow and report physical consistency.

    This is a topology/base-case check on the zero-load network; it is not
    a substitute for the per-timestep checks performed by the simulator.
    """
    net = artifacts.net
    try:
        pp.runpp(net, calculate_voltage_angles=False, init="auto")
    except pp.LoadflowNotConverged:
        return PowerFlowValidation(
            converged=False,
            voltage_min_pu=float("nan"),
            voltage_max_pu=float("nan"),
            absolute_power_balance_error_mw=float("nan"),
            violations=("power flow did not converge",),
            severity="critical",
            violation_types=("non_convergence",),
        )
    check = check_solved_network(net, cfg)
    return PowerFlowValidation(
        converged=check.converged,
        voltage_min_pu=check.voltage_min_pu,
        voltage_max_pu=check.voltage_max_pu,
        absolute_power_balance_error_mw=check.absolute_power_balance_error_mw,
        violations=check.messages,
        severity=check.severity,
        violation_types=check.violation_types,
    )
