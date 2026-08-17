"""Public documentation and paper release contracts."""

from __future__ import annotations

import json
import re
from hashlib import sha256
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
GUIDE = ROOT / "docs" / "user-guide.md"
PAPER = ROOT / "paper" / "line-transformer-verification-paper.md"
BIBLIOGRAPHY = ROOT / "paper" / "references.bib"
PDF = ROOT / "paper" / "line-transformer-verification-paper.pdf"
FIGURE_DIR = ROOT / "paper" / "figures"

REQUIRED_GUIDE_HEADINGS = (
    "环境要求",
    "安装",
    "快速开始",
    "命令行",
    "可视化看板",
    "运行产物",
    "公开证据复现",
    "鲁棒性实验",
    "教学 Notebook",
    "故障排查",
    "项目边界",
    "面试演示",
)
REQUIRED_PAPER_HEADINGS = (
    "摘要",
    "引言",
    "问题定义",
    "数据与系统",
    "方法",
    "软件实现",
    "实验设置",
    "实验结果",
    "鲁棒性与消融",
    "讨论与局限",
    "结论",
    "复现声明",
    "参考文献",
)
REQUIRED_FIGURES = (
    "system-workflow.png",
    "baseline-comparison.png",
    "confusion-matrix.png",
    "robustness-ablation.png",
)


def _read_required(path: Path) -> str:
    assert path.is_file(), f"缺少发布文件: {path.relative_to(ROOT)}"
    return path.read_text(encoding="utf-8")


@pytest.mark.parametrize(
    "path",
    [GUIDE, PAPER, BIBLIOGRAPHY, PDF],
)
def test_publication_artifacts_exist(path: Path) -> None:
    assert path.is_file(), f"缺少发布文件: {path.relative_to(ROOT)}"
    assert path.stat().st_size > 0


def test_user_guide_has_required_sections() -> None:
    guide = _read_required(GUIDE)
    for heading in REQUIRED_GUIDE_HEADINGS:
        assert re.search(rf"^#+\s+.*{re.escape(heading)}", guide, re.MULTILINE), heading


def test_user_guide_relative_links_resolve() -> None:
    guide = _read_required(GUIDE)
    targets = re.findall(r"\[[^]]+\]\(([^)]+)\)", guide)
    relative_targets = [
        target.split("#", 1)[0]
        for target in targets
        if target and not target.startswith(("http://", "https://", "mailto:", "#"))
    ]
    assert relative_targets
    for target in relative_targets:
        assert (GUIDE.parent / target).resolve().exists(), target


def test_paper_has_required_sections_and_honest_headline_results() -> None:
    paper = _read_required(PAPER)
    for heading in REQUIRED_PAPER_HEADINGS:
        assert re.search(rf"^#+\s+.*{re.escape(heading)}", paper, re.MULTILINE), heading
    for value in ("24", "5", "0.167", "0.378", "0.200", "0.400", "130"):
        assert value in paper


def test_paper_references_all_required_figures() -> None:
    paper = _read_required(PAPER)
    for name in REQUIRED_FIGURES:
        assert f"figures/{name}" in paper
        figure = FIGURE_DIR / name
        assert figure.is_file(), name
        assert figure.stat().st_size > 10_000


def test_bibliography_contains_verifiable_dois() -> None:
    bibliography = _read_required(BIBLIOGRAPHY)
    dois = re.findall(r"doi\s*=\s*[{\"]([^}\"]+)", bibliography, re.IGNORECASE)
    assert len(dois) >= 6
    assert all(doi.startswith("10.") for doi in dois)


def test_paper_contains_method_equations_and_evidence_boundaries() -> None:
    paper = _read_required(PAPER)
    for token in (
        "z_{i,t}",
        "r_{xy}",
        "S(i,f)",
        "current_score_threshold",
        "margin_threshold",
        "same_feeder_residual_corr_mean",
        "cross_feeder_residual_corr_mean",
    ):
        assert token in paper
    assert "0.167" in paper and "0.378" in paper
    assert "不代表真实电网" in paper
    assert "尚未实现" in paper


def test_every_bibliography_entry_is_cited() -> None:
    paper = _read_required(PAPER)
    bibliography = _read_required(BIBLIOGRAPHY)
    keys = set(re.findall(r"@\w+\{([^,]+),", bibliography))
    citations = set(re.findall(r"\[@([A-Za-z0-9_:-]+)\]", paper))
    assert len(keys) >= 10
    assert citations == keys


def test_paper_headline_numbers_match_public_summary() -> None:
    paper = _read_required(PAPER)
    summary = json.loads(
        (ROOT / "reports/metrics/default_summary.json").read_text(encoding="utf-8")
    )
    metrics = summary["metrics"]
    expected = (
        f"F1 仅为 {metrics['f1']:.3f}",
        f"PR-AUC 为 {metrics['pr_auc']:.3f}",
        (
            f"Top-1/Top-2 修正率为 {metrics['top1_correction_rate']:.3f}/"
            f"{metrics['top2_correction_rate']:.3f}"
        ),
        f"同馈线残差相关均值为 {summary['failure_boundary']['same_feeder_residual_corr_mean']:.3f}",
        f"跨馈线均值为 {summary['failure_boundary']['cross_feeder_residual_corr_mean']:.3f}",
    )
    for claim in expected:
        assert claim in paper


def test_publication_sources_do_not_make_prohibited_claims() -> None:
    combined = "\n".join(
        path.read_text(encoding="utf-8") for path in (GUIDE, PAPER) if path.exists()
    )
    prohibited = (
        "准确率达到90%",
        "准确率达90%",
        "工业级准确率",
        "已在真实电网投运",
        "已完成现场部署",
        "数字签名保证",
    )
    for phrase in prohibited:
        assert phrase not in combined


def _digest(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def test_paper_figure_data_is_loaded_from_public_evidence() -> None:
    from scripts.generate_paper_figures import load_figure_data

    data = load_figure_data(ROOT)
    assert data["enhanced"]["f1"] == pytest.approx(0.16666666666666666)
    assert data["enhanced"]["pr_auc"] == pytest.approx(0.3778787878787879)
    assert data["baseline"]["f1"] == pytest.approx(0.0)
    assert data["confusion_matrix"] == [[13, 6], [4, 1]]


def test_generate_paper_figures_does_not_mutate_evidence(tmp_path: Path) -> None:
    from scripts.generate_paper_figures import generate_figures

    sources = (
        ROOT / "reports/metrics/default_summary.json",
        ROOT / "reports/evidence/default_run/confusion_matrix.csv",
        ROOT / "reports/metrics/robustness_aggregates.csv",
    )
    before = {path: _digest(path) for path in sources}
    generated = generate_figures(tmp_path, ROOT)
    assert {path.name for path in generated} == set(REQUIRED_FIGURES)
    assert all(path.is_file() and path.stat().st_size > 10_000 for path in generated)
    assert {path: _digest(path) for path in sources} == before
