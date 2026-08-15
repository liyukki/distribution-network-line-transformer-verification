from ltverify.config import NetworkConfig
from ltverify.network import build_network, topology_frames


def test_default_network_contains_three_feeders_and_twenty_four_assets() -> None:
    artifacts = build_network(NetworkConfig())
    assert len(artifacts.asset_table) == 24
    assert artifacts.asset_table["physical_feeder_id"].nunique() == 3
    assert len(artifacts.net.load) == 24
    assert len(artifacts.net.trafo) == 25
    assert len(artifacts.feeder_head_lines) == 3
    assert artifacts.asset_table["transformer_id"].is_unique


def test_topology_export_has_valid_endpoints() -> None:
    artifacts = build_network(NetworkConfig())
    nodes, edges = topology_frames(artifacts)
    assert {"node_id", "node_type", "voltage_kv"} <= set(nodes.columns)
    assert {"from_node", "to_node", "edge_type", "feeder_id"} <= set(edges.columns)
    assert set(edges["from_node"]) <= set(nodes["node_id"])
    assert set(edges["to_node"]) <= set(nodes["node_id"])
