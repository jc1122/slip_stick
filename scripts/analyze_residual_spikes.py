"""Inspect Savitzky–Golay residuals and flag slip–stick-like spikes."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Iterable, List, Sequence, Tuple

if __package__ in (None, ""):
    sys.path.append(str(Path(__file__).resolve().parent.parent))

import numpy as np

OUTPUT_ROOT = Path("outputs/savgol")
DEFAULT_THRESHOLD_RATIO = 10.0
DEFAULT_THRESHOLD_ABS = 0.05  # N, default amplitude for visible spikes

__all__ = ["analyze_residuals"]


def parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--outputs",
        type=Path,
        default=OUTPUT_ROOT,
        help="Base directory containing <dataset>/rep*_savgol.npz files (default: outputs/savgol).",
    )
    parser.add_argument(
        "--datasets",
        nargs="*",
        help="Optional subset of dataset directory names to analyze.",
    )
    parser.add_argument(
        "--ratio-threshold",
        type=float,
        default=DEFAULT_THRESHOLD_RATIO,
        help="Minimum max_abs / MAD ratio to treat as slip-stick spike (default: %(default)s).",
    )
    parser.add_argument(
        "--abs-threshold",
        type=float,
        default=DEFAULT_THRESHOLD_ABS,
        help="Minimum absolute residual (N) to treat as spike (default: %(default)s).",
    )
    parser.add_argument(
        "--json",
        type=Path,
        help="Optional path to write JSON summary of per-replicate metrics.",
    )
    return parser.parse_args(list(argv) if argv is not None else None)


def summarize_dataset(
    dataset_dir: Path,
    ratio_threshold: float,
    abs_threshold: float,
) -> Tuple[List[dict], dict]:
    npz_files = sorted(dataset_dir.glob("*_savgol.npz"))
    records: List[dict] = []
    stats = {
        "dataset": dataset_dir.name,
        "total_replicates": len(npz_files),
        "flagged_replicates": 0,
    }

    for npz_path in npz_files:
        data = np.load(npz_path)
        residual = np.asarray(data["residual"], dtype=float)
        distance = np.asarray(data.get("distance", data.get("time")), dtype=float)
        time = np.asarray(data.get("time", distance), dtype=float)

        if residual.size == 0:
            continue

        abs_res = np.abs(residual)
        max_abs = float(np.max(abs_res))
        rms = float(np.sqrt(np.mean(residual * residual)))
        mad = float(np.median(np.abs(residual - np.median(residual))))
        mad = mad if mad > 1e-9 else 1e-9
        p99 = float(np.quantile(abs_res, 0.99))
        peak_idx = int(np.argmax(abs_res))
        peak_disp = float(distance[peak_idx]) if distance.size > peak_idx else float("nan")
        peak_time = float(time[peak_idx]) if time.size > peak_idx else float("nan")
        ratio = max_abs / mad

        flagged = (ratio >= ratio_threshold) and (max_abs >= abs_threshold)
        if flagged:
            stats["flagged_replicates"] += 1

        records.append(
            {
                "dataset": dataset_dir.name,
                "replicate": npz_path.stem.replace("_savgol", ""),
                "samples": int(residual.size),
                "rms": rms,
                "max_abs": max_abs,
                "mad": mad,
                "p99_abs": p99,
                "peak_ratio": ratio,
                "peak_distance_mm": peak_disp,
                "peak_time_s": peak_time,
                "has_spikes": flagged,
            }
        )

    return records, stats


def resolve_dataset_dirs(base: Path, datasets: Sequence[str | Path] | None) -> List[Path]:
    if not datasets:
        return sorted(p for p in base.iterdir() if p.is_dir())
    resolved: List[Path] = []
    for item in datasets:
        p = Path(item)
        if not p.is_absolute():
            candidate = base / p
            if candidate.exists():
                p = candidate
        if p.exists():
            resolved.append(p)
    return resolved


def analyze_residuals(
    datasets: Sequence[str | Path] | None = None,
    *,
    outputs_root: Path = OUTPUT_ROOT,
    ratio_threshold: float = DEFAULT_THRESHOLD_RATIO,
    abs_threshold: float = DEFAULT_THRESHOLD_ABS,
) -> dict:
    dataset_dirs = resolve_dataset_dirs(outputs_root, datasets)
    if not dataset_dirs:
        raise ValueError("no dataset directories found")

    all_records: List[dict] = []
    rollup: List[dict] = []

    for ds_dir in dataset_dirs:
        records, stats = summarize_dataset(ds_dir, ratio_threshold, abs_threshold)
        all_records.extend(records)
        rollup.append(stats)

    return {
        "parameters": {
            "ratio_threshold": ratio_threshold,
            "abs_threshold": abs_threshold,
        },
        "datasets": rollup,
        "replicates": all_records,
    }


def main(argv: Iterable[str] | None = None) -> int:
    args = parse_args(argv)
    if not args.outputs.exists():
        raise SystemExit(f"outputs directory not found: {args.outputs}")

    summary = analyze_residuals(
        datasets=args.datasets,
        outputs_root=args.outputs,
        ratio_threshold=args.ratio_threshold,
        abs_threshold=args.abs_threshold,
    )

    for stats in summary["datasets"]:
        print(
            f"Analyzing {stats['dataset']} ...\n"
            f"  replicates={stats['total_replicates']} | flagged={stats['flagged_replicates']}"
        )

    flagged_total = sum(item["flagged_replicates"] for item in summary["datasets"])
    total_reps = sum(item["total_replicates"] for item in summary["datasets"])
    print(
        f"\nTotals: {flagged_total}/{total_reps} replicates exceed ratio>= {args.ratio_threshold}"
        f" and |residual|>= {args.abs_threshold} N"
    )

    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        with args.json.open("w", encoding="utf-8") as handle:
            json.dump(summary, handle, indent=2)
        print(f"Wrote {args.json}")

    sorted_records = sorted(
        summary["replicates"], key=lambda r: r["peak_ratio"], reverse=True
    )
    print("\nTop spike candidates:")
    for rec in sorted_records[:10]:
        print(
            (
                "  {dataset}/{replicate}: max|res|={max_abs:.3f} N, peak_ratio={peak_ratio:.1f}, "
                "peak at {peak_distance_mm:.1f} mm ({peak_time_s:.2f} s)"
            ).format(**rec)
        )

    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
