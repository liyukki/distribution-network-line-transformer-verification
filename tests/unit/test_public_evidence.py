from pathlib import Path

from ltverify.io import read_json
from ltverify.manifest import verify_manifest_hashes
from ltverify.report import generate_default_summary

ROOT = Path(__file__).resolve().parents[2]
BUNDLE = ROOT / "reports" / "evidence" / "default_run"


def test_public_default_evidence_reproduces_canonical_reports(
    tmp_path: Path,
) -> None:
    manifest = read_json(BUNDLE / "manifest.json")
    verify_manifest_hashes(manifest, BUNDLE)
    summary = tmp_path / "default_summary.json"
    manifest_copy = tmp_path / "default_manifest.json"
    generate_default_summary(BUNDLE, summary, manifest_output=manifest_copy)
    assert (
        summary.read_bytes() == (ROOT / "reports" / "metrics" / "default_summary.json").read_bytes()
    )
    assert (
        manifest_copy.read_bytes()
        == (ROOT / "reports" / "metrics" / "default_manifest.json").read_bytes()
    )


def test_public_default_evidence_file_set_is_exact() -> None:
    manifest = read_json(BUNDLE / "manifest.json")
    expected = {"manifest.json", *manifest["output_paths"]}
    actual = {path.name for path in BUNDLE.iterdir()}
    assert actual == expected
