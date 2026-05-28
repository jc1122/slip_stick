from __future__ import annotations

import argparse
import locale
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

import numpy as np

from .core import _analyse_replicate, estimate_instrumental_noise, process_replicates
from .io import load_replicates
from .models import DetectionResult, NoiseEstimate, Replicate
from .output import (
    print_dataset_summary,
    print_noise_summary,
    print_replicate_summary,
)
from .plotting import (
    _render_plot_jobs,
    _save_noise_plot,
    _save_noise_summary_plot,
    _save_plot,
    _save_residual_spectrum_plot,
    save_residual_spectra_summary,
)
from .utils import (
    ensure_matplotlib_available,
    clamp_value,
)

# Configure numeric locale to support comma decimals when available.
try:
    locale.setlocale(locale.LC_NUMERIC, "")
except locale.Error:
    pass

# Defaults expressed in Newtons at the original collection width (before scaling).
# 0.0504 N scales to 1.4 cN when reported at 25 mm by default.
DEFAULT_THRESHOLD_FORCE_N = 0.0504
DEFAULT_NOISE_FORCE_ONSET_N = 0.2


@dataclass
class CliConfig:
    """Configuration derived from command-line arguments."""

    collection_width_mm: float
    report_width_mm: float
    force_scale: float
    unit_choice: str
    unit_scale: float
    unit_symbol: str
    force_unit_label: str
    threshold_value: float
    noise_force_max: float | None
    noise_force_onset: float | None
    plot_dir: Path | None
    noise_plot_dir: Path | None
    plot_spectra_dir: Path | None
    spectra_summary_path: Path | None
    spectra_band_min: float | None
    spectra_band_max: float | None
    plot_workers: int
    plot_suffix: str
    dataset_stem: str


def _ensure_plot_dir(dir_path: str | None, flag_name: str) -> Path | None:
    """Create a directory for saving plots, if matplotlib is available."""
    if not dir_path:
        return None
    if not ensure_matplotlib_available(flag_name):
        return None
    path = Path(dir_path)
    path.mkdir(parents=True, exist_ok=True)
    return path


def _build_plot_path(
    base_dir: Path, dataset_stem: str, rep_id: str, plot_type: str, suffix: str
) -> Path:
    """Build a standardized plot output path.

    Args:
        base_dir: Base directory for plots.
        dataset_stem: Dataset file stem.
        rep_id: Replicate identifier.
        plot_type: Type of plot (e.g., 'noise', 'spectrum') or empty string.
        suffix: File extension (e.g., 'png', 'pdf').

    Returns:
        Complete path for the plot file.
    """
    if plot_type:
        filename = f"{dataset_stem}_{rep_id}_{plot_type}.{suffix}"
    else:
        filename = f"{dataset_stem}_{rep_id}.{suffix}"
    return base_dir / filename


def _create_cli_config(args: argparse.Namespace, dataset_path: Path) -> CliConfig:
    """Create a configuration object from the parsed command-line arguments."""

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

    noise_force_max = _resolve_force_argument(args.noise_force_max, default_n=None)
    noise_force_onset = _resolve_force_argument(
        args.noise_force_onset, default_n=DEFAULT_NOISE_FORCE_ONSET_N
    )

    plot_workers = int(clamp_value(args.plot_workers, 1, default=4))

    plot_dir = _ensure_plot_dir(args.plot_dir, "--plot-dir")
    noise_plot_dir = _ensure_plot_dir(args.noise_plot_dir, "--noise-plot-dir")
    plot_spectra_dir = _ensure_plot_dir(
        getattr(args, "spectra_plot_dir", None), "--spectra-plot-dir"
    )

    spectra_summary_path: Path | None = None
    summary_arg = getattr(args, "spectra_summary", None)
    if summary_arg:
        if not ensure_matplotlib_available("--spectra-summary"):
            pass  # spectra_summary_path remains None
        else:
            spectra_summary_path = Path(summary_arg)
            spectra_summary_path.parent.mkdir(parents=True, exist_ok=True)

    spectra_band_min = getattr(args, "spectra_band_min", None)
    spectra_band_max = getattr(args, "spectra_band_max", None)
    if (
        spectra_band_min is not None
        and spectra_band_max is not None
        and spectra_band_max <= spectra_band_min
    ):
        spectra_band_max = spectra_band_min + 0.1

    return CliConfig(
        collection_width_mm=collection_width_mm,
        report_width_mm=report_width_mm,
        force_scale=force_scale,
        unit_choice=unit_choice,
        unit_scale=unit_scale,
        unit_symbol=unit_symbol,
        force_unit_label=force_unit_label,
        threshold_value=threshold_value,
        noise_force_max=noise_force_max,
        noise_force_onset=noise_force_onset,
        plot_dir=plot_dir,
        noise_plot_dir=noise_plot_dir,
        plot_spectra_dir=plot_spectra_dir,
        spectra_summary_path=spectra_summary_path,
        spectra_band_min=spectra_band_min,
        spectra_band_max=spectra_band_max,
        plot_workers=plot_workers,
        plot_suffix=str(args.plot_format).lower(),
        dataset_stem=dataset_path.stem,
    )


