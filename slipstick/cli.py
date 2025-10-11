from __future__ import annotations

import argparse
import locale
import sys
from dataclasses import replace
from pathlib import Path
from typing import Any, Sequence

import numpy as np
from scipy.signal import butter, filtfilt

from .core import _analyse_replicate, _estimate_sampling_rate, estimate_instrumental_noise
from .io import load_replicates
from .models import NoiseEstimate, Replicate, Spike
from .plotting import _render_plot_jobs, _save_noise_plot, _save_noise_summary_plot, _save_plot

# Configure numeric locale to support comma decimals when available.
try:
    locale.setlocale(locale.LC_NUMERIC, "")
except locale.Error:
    pass

# Defaults expressed in Newtons at the original collection width (before scaling).
# 0.0504 N scales to 1.4 cN when reported at 25 mm by default.
DEFAULT_THRESHOLD_FORCE_N = 0.0504
DEFAULT_NOISE_FORCE_ONSET_N = 0.2


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
        try:
            import matplotlib.pyplot as plt
        except ImportError:
            print(
                "matplotlib is required for plotting; skipping --plot-dir output.",
                file=sys.stderr,
            )
        else:
            plot_dir = Path(args.plot_dir)
            plot_dir.mkdir(parents=True, exist_ok=True)

    noise_plot_dir: Path | None = None
    if args.noise_plot_dir:
        try:
            import matplotlib.pyplot as plt
        except ImportError:
            print(
                "matplotlib is required for plotting; skipping --noise-plot-dir output.",
                file=sys.stderr,
            )
        else:
            noise_plot_dir = Path(args.noise_plot_dir)
            noise_plot_dir.mkdir(parents=True, exist_ok=True)

    dataset_stem = dataset_path.stem

    plot_workers = 4
    try:
        plot_workers = int(args.plot_workers)
    except (TypeError, ValueError):
        plot_workers = 4
    if plot_workers <= 0:
        plot_workers = 4
    plot_format = str(args.plot_format).lower()
    plot_suffix = plot_format

    collection_width_mm = (
        args.collection_width_mm
        if args.collection_width_mm and args.collection_width_mm > 0
        else 90.0
    )
    report_width_mm = (
        args.report_width_mm
        if args.report_width_mm and args.report_width_mm > 0
        else collection_width_mm
    )
    force_scale = (
        report_width_mm / collection_width_mm if collection_width_mm > 0 else 1.0
    )
    unit_choice = args.report_unit.lower()
    unit_scale = 100.0 if unit_choice == "cn" else 1.0
    unit_symbol = "cN" if unit_choice == "cn" else "N"
    force_unit_label = f"{unit_symbol} / {report_width_mm:g} mm"

    def _resolve_force_argument(
        value: float | None, *, default_n: float | None
    ) -> float | None:
        """Convert CLI force values to the scaled analysis units."""

        base_value = default_n if value is None else value / unit_scale
        if base_value is None:
            return None
        return base_value * force_scale

    threshold_value = _resolve_force_argument(
        args.threshold, default_n=DEFAULT_THRESHOLD_FORCE_N
    )
    if threshold_value is None:
        raise ValueError("threshold resolution produced None")

    noise_force_max = _resolve_force_argument(
        args.noise_force_max, default_n=None
    )
    noise_force_onset = _resolve_force_argument(
        args.noise_force_onset, default_n=DEFAULT_NOISE_FORCE_ONSET_N
    )

    if force_scale != 1.0:
        for replicate in replicates:
            replicate.force_n *= force_scale

    retain_noise_segments = noise_plot_dir is not None

    summary: list[tuple[str, int]] = []
    noise_summary: list[tuple[str, NoiseEstimate | None]] = []
    replicate_entries: list[tuple[Replicate, NoiseEstimate | None]] = []
    plot_jobs: list[tuple[str, tuple[Any, ...]]] = []

    for replicate in replicates:
        noise_estimate = estimate_instrumental_noise(
            replicate,
            disp_min=args.noise_disp_min,
            disp_max=args.noise_disp_max,
            force_abs_max=noise_force_max,
            min_samples=args.noise_min_samples,
            force_onset=noise_force_onset,
            retain_segments=retain_noise_segments,
        )
        noise_summary.append((replicate.rep_id, noise_estimate))
        if (
            noise_plot_dir is not None
            and noise_estimate is not None
        ):
            noise_out = (
                noise_plot_dir
                / f"{dataset_stem}_{replicate.rep_id}_noise.{plot_suffix}"
            )
            if plot_workers == 1:
                _save_noise_plot(
                    noise_out,
                    dataset_stem,
                    replicate.rep_id,
                    noise_estimate,
                    force_unit_label=force_unit_label,
                    value_scale=unit_scale,
                )
            else:
                plot_jobs.append(
                    (
                        "noise",
                        (
                            noise_out,
                            dataset_stem,
                            replicate.rep_id,
                            noise_estimate,
                            force_unit_label,
                            unit_scale,
                        ),
                    )
                )
        replicate_entries.append((replicate, noise_estimate))

    common_peak_hz: float | None = None
    if args.instrument_peak_hz is not None and args.instrument_peak_hz > 0:
        common_peak_hz = float(args.instrument_peak_hz)
    else:
        peak_values = [
            est.noise_peak_hz
            for _, est in replicate_entries
            if est and est.noise_peak_hz
        ]
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
        if (
            base_cutoff_hz is not None
            and sample_rate is not None
            and sample_rate > 0
            and replicate.force_n.size >= 8
        ):
            nyquist = 0.5 * float(sample_rate)
            cutoff = min(base_cutoff_hz, nyquist * 0.95)
            if cutoff > 0 and cutoff < nyquist:
                normalized_cutoff = cutoff / nyquist
                try:
                    b, a = butter(4, normalized_cutoff, btype="low", analog=False)
                    padlen = 3 * max(len(a), len(b))
                    if replicate.force_n.size > padlen:
                        filtered_force = filtfilt(b, a, replicate.force_n)
                        analysis_replicate = replace(
                            replicate,
                            force_n=np.asarray(filtered_force, dtype=float),
                        )
                        effective_cutoff = float(cutoff)
                except ValueError:
                    pass

        result = _analyse_replicate(
            analysis_replicate,
            displacement_window=(args.disp_min, args.disp_max),
            window_seconds=args.window_seconds,
            polyorder=args.polyorder,
            threshold=threshold_value,
        )
        if result is None:
            _print_summary(
                replicate.rep_id,
                0,
                [],
                threshold_value,
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
            threshold_value,
            noise_estimate=noise_estimate,
            filter_cutoff_hz=effective_cutoff,
            instrument_peak_hz=common_peak_hz,
            force_unit_label=force_unit_label,
            unit_scale=unit_scale,
        )
        summary.append((replicate.rep_id, len(result.spikes)))

        if plot_dir is not None:
            out_path = plot_dir / f"{dataset_stem}_{replicate.rep_id}.{plot_suffix}"
            if plot_workers == 1:
                _save_plot(
                    out_path,
                    dataset_stem,
                    replicate.rep_id,
                    result,
                    threshold_value,
                    force_unit_label=force_unit_label,
                    value_scale=unit_scale,
                )
            else:
                plot_jobs.append(
                    (
                        "analysis",
                        (
                            out_path,
                            dataset_stem,
                            replicate.rep_id,
                            result,
                            threshold_value,
                            force_unit_label,
                            unit_scale,
                        ),
                    )
                )

    if plot_jobs:
        _render_plot_jobs(plot_jobs, max_workers=plot_workers)

    _print_noise_totals(
        dataset_stem,
        noise_summary,
        force_unit_label=force_unit_label,
        unit_scale=unit_scale,
        common_peak_hz=common_peak_hz,
        common_cutoff_hz=base_cutoff_hz,
    )
    if noise_plot_dir is not None:
        summary_out = noise_plot_dir / f"{dataset_stem}_noise_summary.{plot_suffix}"
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
    parser.add_argument(
        "--input", "-i", required=True, help="Path to the CSV file to analyse."
    )
    parser.add_argument(
        "--disp-min", type=float, default=50.0, help="Lower displacement bound (mm)."
    )
    parser.add_argument(
        "--disp-max", type=float, default=200.0, help="Upper displacement bound (mm)."
    )
    parser.add_argument(
        "--window-seconds",
        type=float,
        default=None,
        help=(
            "Savitzky–Golay window duration in seconds (converted to nearest odd number of samples). "
            "Defaults to a long window equal to 50% of the trimmed trace duration (minimum 4 s)."
        ),
    )
    parser.add_argument(
        "--polyorder", type=int, default=3, help="Savitzky–Golay polynomial order."
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=None,
        help=(
            "Residual spike threshold in force units. Defaults to 0.014 N measured at the collection "
            "width and is rescaled to match the requested reporting width/unit."
        ),
    )
    parser.add_argument(
        "--plot-dir",
        help=(
            "Optional directory for plots with spikes marked. "
            "Requires matplotlib; files are named <dataset>_<replicate>.<ext>."
        ),
    )
    parser.add_argument(
        "--plot-workers",
        type=int,
        default=4,
        help=(
            "Number of processes to use for generating plots (default 4). "
            "Lower the value if memory is limited."
        ),
    )
    parser.add_argument(
        "--plot-format",
        choices=["png", "pdf", "svg"],
        default="png",
        help="Image format for generated plots (default png).",
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
        help=(
            "Optional absolute force limit to keep noise samples. Interpreted in the selected report "
            "unit at the collection width and rescaled internally to the reporting width."
        ),
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
        default=None,
        help=(
            "Absolute force that marks the onset of specimen engagement. Defaults to 0.2 N measured at "
            "the collection width; values are interpreted in the selected report unit and rescaled to "
            "the reporting width."
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


def _print_summary(
    rep_id: str,
    sample_count: int,
    spikes: list[Spike],
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
    header_bits = [
        f"samples={sample_count}",
        f"threshold={display_threshold:.3f} {force_unit_label}",
    ]
    print("  " + " | ".join(header_bits))
    if noise_estimate is not None:
        peak_fragment = (
            f" | peak≈{noise_estimate.noise_peak_hz:.2f} Hz"
            if noise_estimate.noise_peak_hz is not None
            else ""
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
    biases = (
        np.array([est.dc_offset_n for _, est in available], dtype=float) * unit_scale
    )
    max_abs = (
        np.array([est.max_abs_n for _, est in available], dtype=float) * unit_scale
    )
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


if __name__ == "__main__":
    raise SystemExit(main())
