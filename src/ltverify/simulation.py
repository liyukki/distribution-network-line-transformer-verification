"""Time-series power-flow simulation exporting clean measurements.

For every timestamp the load and PV profiles are written into the network,
one power flow is solved and per-transformer and per-feeder measurements are
exported. Non-convergence is collected into the failures frame and never
silently dropped; the pipeline decides whether to stop on failures.
"""

from dataclasses import dataclass

import pandapower as pp
import pandas as pd

from ltverify.config import ValidationConfig
from ltverify.network import NetworkArtifacts
from ltverify.profiles import TimeSeriesProfiles


@dataclass(frozen=True)
class SimulationResult:
    transformer_measurements: pd.DataFrame
    feeder_measurements: pd.DataFrame
    failures: pd.DataFrame


def simulate_time_series(
    artifacts: NetworkArtifacts,
    profiles: TimeSeriesProfiles,
    validation_cfg: ValidationConfig,
) -> SimulationResult:
    """Simulate all timestamps and export clean long-form measurements.

    Transformer P/Q use the HV-side transformer results with the convention
    that positive means the transformer consumes power; feeder P/Q are the
    head-line from-side flows, positive when the feeder imports from the
    main bus. validation_cfg is accepted for interface compatibility with
    the pipeline and is not applied here; the pipeline validates afterwards.
    """
    net = artifacts.net
    asset_table = artifacts.asset_table
    transformer_ids = asset_table["transformer_id"].tolist()
    load_indices = asset_table["load_index"].astype(int).tolist()
    lv_buses = asset_table["lv_bus"].astype(int).tolist()
    trafo_indices = asset_table["trafo_index"].astype(int).tolist()
    pv_rows = asset_table[asset_table["pv_index"].notna()]
    pv_columns = pv_rows["transformer_id"].tolist()
    pv_indices = pv_rows["pv_index"].astype(int).tolist()

    feeder_ids = list(artifacts.feeder_head_buses.keys())
    head_buses = [artifacts.feeder_head_buses[f] for f in feeder_ids]
    head_lines = [artifacts.feeder_head_lines[f] for f in feeder_ids]

    transformer_rows: list[dict[str, object]] = []
    feeder_rows: list[dict[str, object]] = []
    failure_rows: list[dict[str, object]] = []

    for step, timestamp in enumerate(profiles.index):
        net.load.loc[load_indices, "p_mw"] = profiles.load_p_mw.iloc[step].to_numpy()
        net.load.loc[load_indices, "q_mvar"] = profiles.load_q_mvar.iloc[step].to_numpy()
        net.sgen.loc[pv_indices, "p_mw"] = (
            profiles.pv_p_mw.iloc[step][pv_columns].to_numpy()
        )
        init_mode = "auto" if step == 0 else "results"
        try:
            pp.runpp(net, calculate_voltage_angles=False, init=init_mode)
        except pp.LoadflowNotConverged as exc:
            failure_rows.append(
                {
                    "timestamp": timestamp,
                    "error_type": "non_convergence",
                    "message": f"load flow did not converge: {exc}",
                }
            )
            continue

        for transformer_id, lv_bus, trafo_index in zip(
            transformer_ids, lv_buses, trafo_indices
        ):
            transformer_rows.append(
                {
                    "timestamp": timestamp,
                    "transformer_id": transformer_id,
                    "voltage_pu": float(net.res_bus.vm_pu.loc[lv_bus]),
                    "p_mw": float(net.res_trafo.p_hv_mw.loc[trafo_index]),
                    "q_mvar": float(net.res_trafo.q_hv_mvar.loc[trafo_index]),
                    "data_quality_flag": "clean",
                }
            )
        for feeder_id, head_bus, head_line in zip(feeder_ids, head_buses, head_lines):
            feeder_rows.append(
                {
                    "timestamp": timestamp,
                    "feeder_id": feeder_id,
                    "head_voltage_pu": float(net.res_bus.vm_pu.loc[head_bus]),
                    "p_mw": float(net.res_line.p_from_mw.loc[head_line]),
                    "q_mvar": float(net.res_line.q_from_mvar.loc[head_line]),
                }
            )

    return SimulationResult(
        transformer_measurements=pd.DataFrame(transformer_rows),
        feeder_measurements=pd.DataFrame(feeder_rows),
        failures=pd.DataFrame(failure_rows),
    )
