#!/usr/bin/env python3
"""Simple slip–stick spike detection for fixed-format FTM 10 CSV exports."""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Generator, List, Sequence

import numpy as np
from scipy.signal import savgol_filter

try:  # Plotting is optional; only enabled when matplotlib is present.
    import matplotlib.pyplot as plt  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    plt = None


@dataclass
class Replicate:
    rep_id: str
    time_s: np.ndarray
    force_n: np.ndarray
    disp_mm: np.ndarray


@dataclass
class Spike:
    index: int
    time_s: float
    disp_mm: float
    residual_n: float


@dataclass
class DetectionResult:
    time: np.ndarray
    disp: np.ndarray
    force: np.ndarray
    baseline: np.ndarray
    residual: np.ndarray
    spikes: List[Spike]


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)

    dataset_path = Path(args.input)
    replicates = load_replicates(dataset_path)
    if not replicates:
        print("No replicates found in the file.")
        return 1

    plot_dir: Path | None = None
    if args.plot_dir:
        if plt is None:
            print("matplotlib is required for plotting; skipping --plot-dir output.", file=sys.stderr)
        else:
            plot_dir = Path(args.plot_dir)
            plot_dir.mkdir(parents=True, exist_ok=True)

    dataset_stem = dataset_path.stem

    for replicate in replicates:
        result = _analyse_replicate(
            replicate,
            displacement_window=(args.disp_min, args.disp_max),
            window_seconds=args.window_seconds,
            polyorder=args.polyorder,
            threshold=args.threshold,
        )
        if result is None:
            _print_summary(replicate.rep_id, 0, [], args.threshold)
            continue

        _print_summary(replicate.rep_id, result.time.size, result.spikes, args.threshold)

        if plot_dir is not None and plt is not None:
            out_path = plot_dir / f"{dataset_stem}_{replicate.rep_id}.png"
            _save_plot(out_path, replicate.rep_id, result, args.threshold)

    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Detect |force-baseline| spikes above a threshold in the 50–200 mm window.",
    )
    parser.add_argument("--input", "-i", required=True, help="Path to the CSV file to analyse.")
    parser.add_argument("--disp-min", type=float, default=50.0, help="Lower displacement bound (mm).")
    parser.add_argument("--disp-max", type=float, default=200.0, help="Upper displacement bound (mm).")
    parser.add_argument(
        "--window-seconds",
        type=float,
        default=None,
        help=(
            "Savitzky–Golay window duration in seconds (converted to nearest odd number of samples). "
            "Defaults to a long window equal to 50% of the trimmed trace duration (minimum 4 s)."
        ),
    )
    parser.add_argument("--polyorder", type=int, default=3, help="Savitzky–Golay polynomial order.")
    parser.add_argument("--threshold", type=float, default=0.05, help="Residual spike threshold (newtons).")
    parser.add_argument(
        "--plot-dir",
        help=(
            "Optional directory for PNG plots with spikes marked. "
            "Requires matplotlib; files are named <dataset>_<replicate>.png."
        ),
    )
    return parser


# ---------------------------------------------------------------------------
# CSV loading helpers
# ---------------------------------------------------------------------------


def load_replicates(path: str | Path, *, encoding: str = "cp1250") -> List[Replicate]:
    rows = list(_iter_csv_rows(Path(path), encoding=encoding))
    if len(rows) < 3:
        return []

    labels_row, names_row, units_row = _pad_rows(rows[:3])
    data_rows = rows[3:]

    n_cols = len(names_row)
    n_cols -= n_cols % 3  # enforce full triples

    replicates: List[Replicate] = []
    current_label = ""

    for offset in range(0, n_cols, 3):
        raw_label = labels_row[offset].strip()
        if raw_label:
            current_label = raw_label
        if not current_label:
            current_label = f"rep_{len(replicates) + 1}"

        name_triplet = [names_row[offset + i].strip() for i in range(3)]
        unit_triplet = [units_row[offset + i].strip() for i in range(3)]
        if not _looks_like_replicate(name_triplet, unit_triplet):
            continue

        time_vals: List[float] = []
        force_vals: List[float] = []
        disp_vals: List[float] = []

        for row in data_rows:
            if len(row) <= offset + 2:
                continue
            t = _parse_float(row[offset])
            f = _parse_float(row[offset + 1])
            d = _parse_float(row[offset + 2])
            if t is None or f is None or d is None:
                continue
            time_vals.append(t)
            force_vals.append(f)
            disp_vals.append(d)

        if not time_vals:
            continue

        replicates.append(
            Replicate(
                rep_id=_normalise_label(current_label, len(replicates) + 1),
                time_s=np.asarray(time_vals, dtype=float),
                force_n=np.asarray(force_vals, dtype=float),
                disp_mm=np.asarray(disp_vals, dtype=float),
            )
        )

    return replicates


