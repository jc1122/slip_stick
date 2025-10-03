"""End-to-end Savitzky–Golay workflow: detrend, average force, residual spikes."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Iterable, Sequence

if __package__ in (None, ""):
    sys.path.append(str(Path(__file__).resolve().parent.parent))

from slip_stick import ftm10

from scripts import analyze_residual_spikes, average_force, detrend_savgol

DEFAULT_DISTANCE_RANGE = detrend_savgol.DEFAULT_DISTANCE_RANGE
DEFAULT_WINDOW_SECONDS = 5.0
DEFAULT_POLYORDER = 3
DEFAULT_RATIO_THRESHOLD = analyze_residual_spikes.DEFAULT_THRESHOLD_RATIO
DEFAULT_ABS_THRESHOLD = analyze_residual_spikes.DEFAULT_THRESHOLD_ABS


def parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--datasets",
        nargs="*",
        help="Optional dataset filenames (CSV) or SavGol directories to process.",
    )
    parser.add_argument(
        "--window-seconds",
        type=float,
        default=DEFAULT_WINDOW_SECONDS,
        help="Savitzky–Golay window size in seconds (default: %(default)s).",
    )
    parser.add_argument(
        "--polyorder",
        type=int,
        default=DEFAULT_POLYORDER,
        help="Savitzky–Golay polynomial order (default: %(default)s).",
    )
    parser.add_argument(
        "--distance-range",
        nargs=2,
        type=float,
        metavar=("MIN_MM", "MAX_MM"),
        default=DEFAULT_DISTANCE_RANGE,
        help="Displacement window [min, max] in mm (default: %(default)s).",
    )
    parser.add_argument(
        "--ratio-threshold",
        type=float,
        default=DEFAULT_RATIO_THRESHOLD,
        help="Residual spike ratio threshold (default: %(default)s).",
    )
    parser.add_argument(
        "--abs-threshold",
        type=float,
        default=DEFAULT_ABS_THRESHOLD,
        help="Residual spike absolute threshold in N (default: %(default)s).",
    )
    parser.add_argument(
        "--preview-lines",
        type=int,
        default=ftm10.DEFAULT_PREVIEW_LINES,
        help="Preview rows forwarded to the parser sniffing (default: %(default)s).",
    )
    parser.add_argument(
        "--outputs-root",
        type=Path,
        default=detrend_savgol.DEFAULT_OUTPUT_DIR,
        help="Directory for SavGol outputs (default: outputs/savgol).",
    )
    parser.add_argument(
        "--summary-json",
        type=Path,
        help="Optional path to write a consolidated JSON summary.",
    )
    return parser.parse_args(list(argv) if argv is not None else None)


def run_workflow(args: argparse.Namespace) -> dict:
    dataset_paths = detrend_savgol.resolve_dataset_paths(args.datasets)
    if not dataset_paths:
        raise ValueError("no datasets found")

    distance_range = tuple(float(x) for x in args.distance_range)

    # Step 1: SavGol detrending
    detrend_summaries = detrend_savgol.run_detrend(
        dataset_paths,
        output_root=args.outputs_root,
        window_seconds=args.window_seconds,
        polyorder=args.polyorder,
        preview_lines=args.preview_lines,
        axis="distance",
        distance_range=distance_range,
    )

    # Step 2: Average force statistics
    avg_stats = average_force.compute_average_force(
        datasets=dataset_paths,
        preview_lines=args.preview_lines,
        distance_range=distance_range,
    )

    # Step 3: Residual spike analysis
    spike_dirs = [Path(entry["output_dir"]) for entry in detrend_summaries]
    spike_summary = analyze_residual_spikes.analyze_residuals(
        datasets=spike_dirs,
        outputs_root=args.outputs_root,
        ratio_threshold=args.ratio_threshold,
        abs_threshold=args.abs_threshold,
    )

    return {
        "parameters": {
            "window_seconds": args.window_seconds,
            "polyorder": args.polyorder,
            "distance_range": distance_range,
            "ratio_threshold": args.ratio_threshold,
            "abs_threshold": args.abs_threshold,
        },
        "detrend": detrend_summaries,
        "average_force": avg_stats,
        "spikes": spike_summary,
    }


def main(argv: Iterable[str] | None = None) -> int:
    args = parse_args(argv)
    summary = run_workflow(args)

    print("SavGol detrending complete:")
    for entry in summary["detrend"]:
        print(
            f"  {entry['dataset']}: {entry['replicates']} replicates, window={entry['window_seconds']}s, "
            f"polyorder={entry['polyorder']}"
        )

    print("\nAverage force (scaled by 25/90):")
    for entry in summary["average_force"]["datasets"]:
        print(
            f"  {entry['dataset']}: mean={entry['mean_force']:.6f} N, scaled={entry['scaled_force']:.6f} N, "
            f"samples={entry['samples']}"
        )
    print(
        f"Overall mean={summary['average_force']['overall_mean']:.6f} N | "
        f"scaled={summary['average_force']['scaled_mean']:.6f} N"
    )

    spike_summary = summary["spikes"]
    flagged_total = sum(item["flagged_replicates"] for item in spike_summary["datasets"])
    total_reps = sum(item["total_replicates"] for item in spike_summary["datasets"])
    print(
        f"\nResidual spikes: {flagged_total}/{total_reps} replicates exceed ratio>="
        f" {summary['parameters']['ratio_threshold']} and |residual|>="
        f" {summary['parameters']['abs_threshold']} N"
    )

    for rec in sorted(
        spike_summary["replicates"], key=lambda r: r["peak_ratio"], reverse=True
    )[:10]:
        print(
            (
                "  {dataset}/{replicate}: max|res|={max_abs:.3f} N, peak_ratio={peak_ratio:.1f}, "
                "peak at {peak_distance_mm:.1f} mm ({peak_time_s:.2f} s)"
            ).format(**rec)
        )

    if args.summary_json:
        args.summary_json.parent.mkdir(parents=True, exist_ok=True)
        with args.summary_json.open("w", encoding="utf-8") as handle:
            json.dump(summary, handle, indent=2)
        print(f"\nSummary written to {args.summary_json}")

    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
