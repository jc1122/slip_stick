"""Apply a Savitzky–Golay baseline to all datasets and render SVG overlays.

Usage
-----
python -m scripts.detrend_savgol --window-seconds 2.5 --polyorder 3

Outputs are written under ``outputs/savgol/<dataset>/`` and include per-replicate NPZ
files plus a dataset-level SVG preview with three panels (shared x-axis of time or
displacement). Optional distance filtering crops each replicate before smoothing so
the overlays focus on a region of interest (e.g. 50–200 mm):
1. Original force traces (overlay of replicates).
2. Savitzky–Golay baseline for each replicate.
3. Detrended residual emphasising slip–stick spikes.
"""

from __future__ import annotations

import argparse
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Sequence, Tuple

import numpy as np
import pandas as pd

from slip_stick import ftm10
from slip_stick.savgol import savgol_filter_1d

DEFAULT_WINDOW_SECONDS = 2.5
DEFAULT_POLYORDER = 3
DEFAULT_DISTANCE_RANGE = (50.0, 200.0)
DEFAULT_OUTPUT_DIR = Path("outputs/savgol")
DATASET_DIR = Path("datasets")
COLORS = [
    "#1f77b4",
    "#ff7f0e",
    "#2ca02c",
    "#d62728",
    "#9467bd",
    "#8c564b",
    "#e377c2",
    "#7f7f7f",
    "#bcbd22",
    "#17becf",
]

__all__ = [
    "ReplicateResult",
    "run_detrend",
    "gather_replicate_series",
    "process_dataset",
]


@dataclass
class ReplicateResult:
    replicate_id: str
    time_s: np.ndarray
    disp_mm: np.ndarray
    force: np.ndarray
    baseline: np.ndarray
    residual: np.ndarray
    fs: float
    window_length: int
    polyorder: int


def parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--datasets",
        nargs="*",
        help="Specific dataset filenames to process (defaults to all in datasets/).",
    )
    parser.add_argument(
        "--window-seconds",
        type=float,
        default=DEFAULT_WINDOW_SECONDS,
        help="Savitzky–Golay window size in seconds (converted per replicate).",
    )
    parser.add_argument(
        "--polyorder",
        type=int,
        default=DEFAULT_POLYORDER,
        help="Polynomial order for the Savitzky–Golay filter.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Base directory for NPZ and SVG outputs.",
    )
    parser.add_argument(
        "--preview-lines",
        type=int,
        default=ftm10.DEFAULT_PREVIEW_LINES,
        help="Preview lines passed to the parser dialect sniffing.",
    )
    parser.add_argument(
        "--axis",
        choices=("time", "distance"),
        default="distance",
        help="X-axis for plots (time in seconds or displacement in millimetres).",
    )
    parser.add_argument(
        "--distance-range",
        nargs=2,
        type=float,
        metavar=("MIN_MM", "MAX_MM"),
        help="Optional displacement window [min, max] in mm to crop before detrending.",
    )
    return parser.parse_args(list(argv) if argv is not None else None)


def ensure_output_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def resolve_dataset_paths(datasets: Iterable[str | Path] | None) -> List[Path]:
    if not datasets:
        return sorted(DATASET_DIR.glob("*.csv"))

    resolved: List[Path] = []
    for item in datasets:
        p = Path(item)
        if not p.exists():
            alt = DATASET_DIR / p
            if alt.exists():
                p = alt
        resolved.append(p)
    return resolved


