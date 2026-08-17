import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

REQUIRED_HEADINGS = [
    "业务背景",
    "方法",
    "快速开始",
    "实验设计",
    "结果",
    "项目限制",
    "仓库结构",
    "面试展示",
]

ALLOWED_COMMAND_PREFIXES = (
    "python -m ltverify",
    "streamlit run",
    ".venv/Scripts/python.exe -m",
    ".venv/bin/python -m",
    "py -3.12 -m venv",
    "uv venv",
    "uv python install",
    "pip install",
    "git clone",
    "Set-Location",
)

REFERENCED_PATHS = [
    "configs/default.yaml",
    "configs/robustness.yaml",
    "scripts/run_pipeline.ps1",
    "scripts/run_dashboard.ps1",
    "app/streamlit_app.py",
    "docs/methodology.md",
    "docs/interview-guide.md",
    "data/README.md",
    "notebooks/01_network_sanity.ipynb",
    "notebooks/02_baseline_analysis.ipynb",
    "notebooks/03_robustness_analysis.ipynb",
    "AI_USAGE.md",
    "docs/audit-summary.md",
    "docs/design.md",
    ".github/workflows/ci.yml",
    "reports/evidence/default_run",
]


def _readme() -> str:
    return (ROOT / "README.md").read_text(encoding="utf-8")


def test_readme_contains_all_required_headings() -> None:
    text = _readme()
    for heading in REQUIRED_HEADINGS:
        assert f"## {heading}" in text, f"missing heading: {heading}"


def test_readme_has_no_fabricated_accuracy() -> None:
    assert not re.search(r"准确率.{0,8}90\.3%", _readme())


def test_readme_commands_use_public_entry_points() -> None:
    text = _readme()
    for line in text.splitlines():
        stripped = line.strip()
        if re.match(r"^(python |py |uv |pip |streamlit |git |Set-Location |\.venv/)", stripped):
            assert stripped.startswith(ALLOWED_COMMAND_PREFIXES), f"非公开入口命令: {stripped}"


def test_readme_referenced_paths_exist() -> None:
    text = _readme()
    for path in REFERENCED_PATHS:
        assert path in text, f"README 未引用路径: {path}"
        assert (ROOT / path).exists(), f"README 引用但不存在: {path}"


def test_streamlit_minimum_version_declared() -> None:
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert "streamlit>=1.51,<2" in pyproject
    requirements = (ROOT / "requirements.txt").read_text(encoding="utf-8")
    assert "streamlit>=1.51,<2" in requirements


def test_readme_evidence_command_includes_manifest_output() -> None:
    text = _readme()
    assert "--manifest-output" in text
    assert "reports/evidence/default_run" in text


def test_readme_uses_markdown_links_for_public_docs() -> None:
    text = _readme()
    for target in (
        "AI_USAGE.md",
        "docs/audit-summary.md",
        "docs/design.md",
        "docs/methodology.md",
        "docs/interview-guide.md",
        "data/README.md",
    ):
        assert f"]({target})" in text, f"README 缺少 Markdown 链接: {target}"


def test_public_docs_and_notebooks_have_no_local_absolute_paths() -> None:
    files = [
        ROOT / "README.md",
        ROOT / "AI_USAGE.md",
        ROOT / "docs" / "audit-summary.md",
        ROOT / "docs" / "design.md",
        ROOT / "docs" / "methodology.md",
        ROOT / "notebooks" / "01_network_sanity.ipynb",
        ROOT / "notebooks" / "02_baseline_analysis.ipynb",
        ROOT / "notebooks" / "03_robustness_analysis.ipynb",
    ]
    for path in files:
        text = path.read_text(encoding="utf-8")
        assert "D:\\" not in text, f"{path} 包含 D:\\ 本机路径"
        assert "C:\\Users\\" not in text, f"{path} 包含 C:\\Users\\ 本机路径"