def _estimate_noise_for_replicates(
    replicates: list[Replicate],
    args: argparse.Namespace,
    config: CliConfig,
    retain_noise_segments: bool,
) -> tuple[
    list[tuple[str, NoiseEstimate | None]],
    list[tuple[Replicate, NoiseEstimate | None]],
    list[tuple[str, tuple[Any, ...]]],
]:
    noise_summary: list[tuple[str, NoiseEstimate | None]] = []
    replicate_entries: list[tuple[Replicate, NoiseEstimate | None]] = []
    plot_jobs: list[tuple[str, tuple[Any, ...]]] = []

    for replicate in replicates:
        noise_estimate = estimate_instrumental_noise(
            replicate,
            disp_min=args.noise_disp_min,
            disp_max=args.noise_disp_max,
            force_abs_max=config.noise_force_max,
            min_samples=args.noise_min_samples,
            force_onset=config.noise_force_onset,
            retain_segments=retain_noise_segments,
        )
        noise_summary.append((replicate.rep_id, noise_estimate))
        if config.noise_plot_dir is not None and noise_estimate is not None:
            noise_out = _build_plot_path(
                config.noise_plot_dir,
                config.dataset_stem,
                replicate.rep_id,
                "noise",
                config.plot_suffix,
            )
            if config.plot_workers == 1:
                _save_noise_plot(
                    noise_out,
                    config.dataset_stem,
                    replicate.rep_id,
                    noise_estimate,
                    force_unit_label=config.force_unit_label,
                    value_scale=config.unit_scale,
                )
            else:
                plot_jobs.append(
                    (
                        "noise",
                        (
                            noise_out,
                            config.dataset_stem,
                            replicate.rep_id,
                            noise_estimate,
                            config.force_unit_label,
                            config.unit_scale,
                        ),
                    )
                )
        replicate_entries.append((replicate, noise_estimate))
    return noise_summary, replicate_entries, plot_jobs


def _analyse_replicates_and_plot(
    replicate_entries: list[tuple[Replicate, NoiseEstimate | None]],
    replicate_map: dict[str, Replicate],
    base_cutoff_hz: float | None,
    common_peak_hz: float | None,
    config: CliConfig,
    plot_jobs: list[tuple[str, tuple[Any, ...]]],
    args: argparse.Namespace,
) -> tuple[
    list[tuple[str, int]],
    list[tuple[str, tuple[Any, ...]]],
    list[tuple[str, DetectionResult | None]],
]:
    summary: list[tuple[str, int]] = []
    result_entries: list[tuple[str, DetectionResult | None]] = []
    for replicate, noise_estimate in replicate_entries:
        analysis_replicate = replicate_map.get(replicate.rep_id, replicate)
        effective_cutoff: float | None = base_cutoff_hz

        result = _analyse_replicate(
            analysis_replicate,
            displacement_window=(args.disp_min, args.disp_max),
            window_seconds=args.window_seconds,
            polyorder=args.polyorder,
            threshold=config.threshold_value,
        )
        if result is None:
            print_replicate_summary(
                replicate.rep_id,
                0,
                [],
                config.threshold_value,
                noise_estimate=noise_estimate,
                filter_cutoff_hz=effective_cutoff,
                instrument_peak_hz=common_peak_hz,
                force_unit_label=config.force_unit_label,
                unit_scale=config.unit_scale,
            )
            summary.append((replicate.rep_id, 0))
            result_entries.append((replicate.rep_id, None))
            continue

        print_replicate_summary(
            replicate.rep_id,
            result.time.size,
            result.spikes,
            config.threshold_value,
            noise_estimate=noise_estimate,
            filter_cutoff_hz=effective_cutoff,
            instrument_peak_hz=common_peak_hz,
            force_unit_label=config.force_unit_label,
            unit_scale=config.unit_scale,
        )
        summary.append((replicate.rep_id, len(result.spikes)))
        result_entries.append((replicate.rep_id, result))

        if config.plot_dir is not None:
            out_path = _build_plot_path(
                config.plot_dir,
                config.dataset_stem,
                replicate.rep_id,
                "",
                config.plot_suffix,
            )
            if config.plot_workers == 1:
                _save_plot(
                    out_path,
                    config.dataset_stem,
                    replicate.rep_id,
                    result,
                    config.threshold_value,
                    force_unit_label=config.force_unit_label,
                    value_scale=config.unit_scale,
                )
            else:
                plot_jobs.append(
                    (
                        "analysis",
                        (
                            out_path,
                            config.dataset_stem,
                            replicate.rep_id,
                            result,
                            config.threshold_value,
                            config.force_unit_label,
                            config.unit_scale,
                        ),
                    )
                )
        if config.plot_spectra_dir is not None:
            spectrum_out = _build_plot_path(
                config.plot_spectra_dir,
                config.dataset_stem,
                replicate.rep_id,
                "spectrum",
                config.plot_suffix,
            )
            spectrum_args = (
                spectrum_out,
                config.dataset_stem,
                replicate.rep_id,
                result,
                config.force_unit_label,
                config.unit_scale,
                config.spectra_band_min,
                config.spectra_band_max,
            )
            if config.plot_workers == 1:
                _save_residual_spectrum_plot(*spectrum_args)
            else:
                plot_jobs.append(("spectrum", spectrum_args))
    return summary, plot_jobs, result_entries