def run_detrend(
    datasets: Iterable[str | Path] | None = None,
    *,
    output_root: Path = DEFAULT_OUTPUT_DIR,
    window_seconds: float = DEFAULT_WINDOW_SECONDS,
    polyorder: int = DEFAULT_POLYORDER,
    preview_lines: int = ftm10.DEFAULT_PREVIEW_LINES,
    axis: str = "distance",
    distance_range: Tuple[float, float] | None = None,
) -> List[dict]:
    """Detrend datasets and write Savitzky–Golay artifacts.

    Returns a list of dictionaries summarising the processed datasets (dataset name and
    replicate count)."""

    dataset_paths = resolve_dataset_paths(datasets)
    if not dataset_paths:
        raise ValueError("no datasets found")

    ensure_output_dir(output_root)
    if distance_range is None and axis == "distance":
        distance_range = DEFAULT_DISTANCE_RANGE

    summaries: List[dict] = []
    for dataset_path in dataset_paths:
        results = process_dataset(
            dataset_path,
            output_root,
            window_seconds,
            polyorder,
            preview_lines,
            axis,
            distance_range,
        )
        summaries.append(
            {
                "dataset": dataset_path.name,
                "dataset_path": str(dataset_path),
                "replicates": len(results),
                "window_seconds": window_seconds,
                "polyorder": polyorder,
                "axis": axis,
                "distance_range": distance_range,
                "output_dir": str(output_root / dataset_path.stem),
            }
        )
    return summaries


def gather_replicate_series(path: Path, preview_lines: int) -> List[dict]:
    """Return per-replicate time/force arrays using the ftm10 parser or a fallback."""

    try:
        df_long, meta = ftm10.load_ftm10_csv(
            str(path),
            preview_lines=preview_lines,
        )
        replicate_ids = list(meta.get("replicate_ids", []))
        if not replicate_ids:
            raise RuntimeError("parser returned no replicates")
        results: List[dict] = []
        for rep_id in replicate_ids:
            frame = df_long[df_long["replicate_id"] == rep_id]
            if frame.empty:
                continue
            fs_hint = None
            rep_meta = meta.get("replicates", {}).get(rep_id, {}) if isinstance(meta, dict) else {}
            if rep_meta:
                fs_hint = rep_meta.get("Fs")
            results.append(
                {
                    "replicate_id": str(rep_id),
                    "time_s": frame["time_s"].to_numpy(dtype=float),
                    "disp_mm": frame["disp_mm"].to_numpy(dtype=float),
                    "force_N": frame["force_N"].to_numpy(dtype=float),
                    "fs": fs_hint,
                }
            )
        if results:
            return results
        raise RuntimeError("parser produced empty frames")
    except Exception as exc:
        print(f"  parser fallback for {path.name}: {exc}")
        return _gather_replicates_via_pandas(path)


def _gather_replicates_via_pandas(path: Path) -> List[dict]:
    """Fallback loader using pandas with a three-row header and decimal commas."""

    df = pd.read_csv(
        path,
        header=[0, 1, 2],
        sep=",",
        engine="python",
        encoding="cp1250",
    )

    n_cols = df.shape[1]
    if n_cols % 3 != 0:
        raise RuntimeError(f"unexpected column count {n_cols} in {path}")

    results: List[dict] = []
    current_rep: str | None = None
    for block_idx, col_idx in enumerate(range(0, n_cols, 3)):
        rep_label = str(df.columns[col_idx][0]).strip()
        if rep_label and not rep_label.startswith("Unnamed"):
            current_rep = rep_label
        if not current_rep:
            current_rep = f"rep{block_idx + 1:02d}"
        rep_id = current_rep.replace(" ", "")

        time_series = df.iloc[:, col_idx]
        force_series = df.iloc[:, col_idx + 1]
        disp_series = df.iloc[:, col_idx + 2]

        time = _series_to_float(time_series)
        disp = _series_to_float(disp_series)
        force = _series_to_float(force_series)

        results.append(
            {
                "replicate_id": rep_id,
                "time_s": time,
                "disp_mm": disp,
                "force_N": force,
            }
        )

    return results


def _series_to_float(series: pd.Series) -> np.ndarray:
    as_str = series.astype(str).str.replace(",", ".", regex=False)
    values = pd.to_numeric(as_str, errors="coerce")
    return values.to_numpy(dtype=float)


def estimate_fs(
    time_s: np.ndarray,
    fs_hint: float | None = None,
    *,
    label: str | None = None,
) -> float:
    if fs_hint is not None:
        try:
            fs_val = float(fs_hint)
        except (TypeError, ValueError):
            fs_val = math.nan
        if math.isfinite(fs_val) and fs_val > 0:
            return fs_val

    diffs = np.diff(time_s.astype(float))
    diffs = diffs[np.isfinite(diffs)]
    if diffs.size == 0:
        msg = "no finite time deltas"
        if label:
            msg = f"replicate {label} {msg}"
        raise RuntimeError(msg)
    dt_median = float(np.median(diffs))
    if not math.isfinite(dt_median) or dt_median <= 0:
        msg = f"median dt invalid: {dt_median!r}"
        if label:
            msg = f"replicate {label} {msg}"
        raise RuntimeError(msg)
    return 1.0 / dt_median