def _iter_csv_rows(path: Path, *, encoding: str) -> Generator[List[str], None, None]:
    with path.open("r", encoding=encoding) as handle:
        for raw_line in handle:
            line = raw_line.rstrip("\r\n")
            if not line:
                continue
            cells = _split_csv_line(line)
            yield [cell.strip() for cell in cells]


def _split_csv_line(line: str) -> List[str]:
    def _parse(text: str) -> List[str]:
        cells: List[str] = []
        field: List[str] = []
        in_quotes = False
        i = 0
        length = len(text)
        while i < length:
            ch = text[i]
            if ch == '"':
                if in_quotes and i + 1 < length and text[i + 1] == '"':
                    field.append('"')
                    i += 1
                else:
                    in_quotes = not in_quotes
            elif ch == ',' and not in_quotes:
                prev_ch = text[i - 1] if i > 0 else ''
                next_ch = text[i + 1] if i + 1 < length else ''
                if prev_ch.isdigit() and next_ch.isdigit():
                    field.append(ch)
                else:
                    cells.append("".join(field))
                    field = []
            else:
                field.append(ch)
            i += 1
        cells.append("".join(field))
        return cells

    primary = _parse(line)
    if len(primary) == 1:
        alt = line
        if alt.startswith('"') and alt.endswith('"') and len(alt) > 1:
            alt = alt[1:-1]
        alt = alt.replace('""', '"')
        secondary = _parse(alt)
        if len(secondary) > 1:
            return secondary
    return primary


def _pad_rows(rows: Sequence[Sequence[str]]) -> List[List[str]]:
    max_len = max(len(row) for row in rows)
    return [list(row) + [""] * (max_len - len(row)) for row in rows]


def _looks_like_replicate(names: List[str], units: List[str]) -> bool:
    if len(names) != 3 or len(units) != 3:
        return False
    expected_names = ["czas", "si", "przemieszczenie"]
    expected_units = ["s", "n", "mm"]
    for name, unit, exp_name, exp_unit in zip(names, units, expected_names, expected_units):
        if exp_unit.lower() not in unit.lower():
            return False
        if exp_name not in _ASCII_fold(name):
            return False
    return True


def _ASCII_fold(text: str) -> str:
    return (
        text.lower()
        .replace("ł", "l")
        .replace("ś", "s")
        .replace("ą", "a")
        .replace("ć", "c")
        .replace("ę", "e")
        .replace("ń", "n")
        .replace("ó", "o")
        .replace("ż", "z")
        .replace("ź", "z")
    )


def _normalise_label(raw: str, fallback_index: int) -> str:
    cleaned = re.sub(r"[^0-9a-zA-Z]+", "_", raw.strip())
    cleaned = cleaned.strip("_")
    return cleaned or f"rep_{fallback_index}"


def _parse_float(text: str) -> float | None:
    value = text.strip()
    if not value:
        return None
    value = value.replace(" ", "")
    value = value.replace(",", ".")
    try:
        return float(value)
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# Spike detection helpers
# ---------------------------------------------------------------------------


def detect_spikes(
    replicate: Replicate,
    *,
    displacement_window: tuple[float, float],
    window_seconds: float | None = None,
    polyorder: int,
    threshold: float,
) -> List[Spike]:
    result = _analyse_replicate(
        replicate,
        displacement_window=displacement_window,
        window_seconds=window_seconds,
        polyorder=polyorder,
        threshold=threshold,
    )
    return [] if result is None else result.spikes


