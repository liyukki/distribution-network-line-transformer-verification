"""Deterministic three-feeder network construction and topology export.

The default network contains one 110 kV external grid, one 110/10 kV main
transformer, one 10 kV bus, three 10 kV feeders and eight 10/0.4 kV
distribution transformers per feeder (plus one aggregated load per
transformer and zero-output PV sgen units at transformer positions 3 and 6
of each feeder).

Engineering parameters are named constants documented here for the README
(Task 14). The main-transformer ratings are sensible engineering values; the
design spec fixes only the voltage levels (110/10 kV) for the main unit.
"""

from dataclasses import dataclass

import numpy as np
import pandapower as pp
import pandas as pd
from pandapower.auxiliary import pandapowerNet

from ltverify.config import NetworkConfig

LINE_R_OHM_PER_KM = 0.32
LINE_X_OHM_PER_KM = 0.35
LINE_C_NF_PER_KM = 10.0
LINE_MAX_I_KA = 0.25
FEEDER_HEAD_LENGTH_KM = 0.5
SECTION_LENGTH_KM = 0.8
DISTRIBUTION_TRAFO_SN_MVA = 0.4
DISTRIBUTION_TRAFO_VK_PERCENT = 4.0
DISTRIBUTION_TRAFO_VKR_PERCENT = 1.2
MAIN_TRAFO_SN_MVA = 25.0
MAIN_TRAFO_VK_PERCENT = 10.5
MAIN_TRAFO_VKR_PERCENT = 0.4

_CUSTOMER_TYPES = ("residential", "commercial", "mixed")
_PV_POSITIONS = (3, 6)


@dataclass(frozen=True)
class NetworkArtifacts:
    net: pandapowerNet
    asset_table: pd.DataFrame
    feeder_head_lines: dict[str, int]
    feeder_head_buses: dict[str, int]


