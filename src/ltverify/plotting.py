"""Reusable Plotly figures for the verification dashboard."""

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.colors import qualitative

from ltverify.i18n import (
    DEFAULT_LOCALE,
    Locale,
    family_label,
    metric_label,
    translate,
)

FEEDER_COLORS = {"F01": "#1f77b4", "F02": "#ff7f0e", "F03": "#2ca02c"}
_NEUTRAL_COLOR = "#cccccc"


def feeder_color(feeder_id: object, neutral: bool = False) -> str:
    """Deterministic color per feeder id; supports more than three feeders.

    In neutral mode every feeder gets the same gray so that the physical
    topology stays hidden outside demo/evaluation mode.
    """
    if neutral:
        return _NEUTRAL_COLOR
    key = str(feeder_id)
    if key in FEEDER_COLORS:
        return FEEDER_COLORS[key]
    palette = qualitative.Plotly
    digits = [character for character in key if character.isdigit()]
    index = (int("".join(digits)) - 1) % len(palette) if digits else hash(key) % len(palette)
    return palette[index]


def confusion_matrix_figure(
    matrix: np.ndarray, *, locale: Locale | str = DEFAULT_LOCALE
) -> go.Figure:
    """Localized heatmap whose values are sample counts, never Accuracy."""
    figure = go.Figure(
        go.Heatmap(
            z=matrix,
            x=[
                translate(locale, "plot.confusion.negative"),
                translate(locale, "plot.confusion.positive"),
            ],
            y=[
                translate(locale, "plot.confusion.negative"),
                translate(locale, "plot.confusion.positive"),
            ],
            colorscale="Blues",
            colorbar={"title": translate(locale, "plot.count")},
            text=matrix,
            texttemplate="%{text}",
        )
    )
    figure.update_layout(
        title=translate(locale, "plot.confusion.title"),
        xaxis={"title": translate(locale, "plot.confusion.predicted")},
        yaxis={"title": translate(locale, "plot.confusion.actual")},
    )
    return figure


def voltage_curves_figure(
    voltage_wide: pd.DataFrame,
    transformer_ids: list[str],
    *,
    locale: Locale | str = DEFAULT_LOCALE,
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
        title=translate(locale, "plot.voltage.title"),
        xaxis={"title": translate(locale, "plot.time")},
        yaxis={"title": translate(locale, "plot.voltage")},
    )
    return figure


def candidate_score_bars_figure(
    scores: pd.DataFrame,
    transformer_id: str,
    *,
    locale: Locale | str = DEFAULT_LOCALE,
) -> go.Figure:
    """Bar chart of candidate feeder scores for one transformer."""
    figure = go.Figure(
        go.Bar(
            x=scores["candidate_feeder_id"],
            y=scores["enhanced_score"],
            marker={"color": [feeder_color(feeder) for feeder in scores["candidate_feeder_id"]]},
        )
    )
    figure.update_layout(
        title=translate(locale, "plot.candidate.title", transformer_id=transformer_id),
        xaxis={"title": translate(locale, "plot.candidate.feeder")},
        yaxis={"title": translate(locale, "plot.candidate.score"), "range": [0, 1]},
    )
    return figure


def similarity_heatmap_figure(
    matrix: pd.DataFrame, *, locale: Locale | str = DEFAULT_LOCALE
) -> go.Figure:
    """Transformer similarity matrix heatmap."""
    figure = go.Figure(
        go.Heatmap(
            z=matrix.to_numpy(),
            x=matrix.columns.tolist(),
            y=matrix.index.tolist(),
            colorscale="RdBu_r",
            zmid=0,
            colorbar={"title": translate(locale, "plot.correlation")},
        )
    )
    figure.update_layout(title=translate(locale, "plot.similarity.title"))
    return figure


def topology_figure(
    nodes: pd.DataFrame,
    edges: pd.DataFrame,
    color_edges_by_feeder: bool = True,
    *,
    locale: Locale | str = DEFAULT_LOCALE,
) -> go.Figure:
    """Schematic topology on a circle layout, colored by voltage level.

    Edge feeder colors reveal the physical topology, so they are only
    shown in demo/evaluation mode (color_edges_by_feeder=True); otherwise
    every edge is neutral gray.
    """
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
        color = feeder_color(edge["feeder_id"], neutral=not color_edges_by_feeder)
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
                "colorbar": {"title": translate(locale, "plot.voltage_level")},
            },
            name=translate(locale, "plot.bus"),
        )
    )
    figure.update_layout(title=translate(locale, "plot.topology.title"), showlegend=False)
    return figure


def pr_curve_figure(
    precision: list[float],
    recall: list[float],
    *,
    locale: Locale | str = DEFAULT_LOCALE,
) -> go.Figure:
    """Precision-recall curve; the headline is P/R, never Accuracy."""
    figure = go.Figure(
        go.Scatter(
            x=recall,
            y=precision,
            mode="lines+markers",
            name=translate(locale, "plot.pr.legend"),
        )
    )
    figure.update_layout(
        title=translate(locale, "plot.pr.title"),
        xaxis={"title": translate(locale, "plot.recall")},
        yaxis={"title": translate(locale, "plot.precision"), "range": [0, 1]},
    )
    return figure


def robustness_line_figure(
    summary: pd.DataFrame,
    family: str,
    metric: str,
    *,
    locale: Locale | str = DEFAULT_LOCALE,
) -> go.Figure:
    """Mean plus/minus one sample standard deviation across experiment levels.

    Requires the aggregate product (robustness_aggregates.csv; legacy
    experiment_aggregates.csv is also accepted by callers); the raw
    robustness_summary.csv lacks the mean_*/std_* columns and is rejected
    with an explicit error. Numeric level values are ordered numerically.
    """
    required = {"family", "value", f"mean_{metric}", f"std_{metric}"}
    missing = sorted(required - set(summary.columns))
    if missing:
        raise ValueError(translate(locale, "plot.aggregate_missing", missing=missing))
    rows = summary[summary["family"] == family]
    numeric = pd.to_numeric(rows["value"].astype(str), errors="coerce")
    if numeric.notna().all():
        rows = rows.loc[numeric.sort_values().index]
    values = rows["value"].astype(str)
    means = rows[f"mean_{metric}"].to_numpy(dtype=float)
    stds = rows[f"std_{metric}"].to_numpy(dtype=float)
    localized_family = family_label(locale, family)
    localized_metric = metric_label(locale, metric)
    figure = go.Figure(
        go.Scatter(
            x=values,
            y=means,
            mode="lines+markers",
            name=localized_metric,
            error_y={"type": "data", "array": stds, "visible": True},
        )
    )
    figure.update_layout(
        title=translate(
            locale,
            "plot.robustness.title",
            family=localized_family,
            metric=localized_metric,
        ),
        xaxis={"title": localized_family},
        yaxis={"title": localized_metric},
    )
    return figure
