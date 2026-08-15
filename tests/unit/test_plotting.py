import numpy as np
import pandas as pd
import pytest

from ltverify.plotting import (
    candidate_score_bars_figure,
    confusion_matrix_figure,
    pr_curve_figure,
    robustness_line_figure,
    similarity_heatmap_figure,
    topology_figure,
    voltage_curves_figure,
)


def test_confusion_matrix_figure_has_chinese_axes() -> None:
    figure = confusion_matrix_figure(np.array([[8, 1], [2, 5]]))
    assert figure.layout.xaxis.title.text == "预测标签"
    assert figure.layout.yaxis.title.text == "真实标签"
    assert len(figure.data) == 1


def test_voltage_curves_figure() -> None:
    index = pd.date_range("2026-01-01", periods=12, freq="15min")
    wide = pd.DataFrame({"T001": [1.0] * 12, "T002": [0.99] * 12}, index=index)
    figure = voltage_curves_figure(wide, ["T001", "T002"])
    assert len(figure.data) == 2
    assert "p.u." in figure.layout.yaxis.title.text


def test_candidate_score_bars_figure() -> None:
    scores = pd.DataFrame(
        {
            "candidate_feeder_id": ["F01", "F02", "F03"],
            "enhanced_score": [0.9, 0.4, 0.3],
        }
    )
    figure = candidate_score_bars_figure(scores, "T001")
    assert len(figure.data) == 1
    assert "T001" in figure.layout.title.text


def test_similarity_heatmap_figure() -> None:
    matrix = pd.DataFrame(
        [[1.0, 0.8], [0.8, 1.0]], index=["T001", "T002"], columns=["T001", "T002"]
    )
    figure = similarity_heatmap_figure(matrix)
    assert len(figure.data) == 1
    assert "相似度" in figure.layout.title.text


def test_topology_figure() -> None:
    nodes = pd.DataFrame(
        {"node_id": [0, 1], "node_type": ["bus", "bus"], "voltage_kv": [10.0, 0.4]}
    )
    edges = pd.DataFrame(
        {
            "from_node": [0],
            "to_node": [1],
            "edge_type": ["trafo"],
            "feeder_id": ["F01"],
        }
    )
    figure = topology_figure(nodes, edges)
    assert len(figure.data) >= 2
    assert "拓扑" in figure.layout.title.text


def test_pr_curve_figure() -> None:
    figure = pr_curve_figure([1.0, 0.8, 0.5], [0.2, 0.6, 1.0])
    assert len(figure.data) == 1
    assert "PR" in figure.layout.title.text


def test_robustness_line_figure() -> None:
    summary = pd.DataFrame(
        {
            "family": ["missing_rate", "missing_rate"],
            "value": ["0.0", "0.1"],
            "mean_f1": [0.9, 0.8],
            "std_f1": [0.05, 0.06],
        }
    )
    figure = robustness_line_figure(summary, "missing_rate", "f1")
    assert len(figure.data) >= 1
    assert "missing_rate" in figure.layout.title.text


def test_robustness_line_figure_validates_aggregate_columns() -> None:
    summary = pd.DataFrame(
        {"family": ["missing_rate"], "value": ["0.0"], "f1": [0.9]}
    )
    with pytest.raises(ValueError, match="mean_f1"):
        robustness_line_figure(summary, "missing_rate", "f1")
