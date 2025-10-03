"""Compute average force within a displacement window across all datasets."""

from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path
from typing import Iterable, List, Tuple

if __package__ in (None, ""):
    sys.path.append(str(Path(__file__).resolve().parent.parent))

import numpy as np

from slip_stick import ftm10

from scripts import detrend_savgol

DATASET_DIR = Path("datasets")
DEFAULT_MIN_MM = 50.0
DEFAULT_MAX_MM = 200.0
SCALE_FACTOR = 25.0 / 90.0


def parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--datasets",
        nargs="*",
        help="Optional list of dataset filenames to include (default: all CSVs).",
    )
    parser.add_argument(
        "--preview-lines",
        type=int,
        default=ftm10.DEFAULT_PREVIEW_LINES,
        help="Preview rows forwarded to the parser dialect sniffing (default: %(default)s).",
    )
    parser.add_argument(
        "--distance-range",
        nargs=2,
        type=float,
        metavar=("MIN_MM", "MAX_MM"),
        default=(DEFAULT_MIN_MM, DEFAULT_MAX_MM),
        help="Displacement window [min, max] in millimetres (default: %(default)s).",
    )
    return parser.parse_args(list(argv) if argv is not None else None)


def main(argv: Iterable[str] | None = None) -> int:
    args = parse_args(argv)
    result = compute_average_force(
        datasets=args.datasets,
        preview_lines=args.preview_lines,
        distance_range=tuple(args.distance_range),
        scale_factor=SCALE_FACTOR,
    )

    for entry in result["datasets"]:
        print(
            f"Processing {entry['dataset']} ...\n"
            f"  included replicates: {entry['included']} / {entry['total']} | "
            f"mean force = {entry['mean_force']:.6f} N"
        )

    print("\n=== Aggregate Results ===")
    for entry in result["datasets"]:
        print(
            f"{entry['dataset']}: mean force = {entry['mean_force']:.6f} N (scaled = "
            f"{entry['scaled_force']:.6f} N) over {entry['samples']} samples"
        )

    print(f"\nOverall mean force ({args.distance_range[0]}-{args.distance_range[1]} mm): {result['overall_mean']:.6f} N")
    print(f"Scaled by 25/90: {result['scaled_mean']:.6f} N")
    return 0


def compute_average_force(
    *,
    datasets: Iterable[str | Path] | None = None,
    preview_lines: int = ftm10.DEFAULT_PREVIEW_LINES,
    distance_range: Tuple[float, float] = (DEFAULT_MIN_MM, DEFAULT_MAX_MM),
    scale_factor: float = SCALE_FACTOR,
) -> dict:
    d_min, d_max = distance_range
    if not math.isfinite(d_min) or not math.isfinite(d_max) or d_max <= d_min:
        raise ValueError("distance range must satisfy min < max and both finite")

    dataset_paths = detrend_savgol.resolve_dataset_paths(datasets)
    if not dataset_paths:
        raise ValueError("no datasets found")

    overall_sum = 0.0
    overall_count = 0
    dataset_results: List[dict] = []

    for dataset_path in dataset_paths:
        series_list = detrend_savgol.gather_replicate_series(dataset_path, preview_lines)
        ds_sum = 0.0
        ds_count = 0
        included = 0
        for entry in series_list:
            disp = entry["disp_mm"].astype(float)
            force = entry["force_N"].astype(float)
            mask = np.isfinite(disp) & np.isfinite(force) & (disp >= d_min) & (disp <= d_max)
            if not np.any(mask):
                continue
            samples = force[mask]
            ds_sum += float(np.sum(samples))
            ds_count += int(samples.size)
            included += 1

        if ds_count == 0:
            dataset_results.append(
                {
                    "dataset": dataset_path.name,
                    "mean_force": float("nan"),
                    "scaled_force": float("nan"),
                    "samples": 0,
                    "included": included,
                    "total": len(series_list),
                }
            )
            continue

        mean_force = ds_sum / ds_count
        scaled_force = mean_force * scale_factor
        dataset_results.append(
            {
                "dataset": dataset_path.name,
                "mean_force": mean_force,
                "scaled_force": scaled_force,
                "samples": ds_count,
                "included": included,
                "total": len(series_list),
            }
        )
        overall_sum += ds_sum
        overall_count += ds_count

    if overall_count == 0:
        raise ValueError("no samples captured across datasets")

    overall_mean = overall_sum / overall_count
    scaled_mean = overall_mean * scale_factor

    return {
        "datasets": dataset_results,
        "overall_mean": overall_mean,
        "scaled_mean": scaled_mean,
        "scale_factor": scale_factor,
        "distance_range": distance_range,
    }
    args = parse_args(argv)
    d_min, d_max = args.distance_range
    if not math.isfinite(d_min) or not math.isfinite(d_max) or d_max <= d_min:
        raise SystemExit("distance range must satisfy min < max and both finite")

    dataset_paths = (
        [DATASET_DIR / name for name in args.datasets]
        if args.datasets
        else sorted(DATASET_DIR.glob("*.csv"))
    )
    if not dataset_paths:
        raise SystemExit("no datasets found")

    overall_sum = 0.0
    overall_count = 0
    dataset_results: List[Tuple[str, float, int]] = []  # (name, sum, count)

    for dataset_path in dataset_paths:
        print(f"Processing {dataset_path.name} ...")
        try:
            series_list = detrend_savgol.gather_replicate_series(dataset_path, args.preview_lines)
        except Exception as exc:  # pragma: no cover - defensive
            print(f"  failed to load dataset: {exc}")
            continue

        ds_sum = 0.0
        ds_count = 0
        skipped = 0
        for entry in series_list:
            disp = entry["disp_mm"].astype(float)
            force = entry["force_N"].astype(float)
            mask = np.isfinite(disp) & np.isfinite(force) & (disp >= d_min) & (disp <= d_max)
            if not np.any(mask):
                skipped += 1
                continue
            samples = force[mask]
            ds_sum += float(np.sum(samples))
            ds_count += int(samples.size)

        if ds_count == 0:
            print("  no samples in range; skipping dataset")
            continue

        dataset_results.append((dataset_path.name, ds_sum, ds_count))
        overall_sum += ds_sum
        overall_count += ds_count
        mean_force = ds_sum / ds_count
        print(
            f"  included replicates: {len(series_list) - skipped}/{len(series_list)} | "
            f"mean force = {mean_force:.6f} N"
        )

    if overall_count == 0:
        raise SystemExit("no samples captured across datasets")

    overall_mean = overall_sum / overall_count
    scaled = overall_mean * (25.0 / 90.0)

    print("\n=== Aggregate Results ===")
    for name, ds_sum, ds_count in dataset_results:
        mean_force = ds_sum / ds_count
        scaled_force = mean_force * (25.0 / 90.0)
        print(
            f"{name}: mean force = {mean_force:.6f} N (scaled = {scaled_force:.6f} N) "
            f"over {ds_count} samples"
        )

    print(f"\nOverall mean force (50-200 mm): {overall_mean:.6f} N")
    print(f"Scaled by 25/90: {scaled:.6f} N")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
