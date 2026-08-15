"""Reusable Plotly figures for the verification dashboard."""

import numpy as np
import pandas as pd
import plotly.graph_objects as go

FEEDER_COLORS = {"F01": "#1f77b4", "F02": "#ff7f0e", "F03": "#2ca02c"}


def confusion_matrix_figure(matrix: np.ndarray) -> go.Figure:
    """Heatmap with Chinese axes; values are sample counts, never Accuracy."""
    figure = go.Figure(
        go.Heatmap(
            z=matrix,
            x=["未误判", "误判"],
            y=["未误判", "误判"],
            colorscale="Blues",
            colorbar={"title": "数量"},
            text=matrix,
            texttemplate="%{text}",
        )
    )
    figure.update_layout(
        title="混淆矩阵",
        xaxis={"title": "预测标签"},
        yaxis={"title": "真实标签"},
    )
    return figure


def voltage_curves_figure(
    voltage_wide: pd.DataFrame, transformer_ids: list[str]
) -> go.Figure:
    """Overlaid per-transformer voltage curves on a shared time axis."""
    figure = go.Figure()
    for transformer_id in transformer_ids:
        series = voltage_wide[transformer_id]
        figure.add_trace(
            go.Scatter(
                x=voltage_wide.index,
                y=series,
                mode="lines",
                name=transformer_id,
                hovertemplate=f"{transformer_id}<br>%{{x}}<br>%{{y:.4f}} p.u.",
            )
        )
    figure.update_layout(
        title="配变电压曲线（标幺值）",
        xaxis={"title": "时间"},
        yaxis={"title": "电压 (p.u.)"},
    )
    return figure


def candidate_score_bars_figure(
    scores: pd.DataFrame, transformer_id: str
) -> go.Figure:
    """Bar chart of candidate feeder scores for one transformer."""
    figure = go.Figure(
        go.Bar(
            x=scores["candidate_feeder_id"],
            y=scores["enhanced_score"],
            marker={"color": [
                FEEDER_COLORS.get(str(feeder), "#999999")
                for feeder in scores["candidate_feeder_id"]
            ]},
        )
    )
    figure.update_layout(
        title=f"{transformer_id} 候选馈线评分",
        xaxis={"title": "候选馈线"},
        yaxis={"title": "增强评分", "range": [0, 1]},
    )
    return figure


def similarity_heatmap_figure(matrix: pd.DataFrame) -> go.Figure:
    """Transformer similarity matrix heatmap."""
    figure = go.Figure(
        go.Heatmap(
            z=matrix.to_numpy(),
            x=matrix.columns.tolist(),
            y=matrix.index.tolist(),
            colorscale="RdBu_r",
            zmid=0,
            colorbar={"title": "相关系数"},
        )
    )
    figure.update_layout(title="配变相似度矩阵")
    return figure


def topology_figure(nodes: pd.DataFrame, edges: pd.DataFrame) -> go.Figure:
    """Schematic topology on a circle layout, colored by voltage level."""
    figure = go.Figure()
    count = len(nodes)
    angles = 2 * np.pi * nodes["node_id"].to_numpy() / max(count, 1)
    radius_by_kv = {110.0: 0.4, 10.0: 0.7, 0.4: 1.0}
    x = np.cos(angles) * nodes["voltage_kv"].map(radius_by_kv)
    y = np.sin(angles) * nodes["voltage_kv"].map(radius_by_kv)
    positions = dict(zip(nodes["node_id"], zip(x, y)))
    for _, edge in edges.iterrows():
        start = positions[edge["from_node"]]
        end = positions[edge["to_node"]]
        color = FEEDER_COLORS.get(str(edge["feeder_id"]), "#aaaaaa")
        figure.add_trace(
            go.Scatter(
                x=[start[0], end[0]],
                y=[start[1], end[1]],
                mode="lines",
                line={"color": color, "width": 1.5},
                hoverinfo="skip",
                showlegend=False,
            )
        )
    figure.add_trace(
        go.Scatter(
            x=x,
            y=y,
            mode="markers+text",
            text=nodes["node_id"],
            textposition="top center",
            marker={
                "size": 10,
                "color": nodes["voltage_kv"],
                "colorscale": "Viridis",
                "colorbar": {"title": "电压等级 (kV)"},
            },
            name="母线",
        )
    )
    figure.update_layout(title="网络拓扑", showlegend=False)
    return figure


def pr_curve_figure(precision: list[float], recall: list[float]) -> go.Figure:
    """Precision-recall curve; the headline is P/R, never Accuracy."""
    figure = go.Figure(
        go.Scatter(
            x=recall,
            y=precision,
            mode="lines+markers",
            name="PR 曲线",
        )
    )
    figure.update_layout(
        title="PR 曲线",
        xaxis={"title": "Recall"},
        yaxis={"title": "Precision", "range": [0, 1]},
    )
    return figure


def robustness_line_figure(
    summary: pd.DataFrame, family: str, metric: str
) -> go.Figure:
    """Mean plus/minus one sample standard deviation across experiment levels."""
    rows = summary[summary["family"] == family]
    values = rows["value"].astype(str)
    means = rows[f"mean_{metric}"].to_numpy(dtype=float)
    stds = rows[f"std_{metric}"].to_numpy(dtype=float)
    figure = go.Figure(
        go.Scatter(
            x=values,
            y=means,
            mode="lines+markers",
            name=metric,
            error_y={"type": "data", "array": stds, "visible": True},
        )
    )
    figure.update_layout(
        title=f"{family} — {metric}（均值 ± 样本标准差）",
        xaxis={"title": family},
        yaxis={"title": metric},
    )
    return figure
