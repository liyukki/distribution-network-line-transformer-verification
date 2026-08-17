"""Generate publication figures strictly from committed public evidence."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib import font_manager
from matplotlib.patches import FancyBboxPatch

ROOT = Path(__file__).resolve().parents[1]
FIGURE_NAMES = (
    "system-workflow.png",
    "baseline-comparison.png",
    "confusion-matrix.png",
    "robustness-ablation.png",
)


def _configure_fonts() -> None:
    candidates = (
        Path("C:/Windows/Fonts/msyh.ttc"),
        Path("C:/Windows/Fonts/simhei.ttf"),
    )
    for path in candidates:
        if path.is_file():
            font_manager.fontManager.addfont(path)
            name = font_manager.FontProperties(fname=path).get_name()
            plt.rcParams["font.sans-serif"] = [name, "DejaVu Sans"]
            break
    plt.rcParams["axes.unicode_minus"] = False


def load_figure_data(source_root: Path = ROOT) -> dict[str, Any]:
    """Load every plotted value from the public evidence package."""
    summary = json.loads(
        (source_root / "reports/metrics/default_summary.json").read_text(encoding="utf-8")
    )
    confusion = pd.read_csv(
        source_root / "reports/evidence/default_run/confusion_matrix.csv", index_col=0
    )
    robustness = pd.read_csv(source_root / "reports/metrics/robustness_aggregates.csv")
    metrics = summary["metrics"]
    return {
        "enhanced": {
            "precision": float(metrics["precision"]),
            "recall": float(metrics["recall"]),
            "f1": float(metrics["f1"]),
            "pr_auc": float(metrics["pr_auc"]),
        },
        "baseline": {
            key: float(summary["baseline_comparison"][key])
            for key in ("precision", "recall", "f1", "pr_auc")
        },
        "confusion_matrix": confusion.to_numpy(dtype=int).tolist(),
        "missing_rate": robustness.loc[
            robustness["family"] == "missing_rate",
            ["value", "mean_f1", "std_f1", "mean_pr_auc", "std_pr_auc"],
        ].copy(),
        "ablation": robustness.loc[
            robustness["family"] == "ablation",
            ["value", "mean_f1", "std_f1"],
        ].copy(),
    }


def _save(figure: plt.Figure, path: Path) -> None:
    figure.savefig(
        path,
        dpi=180,
        bbox_inches="tight",
        facecolor="white",
        metadata={"Software": "ltverify publication figure generator"},
    )
    plt.close(figure)


def _workflow_figure(path: Path) -> None:
    figure, axis = plt.subplots(figsize=(11.2, 4.8))
    axis.set_xlim(0, 1)
    axis.set_ylim(0, 1)
    axis.axis("off")
    labels = (
        (0.02, "合成配电网\n时序潮流"),
        (0.21, "台账错误与\n量测扰动"),
        (0.40, "预处理与\n多源特征"),
        (0.59, "融合评分与\n保守门禁"),
        (0.78, "评价、看板\n与报告"),
    )
    colors = ("#DCEEFF", "#FDE8D8", "#E3F4E7", "#EEE5FA", "#FFF2CC")
    for index, ((x, label), color) in enumerate(zip(labels, colors, strict=True)):
        box = FancyBboxPatch(
            (x, 0.48),
            0.16,
            0.22,
            boxstyle="round,pad=0.02,rounding_size=0.02",
            linewidth=1.5,
            edgecolor="#334155",
            facecolor=color,
        )
        axis.add_patch(box)
        axis.text(x + 0.08, 0.59, label, ha="center", va="center", fontsize=12)
        if index < len(labels) - 1:
            axis.annotate(
                "",
                xy=(x + 0.19, 0.59),
                xytext=(x + 0.16, 0.59),
                arrowprops={"arrowstyle": "->", "lw": 1.7, "color": "#334155"},
            )
    axis.text(
        0.5,
        0.25,
        "配置快照 + manifest + SHA-256 + 公开证据包 + 自动化测试",
        ha="center",
        va="center",
        fontsize=12,
        color="#0F4C5C",
        bbox={"boxstyle": "round,pad=0.45", "fc": "#E6F4F1", "ec": "#0F766E"},
    )
    axis.annotate(
        "可追溯证据链",
        xy=(0.83, 0.46),
        xytext=(0.69, 0.29),
        fontsize=10,
        arrowprops={"arrowstyle": "->", "color": "#0F766E"},
    )
    axis.set_title("线变关系智能校验系统与证据链", fontsize=17, pad=14, weight="bold")
    axis.text(
        0.5,
        0.04,
        "来源：项目软件架构与公开运行证据；图中各阶段均可由仓库命令复现。",
        ha="center",
        fontsize=9,
        color="#475569",
    )
    _save(figure, path)


def _baseline_figure(path: Path, data: dict[str, Any]) -> None:
    labels = ["Precision", "Recall", "F1", "PR-AUC"]
    keys = ["precision", "recall", "f1", "pr_auc"]
    baseline = [data["baseline"][key] for key in keys]
    enhanced = [data["enhanced"][key] for key in keys]
    x = np.arange(len(labels))
    width = 0.34
    figure, axis = plt.subplots(figsize=(9.2, 5.6))
    bars_a = axis.bar(x - width / 2, baseline, width, label="原始 Pearson 基线", color="#94A3B8")
    bars_b = axis.bar(x + width / 2, enhanced, width, label="增强融合方法", color="#2563EB")
    axis.bar_label(bars_a, fmt="%.3f", padding=3, fontsize=9)
    axis.bar_label(bars_b, fmt="%.3f", padding=3, fontsize=9)
    axis.set_xticks(x, labels)
    axis.set_ylim(0, max(max(enhanced), max(baseline), 0.4) + 0.10)
    axis.set_ylabel("指标值")
    axis.set_title("默认 30 天合成场景：基线与增强方法对比", weight="bold")
    axis.grid(axis="y", alpha=0.25)
    axis.legend(frameon=False)
    figure.text(
        0.5,
        0.01,
        "来源：reports/metrics/default_summary.json；24 台配变，其中 5 个台账错误。",
        ha="center",
        fontsize=9,
        color="#475569",
    )
    figure.tight_layout(rect=(0, 0.04, 1, 1))
    _save(figure, path)


def _confusion_figure(path: Path, data: dict[str, Any]) -> None:
    matrix = np.asarray(data["confusion_matrix"], dtype=int)
    figure, axis = plt.subplots(figsize=(6.7, 5.8))
    image = axis.imshow(matrix, cmap="Blues", vmin=0)
    for row in range(matrix.shape[0]):
        for column in range(matrix.shape[1]):
            color = "white" if matrix[row, column] > matrix.max() / 2 else "#0F172A"
            axis.text(
                column,
                row,
                str(matrix[row, column]),
                ha="center",
                va="center",
                fontsize=18,
                color=color,
            )
    axis.set_xticks([0, 1], ["未告警", "告警"])
    axis.set_yticks([0, 1], ["台账正确", "台账错误"])
    axis.set_xlabel("预测标签")
    axis.set_ylabel("真实标签")
    axis.set_title("默认运行混淆矩阵", weight="bold")
    figure.colorbar(image, ax=axis, label="配变数量", shrink=0.82)
    figure.text(
        0.5,
        0.015,
        "来源：reports/evidence/default_run/confusion_matrix.csv；矩阵不等同于 Accuracy。",
        ha="center",
        fontsize=9,
        color="#475569",
    )
    figure.tight_layout(rect=(0, 0.05, 1, 1))
    _save(figure, path)


def _robustness_figure(path: Path, data: dict[str, Any]) -> None:
    missing = data["missing_rate"].copy()
    missing["value"] = pd.to_numeric(missing["value"])
    missing = missing.sort_values("value")
    ablation = data["ablation"].copy()
    labels = {
        "full": "完整特征",
        "without_difference": "移除差分",
        "without_events": "移除事件",
        "without_power": "移除有功",
        "without_residual": "移除残差",
        "without_rolling": "移除滚动",
    }
    ablation["label"] = ablation["value"].map(labels)
    figure, axes = plt.subplots(1, 2, figsize=(12, 5.6))
    axes[0].errorbar(
        missing["value"] * 100,
        missing["mean_f1"],
        yerr=missing["std_f1"],
        marker="o",
        capsize=4,
        label="F1",
        color="#2563EB",
    )
    axes[0].errorbar(
        missing["value"] * 100,
        missing["mean_pr_auc"],
        yerr=missing["std_pr_auc"],
        marker="s",
        capsize=4,
        label="PR-AUC",
        color="#D97706",
    )
    axes[0].set_xlabel("量测缺失率 (%)")
    axes[0].set_ylabel("五个随机种子的均值 ± 样本标准差")
    axes[0].set_title("缺失数据敏感性", weight="bold")
    axes[0].grid(alpha=0.25)
    axes[0].legend(frameon=False)

    y = np.arange(len(ablation))
    axes[1].barh(y, ablation["mean_f1"], xerr=ablation["std_f1"], color="#0F766E", capsize=3)
    axes[1].scatter(ablation["mean_f1"], y, color="#0F172A", marker="D", s=24, zorder=3)
    for row_index, mean_value in enumerate(ablation["mean_f1"]):
        axes[1].text(
            max(float(mean_value), 0.002) + 0.003,
            row_index,
            f"{float(mean_value):.3f}",
            va="center",
            fontsize=8,
        )
    axes[1].set_yticks(y, ablation["label"])
    axes[1].invert_yaxis()
    axes[1].set_xlabel("F1 均值 ± 样本标准差")
    axes[1].set_title("特征消融", weight="bold")
    axes[1].grid(axis="x", alpha=0.25)
    figure.suptitle("130 案例鲁棒性与消融实验节选", fontsize=15, weight="bold")
    figure.text(
        0.5,
        0.01,
        "来源：reports/metrics/robustness_aggregates.csv；误差线基于 5 个随机种子。",
        ha="center",
        fontsize=9,
        color="#475569",
    )
    figure.tight_layout(rect=(0, 0.05, 1, 0.94))
    _save(figure, path)


def generate_figures(output_dir: Path, source_root: Path = ROOT) -> list[Path]:
    """Generate all paper figures and return their paths."""
    _configure_fonts()
    output_dir.mkdir(parents=True, exist_ok=True)
    data = load_figure_data(source_root)
    paths = [output_dir / name for name in FIGURE_NAMES]
    _workflow_figure(paths[0])
    _baseline_figure(paths[1], data)
    _confusion_figure(paths[2], data)
    _robustness_figure(paths[3], data)
    return paths


if __name__ == "__main__":
    for generated_path in generate_figures(ROOT / "paper" / "figures"):
        print(generated_path.relative_to(ROOT))
