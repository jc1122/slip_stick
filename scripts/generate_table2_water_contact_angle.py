#!/usr/bin/env python3
"""Regenerate manuscript Table 2 water-contact-angle summary from source CSV."""

from __future__ import annotations

import argparse
import csv
import statistics
from dataclasses import dataclass
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIR = REPO_ROOT / "publication" / "source_data"
DEFAULT_RAW = SOURCE_DIR / "table2_water_contact_angle_gonio_raw.csv"
DEFAULT_OUTPUT = SOURCE_DIR / "table2_water_contact_angle.csv"
CANONICAL_ORDER = ("C1E", "U2E", "C1EN", "T1E", "T2E", "T1EN", "T2EN")


@dataclass(frozen=True)
class ContactAngleRow:
    sample: str
    measurement_index: int
    contact_angle_deg: float
    used_for_reported_mean: bool


def parse_bool(value: str, *, row_number: int) -> bool:
    normalized = value.strip().lower()
    if normalized == "true":
        return True
    if normalized == "false":
        return False
    raise ValueError(f"Invalid used_for_reported_mean value on row {row_number}: {value!r}")


def load_rows(path: Path) -> list[ContactAngleRow]:
    rows: list[ContactAngleRow] = []
    with path.open("r", newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        required = {
            "canonical_sample",
            "measurement_index",
            "contact_angle_deg",
            "used_for_reported_mean",
        }
        missing = required.difference(reader.fieldnames or [])
        if missing:
            raise ValueError(f"{path} is missing required columns: {', '.join(sorted(missing))}")

        for row_number, row in enumerate(reader, start=2):
            sample = row["canonical_sample"].strip()
            if sample not in CANONICAL_ORDER:
                raise ValueError(f"Unexpected sample on row {row_number}: {sample!r}")
            rows.append(
                ContactAngleRow(
                    sample=sample,
                    measurement_index=int(row["measurement_index"]),
                    contact_angle_deg=float(row["contact_angle_deg"]),
                    used_for_reported_mean=parse_bool(
                        row["used_for_reported_mean"], row_number=row_number
                    ),
                )
            )
    return rows


def central_three_indices(rows: list[ContactAngleRow]) -> set[int]:
    by_value = sorted(rows, key=lambda row: (row.contact_angle_deg, row.measurement_index))
    return {row.measurement_index for row in by_value[1:-1]}


def summarize(rows: list[ContactAngleRow]) -> list[dict[str, str]]:
    by_sample = {sample: [] for sample in CANONICAL_ORDER}
    for row in rows:
        by_sample[row.sample].append(row)

    summary: list[dict[str, str]] = []
    for sample in CANONICAL_ORDER:
        sample_rows = sorted(by_sample[sample], key=lambda row: row.measurement_index)
        if len(sample_rows) != 5:
            raise ValueError(f"{sample} has {len(sample_rows)} measurements; expected 5")
        measurement_indices = [row.measurement_index for row in sample_rows]
        if measurement_indices != [0, 1, 2, 3, 4]:
            raise ValueError(f"{sample} measurement indices are {measurement_indices}; expected 0..4")

        expected_used = central_three_indices(sample_rows)
        actual_used = {row.measurement_index for row in sample_rows if row.used_for_reported_mean}
        if actual_used != expected_used:
            raise ValueError(
                f"{sample} used_for_reported_mean flags do not match central-three rule: "
                f"{sorted(actual_used)} != {sorted(expected_used)}"
            )

        central_values = [
            row.contact_angle_deg for row in sample_rows if row.measurement_index in expected_used
        ]
        summary.append(
            {
                "sample": sample,
                "water_contact_angle_mean_deg": f"{statistics.mean(central_values):.1f}",
                "water_contact_angle_sd_deg": f"{statistics.stdev(central_values):.1f}",
                "measurements_acquired": str(len(sample_rows)),
                "central_values_used": str(len(central_values)),
            }
        )
    return summary


def write_summary(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "sample",
        "water_contact_angle_mean_deg",
        "water_contact_angle_sd_deg",
        "measurements_acquired",
        "central_values_used",
    ]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Regenerate the manuscript Table 2 water-contact-angle summary from "
            "the replicate-level source CSV."
        )
    )
    parser.add_argument("--raw", type=Path, default=DEFAULT_RAW, help="Input raw contact-angle CSV.")
    parser.add_argument(
        "--output", type=Path, default=DEFAULT_OUTPUT, help="Output processed Table 2 CSV."
    )
    args = parser.parse_args()

    rows = summarize(load_rows(args.raw))
    write_summary(args.output, rows)
    print(f"Wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