def _analyse_replicate(
    replicate: Replicate,
    *,
    displacement_window: tuple[float, float],
    window_seconds: float | None,
    polyorder: int,
    threshold: float,
) -> DetectionResult | None:
    disp_min, disp_max = displacement_window
    mask = (replicate.disp_mm >= disp_min) & (replicate.disp_mm <= disp_max)
    if not np.any(mask):
        return None

    time = replicate.time_s[mask]
    force = replicate.force_n[mask]
    disp = replicate.disp_mm[mask]

    if time.size < polyorder + 2:
        return None

    fs = _estimate_sampling_rate(time)
    if fs is None or fs <= 0:
        return None

    trace_duration = float(time[-1] - time[0]) if time.size > 1 else 0.0
    if window_seconds is None or window_seconds <= 0:
        long_window_seconds = max(trace_duration * 0.50, 4.0)
    else:
        long_window_seconds = window_seconds

    window_length = _window_length_from_seconds(long_window_seconds, fs)
    if window_length <= polyorder:
        window_length = polyorder + 1
    if window_length % 2 == 0:
        window_length += 1
    if window_length > force.size:
        window_length = force.size if force.size % 2 == 1 else max(force.size - 1, 1)
    if window_length <= polyorder or window_length < 3:
        return None

    baseline = _savgol(force, window_length=window_length, polyorder=polyorder)
    residual = force - baseline

    spikes = _find_spikes(time, disp, residual, threshold)

    return DetectionResult(
        time=time,
        disp=disp,
        force=force,
        baseline=baseline,
        residual=residual,
        spikes=spikes,
    )


def _find_spikes(
    time: np.ndarray,
    disp: np.ndarray,
    residual: np.ndarray,
    threshold: float,
) -> List[Spike]:
    indices = np.where(np.abs(residual) > threshold)[0]
    if indices.size == 0:
        return []

    groups = np.split(indices, np.where(np.diff(indices) > 1)[0] + 1)
    spikes: List[Spike] = []
    for group in groups:
        if group.size == 0:
            continue
        peak_idx = group[np.argmax(np.abs(residual[group]))]
        spikes.append(
            Spike(
                index=int(peak_idx),
                time_s=float(time[peak_idx]),
                disp_mm=float(disp[peak_idx]),
                residual_n=float(residual[peak_idx]),
            )
        )
    return spikes


def _estimate_sampling_rate(time: np.ndarray) -> float | None:
    diffs = np.diff(time)
    diffs = diffs[diffs > 0]
    if diffs.size == 0:
        return None
    return float(1.0 / np.median(diffs))


def _window_length_from_seconds(window_seconds: float, fs: float) -> int:
    samples = max(int(round(window_seconds * fs)), 1)
    if samples % 2 == 0:
        samples += 1
    return max(samples, 3)


def _savgol(y: np.ndarray, *, window_length: int, polyorder: int) -> np.ndarray:
    return savgol_filter(y, window_length=window_length, polyorder=polyorder, mode="mirror")


# ---------------------------------------------------------------------------
# Output helpers
# ---------------------------------------------------------------------------


def _print_summary(rep_id: str, sample_count: int, spikes: List[Spike], threshold: float) -> None:
    print(f"Replicate {rep_id}")
    print(f"  samples={sample_count} threshold={threshold:.3f} N")
    if not spikes:
        print("  No spikes above threshold in the selected displacement window.\n")
        return
    for spike in spikes:
        print(
            "  time={:.3f} s | disp={:.3f} mm | residual={:.4f} N (idx {})".format(
                spike.time_s,
                spike.disp_mm,
                spike.residual_n,
                spike.index,
            )
        )
    print()


def _save_plot(out_path: Path, rep_id: str, result: DetectionResult, threshold: float) -> None:
    assert plt is not None  # plotting gated by caller

    spike_indices = [sp.index for sp in result.spikes]
    spike_disp = result.disp[spike_indices] if spike_indices else np.array([])

    fig, (ax_force, ax_residual) = plt.subplots(2, 1, sharex=True, figsize=(10, 6))

    ax_force.plot(result.disp, result.force, label="force", color="tab:blue", linewidth=1.1)
    ax_force.plot(
        result.disp,
        result.baseline,
        label="baseline",
        color="tab:orange",
        linestyle="--",
        linewidth=1.0,
    )
    if spike_indices:
        ax_force.scatter(spike_disp, result.force[spike_indices], color="tab:red", marker="x", label="spikes")
    ax_force.set_ylabel("Force (N)")
    ax_force.set_title(f"Replicate {rep_id}")
    ax_force.legend(loc="upper left")

    ax_residual.plot(result.disp, result.residual, color="tab:red", label="residual", linewidth=1.0)
    ax_residual.axhline(threshold, color="tab:gray", linestyle="--", linewidth=0.8, label="±threshold")
    ax_residual.axhline(-threshold, color="tab:gray", linestyle="--", linewidth=0.8)
    if spike_indices:
        ax_residual.scatter(spike_disp, result.residual[spike_indices], color="tab:red", marker="x")
    ax_residual.set_xlabel("Displacement (mm)")
    ax_residual.set_ylabel("Residual (N)")
    ax_residual.legend(loc="upper left")

    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    raise SystemExit(main())