def _calculate_common_frequencies(
    replicate_entries: list[tuple[Replicate, NoiseEstimate | None]],
    args: argparse.Namespace,
) -> tuple[float | None, float | None]:
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
    return common_peak_hz, base_cutoff_hz


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)

    dataset_path = Path(args.input)
    replicates = load_replicates(dataset_path)
    if not replicates:
        print("No replicates found in the file.")
        return 1

    config = _create_cli_config(args, dataset_path)

    if config.force_scale != 1.0:
        for replicate in replicates:
            replicate.force_n *= config.force_scale

    retain_noise_segments = config.noise_plot_dir is not None
    noise_summary, replicate_entries, plot_jobs = _estimate_noise_for_replicates(
        replicates, args, config, retain_noise_segments
    )

    common_peak_hz, base_cutoff_hz = _calculate_common_frequencies(
        replicate_entries, args
    )

    processed_replicates = process_replicates(
        replicates, force_scale=1.0, cutoff_hz=base_cutoff_hz
    )
    replicate_map = {rep.rep_id: rep for rep in processed_replicates}

    summary, plot_jobs, result_entries = _analyse_replicates_and_plot(
        replicate_entries,
        replicate_map,
        base_cutoff_hz,
        common_peak_hz,
        config,
        plot_jobs,
        args,
    )

    if plot_jobs:
        _render_plot_jobs(plot_jobs, max_workers=config.plot_workers)

    if config.spectra_summary_path is not None:
        spectrum_inputs = [
            (rep_id, result) for rep_id, result in result_entries if result is not None
        ]
        if spectrum_inputs:
            save_residual_spectra_summary(
                config.spectra_summary_path,
                config.dataset_stem,
                spectrum_inputs,
                force_unit_label=config.force_unit_label,
                value_scale=config.unit_scale,
                band_min=config.spectra_band_min,
                band_max=config.spectra_band_max,
            )

    print_noise_summary(
        config.dataset_stem,
        noise_summary,
        force_unit_label=config.force_unit_label,
        unit_scale=config.unit_scale,
        common_peak_hz=common_peak_hz,
        common_cutoff_hz=base_cutoff_hz,
    )
    if config.noise_plot_dir is not None:
        summary_out = (
            config.noise_plot_dir
            / f"{config.dataset_stem}_noise_summary.{config.plot_suffix}"
        )
        _save_noise_summary_plot(
            summary_out,
            config.dataset_stem,
            noise_summary,
            force_unit_label=config.force_unit_label,
            value_scale=config.unit_scale,
        )
    print_dataset_summary(config.dataset_stem, summary)

    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Detect positive force-baseline residual spikes above a threshold in the 50-200 mm window.",
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
            "Defaults to a long window equal to 50%% of the trimmed trace duration (minimum 4 s)."
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
        "--spectra-plot-dir",
        help=(
            "Optional directory for per-replicate residual spectrum plots. "
            "Requires matplotlib; files are named <dataset>_<replicate>_spectrum.<ext>."
        ),
    )
    parser.add_argument(
        "--spectra-summary",
        help=(
            "Optional path for a multi-panel residual spectrum summary image. "
            "Requires matplotlib; the parent directory is created automatically."
        ),
    )
    parser.add_argument(
        "--spectra-band-min",
        type=float,
        default=1.8,
        help=(
            "Lower bound of the highlighted slip–stick band (Hz) in residual spectrum plots (default 1.8)."
        ),
    )
    parser.add_argument(
        "--spectra-band-max",
        type=float,
        default=2.4,
        help=(
            "Upper bound of the highlighted slip–stick band (Hz) in residual spectrum plots (default 2.4)."
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


if __name__ == "__main__":
    raise SystemExit(main())
