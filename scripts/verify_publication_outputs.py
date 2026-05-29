#!/usr/bin/env python3
"""Verify that the publication tables/data regenerate byte-for-byte.

The check intentionally excludes the generated DOCX file because ZIP metadata in
DOCX containers may differ between runs even when the XML content is unchanged.
"""

from __future__ import annotations

import argparse
import csv
import filecmp
import importlib.metadata
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
GENERATOR = REPO_ROOT / "scripts" / "generate_publication_outputs.py"
EXPECTED_ROOT = REPO_ROOT / "publication" / "generated"
EXPECTED_PYTHON = (3, 14, 4)
EXPECTED_PACKAGES = {
    "numpy": "2.4.6",
    "scipy": "1.17.1",
    "matplotlib": "3.10.9",
}

COMPARE_FILES = [
    "data/configuration_summary.csv",
    "data/replicate_metrics.csv",
    "data/threshold_noise_summary.csv",
    "data/threshold_robustness.csv",
    "data/threshold_robustness_summary.json",
    "data/top_peak_configs.csv",
    "data/warnings.csv",
    "tables/force_ratio_inner_outer_table.csv",
    "tables/force_ratio_inner_outer_table.md",
    "tables/force_ratio_inner_outer_table_numeric.csv",
    "tables/release_force_table.csv",
    "tables/release_force_table.md",
    "tables/release_force_table_numeric.csv",
    "tables/threshold_sensitivity_supplement.md",
]


def check_environment(*, allow_mismatch: bool) -> int:
    mismatches: list[str] = []
    current_python = sys.version_info[:3]
    if current_python != EXPECTED_PYTHON:
        mismatches.append(
            "Python "
            f"{current_python[0]}.{current_python[1]}.{current_python[2]} != "
            f"{EXPECTED_PYTHON[0]}.{EXPECTED_PYTHON[1]}.{EXPECTED_PYTHON[2]}"
        )
    for package, expected in EXPECTED_PACKAGES.items():
        try:
            actual = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            mismatches.append(f"{package} is not installed")
            continue
        if actual != expected:
            mismatches.append(f"{package} {actual} != {expected}")

    if not mismatches:
        return 0

    print("Environment does not match the submitted-output lock:")
    for mismatch in mismatches:
        print(f"- {mismatch}")
    print()
    print("Use the archived exact environment before verifying submitted outputs:")
    print("  python -m pip install -r requirements.txt")
    print("or run the included Dockerfile from a clean checkout.")
    if allow_mismatch:
        print()
        print("--allow-version-mismatch was supplied; continuing as a diagnostic run.")
        return 0
    print()
    print("For diagnostic-only comparison in a different environment, rerun with")
    print("--allow-version-mismatch. Such output is not the submitted reproduction target.")
    return 1


def read_config_row(path: Path, *, liner: str, sealant: str, side_label: str) -> dict[str, str]:
    with path.open("r", newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            if (
                row["liner_label"] == liner
                and row["sealant"] == sealant
                and row["side_label"] == side_label
            ):
                return row
    raise RuntimeError(f"Missing configuration row: {liner}/{sealant}/{side_label}")


def read_threshold_total(path: Path, threshold: str) -> str:
    with path.open("r", newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            if row["threshold_cN"] == threshold:
                return row["total_peaks"]
    raise RuntimeError(f"Missing threshold row: {threshold}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Regenerate publication tabular outputs and compare them with the archive."
    )
    parser.add_argument(
        "--keep-temp",
        action="store_true",
        help="Keep the temporary regenerated output directory for inspection.",
    )
    parser.add_argument(
        "--allow-version-mismatch",
        action="store_true",
        help=(
            "Continue even if Python/package versions do not match the submitted "
            "reproduction lock. This is for diagnostics only."
        ),
    )
    args = parser.parse_args()

    environment_status = check_environment(allow_mismatch=args.allow_version_mismatch)
    if environment_status:
        return environment_status

    temp_dir = Path(tempfile.mkdtemp(prefix="slipstick_verify_"))
    try:
        subprocess.run(
            [
                sys.executable,
                str(GENERATOR),
                "--tables-only",
                "--output-dir",
                str(temp_dir),
            ],
            cwd=REPO_ROOT,
            check=True,
        )

        failures: list[str] = []
        for relative in COMPARE_FILES:
            expected = EXPECTED_ROOT / relative
            regenerated = temp_dir / relative
            if not expected.exists():
                failures.append(f"missing expected file: {relative}")
                continue
            if not regenerated.exists():
                failures.append(f"missing regenerated file: {relative}")
                continue
            if not filecmp.cmp(expected, regenerated, shallow=False):
                failures.append(f"content differs: {relative}")

        config_row = read_config_row(
            temp_dir / "data" / "configuration_summary.csv",
            liner="Rossella",
            sealant="C1E",
            side_label="outer",
        )
        if config_row["peak_count_1p4cN_mean"] != "4.300000":
            failures.append(
                "Rossella/C1E outer mean peak count changed: "
                f"{config_row['peak_count_1p4cN_mean']} != 4.300000"
            )
        if config_row["peak_count_1p4cN_sum"] != "43":
            failures.append(
                "Rossella/C1E outer peak-count sum changed: "
                f"{config_row['peak_count_1p4cN_sum']} != 43"
            )

        total_14 = read_threshold_total(temp_dir / "data" / "threshold_robustness.csv", "1.400")
        if total_14 != "904":
            failures.append(f"threshold 1.4 cN total peaks changed: {total_14} != 904")

        if failures:
            print("Publication output verification failed:")
            for failure in failures:
                print(f"- {failure}")
            print(f"Regenerated outputs: {temp_dir}")
            return 1

        print("Publication output verification passed.")
        print("Checked files:")
        for relative in COMPARE_FILES:
            print(f"- {relative}")
        print("Sentinel values:")
        print("- Rossella/C1E outer peak_count_1p4cN_mean = 4.300000")
        print("- Rossella/C1E outer peak_count_1p4cN_sum = 43")
        print("- threshold 1.4 cN total_peaks = 904")
        return 0
    finally:
        if args.keep_temp:
            print(f"Kept temporary outputs: {temp_dir}")
        else:
            shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
