import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "ltverify", *args],
        capture_output=True,
        text=True,
        cwd=ROOT,
        check=False,
    )


def test_module_help_exits_zero() -> None:
    result = _run("--help")
    assert result.returncode == 0
    assert "run-all" in result.stdout


def test_run_all_prints_absolute_run_directory() -> None:
    result = _run("run-all", "--config", "tests/fixtures/small_config.yaml")
    assert result.returncode == 0, result.stderr
    lines = [line for line in result.stdout.splitlines() if line.strip()]
    printed = Path(lines[-1].strip())
    assert printed.is_absolute()
    assert printed.exists()


def test_stage_commands_are_removed_from_parser() -> None:
    result = _run("simulate", "--config", "tests/fixtures/small_config.yaml")
    assert result.returncode == 2
    assert "invalid choice" in result.stderr