def compute_window_length(fs: float, n_samples: int, window_seconds: float, polyorder: int) -> int:
    desired = max(polyorder + 1, int(round(window_seconds * fs)))
    if desired % 2 == 0:
        desired += 1
    if desired >= n_samples:
        desired = n_samples if n_samples % 2 == 1 else n_samples - 1
    if desired < polyorder + 1:
        desired = polyorder + 1 if (polyorder + 1) % 2 == 1 else polyorder + 2
    if desired > n_samples:
        raise ValueError("unable to derive a valid window length for the signal")
    if desired % 2 == 0:
        desired += 1
    return desired


def fill_missing_values(y: np.ndarray) -> np.ndarray:
    mask = np.isfinite(y)
    if mask.all():
        return y
    y = y.copy()
    idx = np.flatnonzero(mask)
    if idx.size == 0:
        return np.zeros_like(y)
    if idx.size == 1:
        y[~mask] = y[idx[0]]
        return y
    missing = np.flatnonzero(~mask)
    y[~mask] = np.interp(missing, idx, y[idx])
    return y


def savgol_baseline(
    time_s: np.ndarray,
    force: np.ndarray,
    fs: float,
    window_seconds: float,
    polyorder: int,
) -> Tuple[np.ndarray, int]:
    clean_force = fill_missing_values(force.astype(float))
    window_length = compute_window_length(fs, clean_force.size, window_seconds, polyorder)
    baseline = savgol_filter_1d(clean_force, window_length, polyorder, mode="reflect")
    return baseline, window_length


def process_dataset(
    dataset_path: Path,
    output_root: Path,
    window_seconds: float,
    polyorder: int,
    preview_lines: int,
    axis: str,
    distance_range: Tuple[float, float] | None,
) -> List[ReplicateResult]:
    series_list = gather_replicate_series(dataset_path, preview_lines)
    dataset_out = output_root / dataset_path.stem
    ensure_output_dir(dataset_out)

    for stale in dataset_out.glob("*_savgol.npz"):
        try:
            stale.unlink()
        except OSError:
            pass

    results: List[ReplicateResult] = []

    for idx, entry in enumerate(series_list):
        rep_id = entry["replicate_id"]
        time_s = entry["time_s"].astype(float)
        disp_mm = entry["disp_mm"].astype(float)
        force = entry["force_N"].astype(float)

        if distance_range is not None:
            d_min, d_max = distance_range
            mask = (
                np.isfinite(disp_mm)
                & (disp_mm >= d_min)
                & (disp_mm <= d_max)
                & np.isfinite(time_s)
                & np.isfinite(force)
            )
            keep = np.count_nonzero(mask)
            if keep < polyorder + 1:
                print(
                    f"    skip {rep_id}: insufficient samples after distance filter ({keep})"
                )
                continue
            time_s = time_s[mask]
            disp_mm = disp_mm[mask]
            force = force[mask]

        if force.size < polyorder + 1:
            print(f"    skip {rep_id}: too few samples ({force.size}) for polyorder {polyorder}")
            continue
        fs = estimate_fs(time_s, entry.get("fs"), label=rep_id)
        baseline, window_length = savgol_baseline(time_s, force, fs, window_seconds, polyorder)
        residual = force - baseline

        results.append(
            ReplicateResult(
                replicate_id=str(rep_id),
                time_s=time_s,
                disp_mm=disp_mm,
                force=force,
                baseline=baseline,
                residual=residual,
                fs=fs,
                window_length=window_length,
                polyorder=polyorder,
            )
        )

        npz_path = dataset_out / f"{rep_id}_savgol.npz"
        np.savez(
            npz_path,
            time=time_s,
            distance=disp_mm,
            force=force,
            baseline=baseline,
            residual=residual,
            fs=fs,
            window_length=window_length,
            polyorder=polyorder,
        )

    if not results:
        raise RuntimeError(f"no replicates processed for {dataset_path}")

    svg_path = dataset_out / "savgol_detrend.svg"
    svg = render_dataset_svg(dataset_path.name, results, axis=axis)
    svg_path.write_text(svg, encoding="utf-8")

    summary_path = dataset_out / "summary.json"
    with summary_path.open("w", encoding="utf-8") as handle:
        json.dump(
            {
                "dataset": dataset_path.name,
                "window_seconds": window_seconds,
                "polyorder": polyorder,
                "x_axis": axis,
                "distance_range_mm": list(distance_range) if distance_range else None,
                "replicates": [
                    {
                        "replicate_id": r.replicate_id,
                        "fs": r.fs,
                        "window_length": r.window_length,
                        "samples": int(r.force.size),
                    }
                    for r in results
                ],
            },
            handle,
            indent=2,
        )

    return results


