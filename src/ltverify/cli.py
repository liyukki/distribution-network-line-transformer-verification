"""Command-line entry points for the verification project."""

import argparse
import sys
from pathlib import Path

from ltverify.pipeline import run_pipeline

_SUBCOMMANDS = ("simulate", "corrupt", "diagnose", "evaluate", "run-all")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ltverify",
        description="配电网线变关系智能校验命令行工具",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    for name in _SUBCOMMANDS:
        sub = subparsers.add_parser(name)
        sub.add_argument("--config", required=True, help="YAML 配置文件路径")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    config_path = Path(args.config)
    if args.command == "run-all":
        try:
            run_dir = run_pipeline(config_path)
        except Exception as exc:  # noqa: BLE001 - CLI top-level boundary
            print(f"run-all failed: {type(exc).__name__}: {exc}", file=sys.stderr)
            return 1
        print(run_dir.resolve())
        return 0
    if not config_path.exists():
        print(f"missing prerequisite artifact: {config_path.resolve()}")
        return 1
    print(f"{args.command} prerequisites satisfied: {config_path.resolve()}")
    return 0
