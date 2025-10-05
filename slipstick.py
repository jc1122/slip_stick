#!/usr/bin/env python3
"""Simple slip–stick spike detection for fixed-format FTM 10 CSV exports."""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Generator, List, Sequence

import numpy as np
from scipy.signal import butter, filtfilt, savgol_filter

try:  # Plotting is optional; only enabled when matplotlib is present.
    import matplotlib.pyplot as plt  # type: ignore
    from matplotlib import rcParams

    _PLOT_STYLE = {
        "figure.figsize": (10, 6),
        "axes.titlesize": 14,
        "axes.labelsize": 12,
        "axes.titleweight": "semibold",
        "font.family": "sans-serif",
        "font.sans-serif": ["DejaVu Sans", "Arial", "Helvetica"],
        "legend.fontsize": 11,
        "xtick.labelsize": 11,
        "ytick.labelsize": 11,
        "lines.linewidth": 1.5,
        "axes.grid": True,
        "grid.alpha": 0.2,
    }

    rcParams.update(_PLOT_STYLE)
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


@dataclass
class NoiseEstimate:
    std_n: float
    dc_offset_n: float
    max_abs_n: float
    sample_count: int
    disp_max_mm: float
    time_span_s: float
    sample_rate_hz: float | None
    noise_peak_hz: float | None
    raw_force: np.ndarray = field(repr=False)
    baseline_force: np.ndarray = field(repr=False)
    residual_force: np.ndarray = field(repr=False)
    time_s: np.ndarray = field(repr=False)
    disp_mm: np.ndarray = field(repr=False)


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

    noise_plot_dir: Path | None = None
    if args.noise_plot_dir:
        if plt is None:
            print("matplotlib is required for plotting; skipping --noise-plot-dir output.", file=sys.stderr)
        else:
            noise_plot_dir = Path(args.noise_plot_dir)
            noise_plot_dir.mkdir(parents=True, exist_ok=True)

    dataset_stem = dataset_path.stem

    collection_width_mm = (
        args.collection_width_mm if args.collection_width_mm and args.collection_width_mm > 0 else 90.0
    )
    report_width_mm = (
        args.report_width_mm if args.report_width_mm and args.report_width_mm > 0 else collection_width_mm
    )
    force_scale = report_width_mm / collection_width_mm if collection_width_mm > 0 else 1.0
    unit_choice = args.report_unit.lower()
    unit_scale = 100.0 if unit_choice == "cn" else 1.0
    unit_symbol = "cN" if unit_choice == "cn" else "N"
    force_unit_label = f"{unit_symbol} / {report_width_mm:g} mm"

    scaled_replicates: list[Replicate] = []
    for replicate in replicates:
        scaled_replicates.append(
            Replicate(
                rep_id=replicate.rep_id,
                time_s=replicate.time_s,
                force_n=replicate.force_n * force_scale,
                disp_mm=replicate.disp_mm,
            )
        )
    replicates = scaled_replicates

    summary: list[tuple[str, int]] = []
    noise_summary: list[tuple[str, NoiseEstimate | None]] = []
    replicate_entries: list[tuple[Replicate, NoiseEstimate | None]] = []

    for replicate in replicates:
        noise_estimate = estimate_instrumental_noise(
            replicate,
            disp_min=args.noise_disp_min,
            disp_max=args.noise_disp_max,
            force_abs_max=args.noise_force_max,
            min_samples=args.noise_min_samples,
            force_onset=args.noise_force_onset,
        )
        noise_summary.append((replicate.rep_id, noise_estimate))
        if noise_plot_dir is not None and plt is not None and noise_estimate is not None:
            noise_out = noise_plot_dir / f"{dataset_stem}_{replicate.rep_id}_noise.png"
            _save_noise_plot(
                noise_out,
                dataset_stem,
                replicate.rep_id,
                noise_estimate,
                force_unit_label=force_unit_label,
                value_scale=unit_scale,
            )
        replicate_entries.append((replicate, noise_estimate))

    common_peak_hz: float | None = None
    if args.instrument_peak_hz is not None and args.instrument_peak_hz > 0:
        common_peak_hz = float(args.instrument_peak_hz)
    else:
        peak_values = [est.noise_peak_hz for _, est in replicate_entries if est and est.noise_peak_hz]
        if peak_values:
            common_peak_hz = float(np.median(peak_values))

    base_cutoff_hz: float | None = None
    if args.instrument_cutoff_hz is not None and args.instrument_cutoff_hz > 0:
        base_cutoff_hz = float(args.instrument_cutoff_hz)
    elif common_peak_hz is not None:
        factor = args.instrument_cutoff_factor
        if factor <= 0:
            factor = 0.8
        base_cutoff_hz = common_peak_hz * factor

    for replicate, noise_estimate in replicate_entries:
        analysis_replicate = replicate
        effective_cutoff: float | None = None

        sample_rate = _estimate_sampling_rate(replicate.time_s)
        if base_cutoff_hz is not None and sample_rate is not None and sample_rate > 0 and replicate.force_n.size >= 8:
            nyquist = 0.5 * float(sample_rate)
            cutoff = min(base_cutoff_hz, nyquist * 0.95)
            if cutoff > 0 and cutoff < nyquist:
                normalized_cutoff = cutoff / nyquist
                try:
                    b, a = butter(4, normalized_cutoff, btype="low", analog=False)
                    padlen = 3 * max(len(a), len(b))
                    if replicate.force_n.size > padlen:
                        filtered_force = filtfilt(b, a, replicate.force_n)
                        analysis_replicate = Replicate(
                            rep_id=replicate.rep_id,
                            time_s=replicate.time_s,
                            force_n=np.asarray(filtered_force, dtype=float),
                            disp_mm=replicate.disp_mm,
                        )
                        effective_cutoff = float(cutoff)
                except ValueError:
                    pass

        result = _analyse_replicate(
            analysis_replicate,
            displacement_window=(args.disp_min, args.disp_max),
            window_seconds=args.window_seconds,
            polyorder=args.polyorder,
            threshold=args.threshold,
        )
        if result is None:
            _print_summary(
                replicate.rep_id,
                0,
                [],
                args.threshold,
                noise_estimate=noise_estimate,
                filter_cutoff_hz=effective_cutoff,
                instrument_peak_hz=common_peak_hz,
                force_unit_label=force_unit_label,
                unit_scale=unit_scale,
            )
            summary.append((replicate.rep_id, 0))
            continue

        _print_summary(
            replicate.rep_id,
            result.time.size,
            result.spikes,
            args.threshold,
            noise_estimate=noise_estimate,
            filter_cutoff_hz=effective_cutoff,
            instrument_peak_hz=common_peak_hz,
            force_unit_label=force_unit_label,
            unit_scale=unit_scale,
        )
        summary.append((replicate.rep_id, len(result.spikes)))

        if plot_dir is not None and plt is not None:
            out_path = plot_dir / f"{dataset_stem}_{replicate.rep_id}.png"
            _save_plot(
                out_path,
                dataset_stem,
                replicate.rep_id,
                result,
                args.threshold,
                force_unit_label=force_unit_label,
                value_scale=unit_scale,
            )

    _print_noise_totals(
        dataset_stem,
        noise_summary,
        force_unit_label=force_unit_label,
        unit_scale=unit_scale,
        common_peak_hz=common_peak_hz,
        common_cutoff_hz=base_cutoff_hz,
    )
    if noise_plot_dir is not None and plt is not None:
        summary_out = noise_plot_dir / f"{dataset_stem}_noise_summary.png"
        _save_noise_summary_plot(
            summary_out,
            dataset_stem,
            noise_summary,
            force_unit_label=force_unit_label,
            value_scale=unit_scale,
        )
    _print_summary_totals(dataset_stem, summary)

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
    parser.add_argument(
        "--threshold",
        type=float,
        default=0.014,
        help="Residual spike threshold in force units (defaults to 0.014 in the chosen reporting scale).",
    )
    parser.add_argument(
        "--plot-dir",
        help=(
            "Optional directory for PNG plots with spikes marked. "
            "Requires matplotlib; files are named <dataset>_<replicate>.png."
        ),
    )
    parser.add_argument(
        "--noise-plot-dir",
        help=(
            "Optional directory for plots of the inferred instrumental noise. "
            "Requires matplotlib; files are named <dataset>_<replicate>_noise.png."
        ),
    )
    parser.add_argument(
        "--noise-disp-min",
        type=float,
        default=1.0,
        help="Lower displacement bound (mm) for the noise window (defaults to 1 mm).",
    )
    parser.add_argument(
        "--noise-disp-max",
        type=float,
        default=5.0,
        help="Upper displacement bound (mm) for the instrumental noise window (defaults to 5 mm).",
    )
    parser.add_argument(
        "--noise-force-max",
        type=float,
        default=None,
        help="Optional absolute force bound (N) to keep noise samples; omit to skip force filtering.",
    )
    parser.add_argument(
        "--noise-min-samples",
        type=int,
        default=40,
        help="Minimum number of points to use for noise estimation (falls back to earliest samples).",
    )
    parser.add_argument(
        "--noise-force-onset",
        type=float,
        default=0.2,
        help=(
            "Absolute force (N) that marks the onset of specimen engagement. The noise window excludes "
            "samples at or above this force."
        ),
    )
    parser.add_argument(
        "--instrument-peak-hz",
        type=float,
        default=None,
        help=(
            "Optional global instrumental noise peak (Hz). When provided, overrides replicate-level peak"
            " detection."
        ),
    )
    parser.add_argument(
        "--instrument-cutoff-hz",
        type=float,
        default=None,
        help=(
            "Optional global low-pass cutoff (Hz) applied to every replicate before spike analysis."
        ),
    )
    parser.add_argument(
        "--instrument-cutoff-factor",
        type=float,
        default=0.8,
        help=(
            "Scaling factor applied to the common noise peak when deriving the low-pass cutoff (default 0.8)."
        ),
    )
    parser.add_argument(
        "--collection-width-mm",
        type=float,
        default=90.0,
        help=(
            "Sample width in millimetres. Forces from the CSV are assumed to be normalised to 90 mm; "
            "the script rescales them linearly to this width for reporting and plotting."
        ),
    )
    parser.add_argument(
        "--report-width-mm",
        type=float,
        default=25.0,
        help=(
            "Reporting width in millimetres. Forces are normalised to this width for summaries and plots."
        ),
    )
    parser.add_argument(
        "--report-unit",
        choices=["N", "cN"],
        default="cN",
        help="Unit to use when reporting forces. Choose 'cN' to scale values by 100 for readability.",
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
# Instrumental noise helpers
# ---------------------------------------------------------------------------


def estimate_instrumental_noise(
    replicate: Replicate,
    *,
    disp_min: float,
    disp_max: float,
    force_abs_max: float | None,
    min_samples: int,
    force_onset: float | None,
) -> NoiseEstimate | None:
    if replicate.force_n.size == 0:
        return None

    disp_limit_min = max(disp_min, 0.0)
    disp_limit_max = max(disp_max, disp_limit_min)
    if min_samples <= 0:
        min_samples = 1

    noise_mask = (replicate.disp_mm >= disp_limit_min) & (replicate.disp_mm <= disp_limit_max)
    if force_abs_max is not None and force_abs_max > 0:
        noise_mask &= np.abs(replicate.force_n) <= force_abs_max

    indices = np.nonzero(noise_mask)[0]
    target_count = min(min_samples, replicate.force_n.size)
    if indices.size == 0:
        fallback_candidates = np.where(
            (replicate.disp_mm >= disp_limit_min) & (replicate.disp_mm <= disp_limit_max)
        )[0]
        indices = fallback_candidates[:target_count]

    indices = indices[indices < replicate.force_n.size]
    if indices.size == 0:
        return None

    indices.sort()

    if indices.size == 0:
        return None

    force_segment = replicate.force_n[indices]
    if force_onset is not None and force_onset > 0:
        onset_mask = np.abs(force_segment) >= force_onset
        if np.any(onset_mask):
            first_contact_rel = int(np.where(onset_mask)[0][0])
            indices = indices[:first_contact_rel]
            force_segment = replicate.force_n[indices]

    if indices.size == 0:
        return None

    time_segment = replicate.time_s[indices]
    disp_segment = replicate.disp_mm[indices]

    disp_span = float(np.max(disp_segment) - np.min(disp_segment)) if disp_segment.size else 0.0
    if disp_span <= 0.0:
        disp_span = max(float(disp_limit_max - disp_limit_min), 1.0)

    polyorder = 2
    baseline_force = np.full_like(force_segment, float(np.mean(force_segment)))
    residual_force = force_segment - baseline_force

    if force_segment.size >= 5:
        delta_disp = np.diff(disp_segment)
        step = np.median(np.abs(delta_disp[delta_disp != 0])) if delta_disp.size else 0.0
        if step <= 0.0:
            step = disp_span / max(force_segment.size - 1, 1)
        # Use a long SavGol window (≈ 50% of the displacement span) to better remove slow ramps.
        window_disp = max(disp_span * 0.5, step)
        window_samples = int(round(window_disp / step)) if step > 0 else force_segment.size
        window_samples = max(window_samples, polyorder + 1, 3)
        if window_samples % 2 == 0:
            window_samples += 1
        if window_samples > force_segment.size:
            window_samples = force_segment.size if force_segment.size % 2 == 1 else force_segment.size - 1
        if window_samples > polyorder and window_samples >= 3:
            try:
                baseline_force = savgol_filter(
                    force_segment,
                    window_length=window_samples,
                    polyorder=polyorder,
                    mode="interp",
                )
                residual_force = force_segment - baseline_force
            except ValueError:
                pass

    offset = float(np.mean(baseline_force))
    std = float(np.std(residual_force, ddof=1)) if residual_force.size > 1 else 0.0
    max_abs = float(np.max(np.abs(residual_force))) if residual_force.size else 0.0
    disp_max_used = float(np.max(disp_segment)) if disp_segment.size else 0.0
    time_span = (
        float(np.max(time_segment) - np.min(time_segment))
        if time_segment.size > 1
        else 0.0
    )

    sample_rate = _estimate_sampling_rate(time_segment)
    noise_peak_hz: float | None = None
    if sample_rate is not None and residual_force.size >= 8:
        centered = residual_force - np.mean(residual_force)
        spectrum = np.fft.rfft(centered)
        freqs = np.fft.rfftfreq(centered.size, d=1.0 / sample_rate)
        if spectrum.size > 1:
            power = np.abs(spectrum)
            power[0] = 0.0  # ignore DC
            peak_index = int(np.argmax(power)) if np.any(power) else 0
            if peak_index > 0 and peak_index < freqs.size:
                noise_peak_hz = float(freqs[peak_index])

    return NoiseEstimate(
        std_n=std,
        dc_offset_n=offset,
        max_abs_n=max_abs,
        sample_count=int(force_segment.size),
        disp_max_mm=disp_max_used,
        time_span_s=time_span,
        sample_rate_hz=float(sample_rate) if sample_rate is not None else None,
        noise_peak_hz=noise_peak_hz,
        raw_force=np.asarray(force_segment, dtype=float),
        baseline_force=np.asarray(baseline_force, dtype=float),
        residual_force=np.asarray(residual_force, dtype=float),
        time_s=np.asarray(time_segment, dtype=float),
        disp_mm=np.asarray(disp_segment, dtype=float),
    )


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


def _print_summary(
    rep_id: str,
    sample_count: int,
    spikes: List[Spike],
    threshold: float,
    *,
    noise_estimate: NoiseEstimate | None,
    filter_cutoff_hz: float | None,
    instrument_peak_hz: float | None,
    force_unit_label: str,
    unit_scale: float,
) -> None:
    print(f"Replicate {rep_id}")
    display_threshold = threshold * unit_scale
    header_bits = [f"samples={sample_count}", f"threshold={display_threshold:.3f} {force_unit_label}"]
    print("  " + " | ".join(header_bits))
    if noise_estimate is not None:
        peak_fragment = (
            f" | peak≈{noise_estimate.noise_peak_hz:.2f} Hz" if noise_estimate.noise_peak_hz is not None else ""
        )
        std_display = noise_estimate.std_n * unit_scale
        bias_display = noise_estimate.dc_offset_n * unit_scale
        max_display = noise_estimate.max_abs_n * unit_scale
        line = (
            f"  noise: std={std_display:.5f} {force_unit_label} | "
            f"bias={bias_display:.5f} {force_unit_label} | "
            f"max_abs={max_display:.5f} {force_unit_label} | "
            f"n={noise_estimate.sample_count} | disp≤{noise_estimate.disp_max_mm:.3f} mm | span={noise_estimate.time_span_s:.3f} s"
        )
        print(line + peak_fragment)
    if filter_cutoff_hz is not None:
        if instrument_peak_hz is not None:
            print(
                f"  denoised: low-pass filter fc={filter_cutoff_hz:.2f} Hz (instrument peak ≈ {instrument_peak_hz:.2f} Hz)"
            )
        else:
            print(f"  denoised: low-pass filter fc={filter_cutoff_hz:.2f} Hz")
    elif instrument_peak_hz is not None:
        print(f"  instrument peak ≈ {instrument_peak_hz:.2f} Hz (filter not applied)")
    if not spikes:
        print("  No spikes above threshold in the selected displacement window.\n")
        return
    for spike in spikes:
        residual_display = spike.residual_n * unit_scale
        print(
            f"  time={spike.time_s:.3f} s | disp={spike.disp_mm:.3f} mm | "
            f"residual={residual_display:.4f} {force_unit_label} (idx {spike.index})"
        )
    print()


def _save_plot(
    out_path: Path,
    dataset_stem: str,
    rep_id: str,
    result: DetectionResult,
    threshold: float,
    *,
    force_unit_label: str,
    value_scale: float,
) -> None:
    assert plt is not None  # plotting gated by caller

    spike_indices = [sp.index for sp in result.spikes]
    spike_disp = result.disp[spike_indices] if spike_indices else np.array([])

    fig, (ax_force, ax_residual) = plt.subplots(2, 1, sharex=True, figsize=(10, 6))

    force_series = result.force * value_scale
    baseline_series = result.baseline * value_scale
    residual_series = result.residual * value_scale
    threshold_display = threshold * value_scale

    ax_force.plot(result.disp, force_series, label="filtered force", color="#1f77b4")
    ax_force.plot(
        result.disp,
        baseline_series,
        label="baseline",
        color="#ff7f0e",
        linestyle="--",
    )
    if spike_indices:
        ax_force.scatter(spike_disp, force_series[spike_indices], color="#d62728", marker="x", label="spikes")
    ax_force.set_ylabel(f"Force ({force_unit_label})")
    ax_force.set_title("Force vs displacement")
    ax_force.legend(loc="upper left")

    ax_residual.plot(result.disp, residual_series, color="#9467bd", label="residual")
    ax_residual.axhline(threshold_display, color="0.3", linestyle="--", linewidth=1.0, label="threshold")
    ax_residual.axhline(-threshold_display, color="0.3", linestyle="--", linewidth=1.0)
    if spike_indices:
        ax_residual.scatter(spike_disp, residual_series[spike_indices], color="#d62728", marker="x")
    ax_residual.set_xlabel("Displacement (mm)")
    ax_residual.set_ylabel(f"Residual ({force_unit_label})")
    ax_residual.legend(loc="upper left")

    fig.suptitle(f"{dataset_stem} – replicate {rep_id}", fontsize=15, fontweight="semibold")
    fig.tight_layout(rect=[0, 0, 1, 0.97])
    fig.savefig(out_path, dpi=150)
    plt.close(fig)


def _save_noise_plot(
    out_path: Path,
    dataset_stem: str,
    rep_id: str,
    noise: NoiseEstimate,
    *,
    force_unit_label: str,
    value_scale: float,
) -> None:
    assert plt is not None

    fig = plt.figure(figsize=(9, 8))
    gs = fig.add_gridspec(3, 1, height_ratios=[2, 1, 1])

    raw_series = noise.raw_force * value_scale
    baseline_series = noise.baseline_force * value_scale
    residual_series = noise.residual_force * value_scale

    ax_series = fig.add_subplot(gs[0])
    ax_series.plot(noise.disp_mm, raw_series, label="raw force", color="#1f77b4")
    ax_series.plot(
        noise.disp_mm,
        baseline_series,
        label="Savgol baseline",
        color="#ff7f0e",
        linestyle="--",
    )
    ax_series.axhline(0.0, color="0.3", linestyle="--", linewidth=1.0)
    ax_series.set_ylabel(f"Force ({force_unit_label})")
    ax_series.set_xlabel("Displacement (mm)")
    ax_series.set_title(f"Replicate {rep_id} noise window")
    ax_series.legend(loc="upper right")

    ax_residual = fig.add_subplot(gs[1], sharex=ax_series)
    ax_residual.plot(noise.disp_mm, residual_series, color="#9467bd", label="residual")
    ax_residual.axhline(0.0, color="0.3", linestyle="--", linewidth=1.0)
    ax_residual.set_ylabel(f"Residual ({force_unit_label})")
    ax_residual.set_xlabel("Displacement (mm)")
    ax_residual.set_title("Detrended force")

    ax_hist = fig.add_subplot(gs[2])
    bins = min(60, max(10, int(np.sqrt(max(residual_series.size, 1)))))
    ax_hist.hist(residual_series, bins=bins, color="#d62728", alpha=0.75)
    ax_hist.axvline(0.0, color="0.3", linestyle="--", linewidth=1.0)
    ax_hist.set_xlabel(f"Residual force ({force_unit_label})")
    ax_hist.set_ylabel("Count")
    if noise.noise_peak_hz is not None:
        ax_hist.set_title(
            f"std={noise.std_n * value_scale:.5f} {force_unit_label} | max |noise|={noise.max_abs_n * value_scale:.5f} {force_unit_label} | peak≈{noise.noise_peak_hz:.2f} Hz"
        )
    else:
        ax_hist.set_title(
            f"std={noise.std_n * value_scale:.5f} {force_unit_label} | max |noise|={noise.max_abs_n * value_scale:.5f} {force_unit_label}"
        )

    fig.suptitle(dataset_stem, y=0.98, fontsize=12)
    fig.tight_layout(rect=[0, 0, 1, 0.96])
    fig.savefig(out_path, dpi=150)
    plt.close(fig)


def _save_noise_summary_plot(
    out_path: Path,
    dataset_stem: str,
    noise_entries: list[tuple[str, NoiseEstimate | None]],
    *,
    force_unit_label: str,
    value_scale: float,
) -> None:
    assert plt is not None

    available = [(rep_id, est) for rep_id, est in noise_entries if est is not None]
    if not available:
        return

    rep_ids = [rep_id for rep_id, _ in available]
    biases = np.array([est.dc_offset_n for _, est in available], dtype=float) * value_scale
    stds = np.array([est.std_n for _, est in available], dtype=float) * value_scale
    max_abs = np.array([est.max_abs_n for _, est in available], dtype=float) * value_scale

    width = max(8.0, len(rep_ids) * 0.7)
    fig, (ax_bias, ax_std) = plt.subplots(2, 1, figsize=(width, 6), sharex=True)

    x = np.arange(len(rep_ids))

    ax_bias.bar(x, biases, color="#1f77b4")
    ax_bias.axhline(0.0, color="0.3", linestyle="--", linewidth=1.0)
    ax_bias.set_ylabel(f"Bias ({force_unit_label})")
    ax_bias.set_title(f"Instrument bias per replicate – {dataset_stem}")

    ax_std.bar(x, stds, color="#ff7f0e", label="std dev")
    ax_std.scatter(x, max_abs, color="#d62728", marker="x", label="max |noise|")
    ax_std.set_ylabel(f"Noise ({force_unit_label})")
    ax_std.set_title("Noise spread and extrema")
    ax_std.legend(loc="upper right")
    ax_std.set_xticks(x)
    ax_std.set_xticklabels(rep_ids, rotation=45, ha="right")

    fig.suptitle(dataset_stem, fontsize=15, fontweight="semibold")
    fig.tight_layout(rect=[0, 0, 1, 0.97])
    fig.savefig(out_path, dpi=150)
    plt.close(fig)


def _print_noise_totals(
    dataset_stem: str,
    noise_entries: list[tuple[str, NoiseEstimate | None]],
    *,
    force_unit_label: str,
    unit_scale: float,
    common_peak_hz: float | None,
    common_cutoff_hz: float | None,
) -> None:
    print(f"Noise estimates for {dataset_stem}")
    available = [(rep_id, est) for rep_id, est in noise_entries if est is not None]
    if not available:
        print("  No noise window samples found.\n")
        return

    stds = np.array([est.std_n for _, est in available], dtype=float) * unit_scale
    biases = np.array([est.dc_offset_n for _, est in available], dtype=float) * unit_scale
    max_abs = np.array([est.max_abs_n for _, est in available], dtype=float) * unit_scale
    disp_limits = np.array([est.disp_max_mm for _, est in available], dtype=float)
    sample_total = int(sum(est.sample_count for _, est in available))

    print(
        "  replicates={} | median std={:.5f} {unit} | mean std={:.5f} {unit} | max abs noise={:.5f} {unit}".format(
            len(available),
            float(np.median(stds)),
            float(np.mean(stds)),
            float(np.max(max_abs)),
            unit=force_unit_label,
        )
    )
    print(
        "  bias median={:.5f} {unit} | bias range=({:.5f}, {:.5f}) {unit}".format(
            float(np.median(biases)),
            float(np.min(biases)),
            float(np.max(biases)),
            unit=force_unit_label,
        )
    )
    print(
        "  total noise samples={} | max disp used={:.3f} mm".format(
            sample_total,
            float(np.max(disp_limits)),
        )
    )
    if common_peak_hz is not None:
        second_line = f"  instrument peak≈{common_peak_hz:.2f} Hz"
        if common_cutoff_hz is not None:
            second_line += f" | applied cutoff≈{common_cutoff_hz:.2f} Hz"
        print(second_line)
    print()


def _print_summary_totals(dataset_stem: str, summary: list[tuple[str, int]]) -> None:
    print(f"Summary for {dataset_stem}")
    if not summary:
        print("  No replicates processed.\n")
        return
    total = 0
    for rep_id, count in summary:
        total += count
        plural = "spikes" if count != 1 else "spike"
        print(f"  {rep_id}: {count} {plural}")
    plural_total = "spikes" if total != 1 else "spike"
    print(f"  Total: {total} {plural_total}\n")


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    raise SystemExit(main())