def render_dataset_svg(
    dataset_name: str,
    replicates: Sequence[ReplicateResult],
    *,
    axis: str = "time",
) -> str:
    width_px = 1280
    height_px = 960
    margin_left = 90
    margin_right = 220
    margin_top = 70
    margin_bottom = 70
    panel_gap = 40
    panels = [
        ("Original force", [r.force for r in replicates]),
        ("Savitzky–Golay baseline", [r.baseline for r in replicates]),
        ("Detrended residual", [r.residual for r in replicates]),
    ]

    plot_width = width_px - margin_left - margin_right
    total_panel_height = height_px - margin_top - margin_bottom - panel_gap * (len(panels) - 1)
    panel_height = total_panel_height / len(panels)

    if axis == "distance":
        x_label = "Displacement (mm)"
        x_series = [r.disp_mm for r in replicates]
    else:
        x_label = "Time (s)"
        x_series = [r.time_s for r in replicates]

    x_min = min(float(np.nanmin(xs)) for xs in x_series)
    x_max = max(float(np.nanmax(xs)) for xs in x_series)
    if not math.isfinite(x_min) or not math.isfinite(x_max) or x_max <= x_min:
        x_min, x_max = 0.0, 1.0

    def x_to_px(v: float) -> float:
        return margin_left + (v - x_min) * plot_width / (x_max - x_min)

    parts: List[str] = []
    parts.append(
        f"<svg xmlns='http://www.w3.org/2000/svg' width='{width_px}' height='{height_px}' viewBox='0 0 {width_px} {height_px}'>"
    )
    parts.append("<rect x='0' y='0' width='100%' height='100%' fill='white'/>")

    title = f"Savitzky–Golay detrending: {dataset_name}"
    parts.append(
        f"<text x='{width_px/2:.1f}' y='{margin_top/2:.1f}' text-anchor='middle' font-family='sans-serif' font-size='22'>{_escape(title)}</text>"
    )

    # Legend (replicate id -> color) in the right margin
    legend_x = width_px - margin_right + 20
    legend_y = margin_top
    for idx, rep in enumerate(replicates):
        color = COLORS[idx % len(COLORS)]
        parts.append(
            f"<line x1='{legend_x}' y1='{legend_y}' x2='{legend_x+24}' y2='{legend_y}' stroke='{color}' stroke-width='3'/>"
        )
        parts.append(
            f"<text x='{legend_x+30}' y='{legend_y+5}' font-family='sans-serif' font-size='14'>{_escape(rep.replicate_id)}</text>"
        )
        legend_y += 24

    for panel_idx, (label, series_list) in enumerate(panels):
        top = margin_top + panel_idx * (panel_height + panel_gap)
        bottom = top + panel_height
        y_vals = np.concatenate([np.asarray(series, dtype=float) for series in series_list])
        y_min = float(np.min(y_vals))
        y_max = float(np.max(y_vals))
        if not math.isfinite(y_min) or not math.isfinite(y_max):
            y_min, y_max = -1.0, 1.0
        if y_min == y_max:
            y_min -= 1.0
            y_max += 1.0
        padding = 0.05 * (y_max - y_min)
        y_min -= padding
        y_max += padding

        def y_to_px(v: float) -> float:
            return top + (y_max - v) * panel_height / (y_max - y_min)

        # Panel border
        parts.append(
            f"<rect x='{margin_left}' y='{top}' width='{plot_width}' height='{panel_height}' fill='none' stroke='#444' stroke-width='1'/>"
        )
        # Panel label
        parts.append(
            f"<text x='{margin_left - 10}' y='{top - 10}' text-anchor='start' font-family='sans-serif' font-size='16'>{_escape(label)}</text>"
        )

        # Horizontal gridlines and y ticks
        for i in range(6):
            y_val = y_min + (y_max - y_min) * i / 5.0
            py = y_to_px(y_val)
            parts.append(
                f"<line x1='{margin_left}' y1='{py:.2f}' x2='{margin_left + plot_width}' y2='{py:.2f}' stroke='#eee' stroke-width='1'/>"
            )
            parts.append(
                f"<text x='{margin_left - 12}' y='{py + 4:.2f}' text-anchor='end' font-family='monospace' font-size='12'>{y_val:.3g}</text>"
            )

        # Vertical gridlines and x ticks (shared across panels)
        if panel_idx == len(panels) - 1:
            axis_y = bottom
            label_offset = 20
        else:
            axis_y = bottom
            label_offset = 18
        for i in range(6):
            x_val = x_min + (x_max - x_min) * i / 5.0
            px = x_to_px(x_val)
            parts.append(
                f"<line x1='{px:.2f}' y1='{top}' x2='{px:.2f}' y2='{top + panel_height}' stroke='#eee' stroke-width='1'/>"
            )
            parts.append(
                f"<line x1='{px:.2f}' y1='{axis_y}' x2='{px:.2f}' y2='{axis_y + 6}' stroke='#888' stroke-width='1'/>"
            )
            parts.append(
                f"<text x='{px:.2f}' y='{axis_y + label_offset}' text-anchor='middle' font-family='monospace' font-size='12'>{x_val:.2f}</text>"
            )

        # Series polylines
        for idx, series in enumerate(series_list):
            color = COLORS[idx % len(COLORS)]
            x_arr = np.asarray(x_series[idx], dtype=float)
            series_arr = np.asarray(series, dtype=float)
            step = max(1, series_arr.size // 4000)
            pts = []
            for j in range(0, series_arr.size, step):
                px = x_to_px(float(x_arr[j]))
                py = y_to_px(float(series_arr[j]))
                pts.append(f"{px:.2f},{py:.2f}")
            points_attr = " ".join(pts)
            parts.append(
                f"<polyline fill='none' stroke='{color}' stroke-width='1.2' points='{points_attr}'/>"
            )

    # X-axis label
    parts.append(
        f"<text x='{margin_left + plot_width / 2:.1f}' y='{height_px - margin_bottom / 2:.1f}' text-anchor='middle' font-family='sans-serif' font-size='16'>{_escape(x_label)}</text>"
    )

    parts.append("</svg>")
    return "".join(parts)


def _escape(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace("\"", "&quot;")
        .replace("'", "&#39;")
    )


def main(argv: Iterable[str] | None = None) -> int:
    args = parse_args(argv)
    output_root = args.output
    ensure_output_dir(output_root)

    if args.datasets:
        dataset_paths = [DATASET_DIR / name for name in args.datasets]
    else:
        dataset_paths = sorted(DATASET_DIR.glob("*.csv"))
    if not dataset_paths:
        raise SystemExit("no datasets found")

    if args.distance_range is not None:
        distance_range = tuple(float(x) for x in args.distance_range)
    elif args.axis == "distance":
        distance_range = DEFAULT_DISTANCE_RANGE
    else:
        distance_range = None

    for dataset_path in dataset_paths:
        print(f"Processing {dataset_path} ...")
        results = process_dataset(
            dataset_path,
            output_root,
            args.window_seconds,
            args.polyorder,
            args.preview_lines,
            args.axis,
            distance_range,
        )
        print(
            f"  -> {len(results)} replicates | fs ~ {np.mean([r.fs for r in results]):.2f} Hz | "
            f"window ~ {np.mean([r.window_length for r in results]):.0f} samples"
        )

    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
