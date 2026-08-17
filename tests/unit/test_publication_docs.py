"""Public documentation and paper release contracts."""

from __future__ import annotations

import re
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