def build_network(cfg: NetworkConfig) -> NetworkArtifacts:
    """Build the deterministic multi-feeder network described in the plan."""
    net = pp.create_empty_network(f_hz=50.0)

    hv_bus = pp.create_bus(net, vn_kv=cfg.hv_kv, name="HV110")
    pp.create_ext_grid(net, hv_bus, vm_pu=1.0, name="external_grid")
    mv_main_bus = pp.create_bus(net, vn_kv=cfg.mv_kv, name="MV10_main")
    pp.create_transformer_from_parameters(
        net,
        hv_bus,
        mv_main_bus,
        sn_mva=MAIN_TRAFO_SN_MVA,
        vn_hv_kv=cfg.hv_kv,
        vn_lv_kv=cfg.mv_kv,
        vkr_percent=MAIN_TRAFO_VKR_PERCENT,
        vk_percent=MAIN_TRAFO_VK_PERCENT,
        pfe_kw=0.0,
        i0_percent=0.0,
        name="main_trafo",
    )

    rows: list[dict[str, object]] = []
    feeder_head_lines: dict[str, int] = {}
    feeder_head_buses: dict[str, int] = {}
    for feeder_number in range(cfg.feeder_count):
        feeder_id = f"F{feeder_number + 1:02d}"
        head_bus = pp.create_bus(net, vn_kv=cfg.mv_kv, name=f"{feeder_id}_head")
        head_line = pp.create_line_from_parameters(
            net,
            mv_main_bus,
            head_bus,
            length_km=FEEDER_HEAD_LENGTH_KM,
            r_ohm_per_km=LINE_R_OHM_PER_KM,
            x_ohm_per_km=LINE_X_OHM_PER_KM,
            c_nf_per_km=LINE_C_NF_PER_KM,
            max_i_ka=LINE_MAX_I_KA,
            name=f"{feeder_id}_head_line",
        )
        feeder_head_lines[feeder_id] = head_line
        feeder_head_buses[feeder_id] = head_bus
        prev_mv_bus = head_bus
        for position in range(1, cfg.transformers_per_feeder + 1):
            transformer_number = feeder_number * cfg.transformers_per_feeder + position
            transformer_id = f"T{transformer_number:03d}"
            mv_bus = pp.create_bus(
                net, vn_kv=cfg.mv_kv, name=f"{feeder_id}_s{position}_mv"
            )
            pp.create_line_from_parameters(
                net,
                prev_mv_bus,
                mv_bus,
                length_km=SECTION_LENGTH_KM,
                r_ohm_per_km=LINE_R_OHM_PER_KM,
                x_ohm_per_km=LINE_X_OHM_PER_KM,
                c_nf_per_km=LINE_C_NF_PER_KM,
                max_i_ka=LINE_MAX_I_KA,
                name=f"{feeder_id}_s{position}_line",
            )
            lv_bus = pp.create_bus(net, vn_kv=cfg.lv_kv, name=f"{transformer_id}_lv")
            trafo_index = pp.create_transformer_from_parameters(
                net,
                mv_bus,
                lv_bus,
                sn_mva=DISTRIBUTION_TRAFO_SN_MVA,
                vn_hv_kv=cfg.mv_kv,
                vn_lv_kv=cfg.lv_kv,
                vkr_percent=DISTRIBUTION_TRAFO_VKR_PERCENT,
                vk_percent=DISTRIBUTION_TRAFO_VK_PERCENT,
                pfe_kw=0.0,
                i0_percent=0.0,
                name=transformer_id,
            )
            load_index = pp.create_load(
                net, lv_bus, p_mw=0.0, q_mvar=0.0, name=f"{transformer_id}_load"
            )
            pv_index: int | None = None
            if position in _PV_POSITIONS:
                pv_index = pp.create_sgen(
                    net, lv_bus, p_mw=0.0, q_mvar=0.0, name=f"{transformer_id}_pv"
                )
            rows.append(
                {
                    "transformer_id": transformer_id,
                    "physical_feeder_id": feeder_id,
                    "customer_type": _CUSTOMER_TYPES[(position - 1) % 3],
                    "transformer_capacity_kva": DISTRIBUTION_TRAFO_SN_MVA * 1000.0,
                    "mv_bus": mv_bus,
                    "lv_bus": lv_bus,
                    "trafo_index": trafo_index,
                    "load_index": load_index,
                    "pv_index": pv_index if pv_index is not None else np.nan,
                }
            )
            prev_mv_bus = mv_bus

    asset_table = pd.DataFrame(rows)
    return NetworkArtifacts(
        net=net,
        asset_table=asset_table,
        feeder_head_lines=feeder_head_lines,
        feeder_head_buses=feeder_head_buses,
    )


def topology_frames(artifacts: NetworkArtifacts) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Export network topology as node and edge frames.

    Feeder membership is read from explicit element names and the asset table,
    never inferred from row order. The main transformer carries an empty
    feeder id.
    """
    net = artifacts.net
    nodes = pd.DataFrame(
        {
            "node_id": net.bus.index.to_list(),
            "node_type": ["bus"] * len(net.bus),
            "voltage_kv": net.bus.vn_kv.to_list(),
        }
    )
    line_edges = pd.DataFrame(
        {
            "from_node": net.line.from_bus.to_list(),
            "to_node": net.line.to_bus.to_list(),
            "edge_type": ["line"] * len(net.line),
            "feeder_id": [str(name).split("_")[0] for name in net.line["name"]],
        }
    )
    feeder_by_trafo = dict(
        zip(artifacts.asset_table["trafo_index"], artifacts.asset_table["physical_feeder_id"])
    )
    trafo_feeder_ids: list[str] = []
    for index, name in zip(net.trafo.index, net.trafo["name"]):
        if name == "main_trafo":
            trafo_feeder_ids.append("")
        else:
            trafo_feeder_ids.append(str(feeder_by_trafo.get(index, "")))
    trafo_edges = pd.DataFrame(
        {
            "from_node": net.trafo.hv_bus.to_list(),
            "to_node": net.trafo.lv_bus.to_list(),
            "edge_type": ["trafo"] * len(net.trafo),
            "feeder_id": trafo_feeder_ids,
        }
    )
    edges = pd.concat([line_edges, trafo_edges], ignore_index=True)
    return nodes, edges
