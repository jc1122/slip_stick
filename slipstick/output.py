"""Output formatting functions for the slipstick package."""

from __future__ import annotations

from typing import Any

import numpy as np

from .models import NoiseEstimate, Spike
from .utils import pluralize, scale_force_value


def print_section_header(title: str, level: int = 1) -> None:
    """Print a formatted section header.

    Args:
        title: The section title.
        level: Header level (1 for main sections, 2 for subsections).
    """
    if level == 1:
        print(f"\n{title}")
    else:
        print(f"{title}")


def format_statistics_line(label: str, values: dict[str, Any], unit: str = "") -> str:
    """Format a statistics line with key-value pairs.

    Args:
        label: The label for the statistics line.
        values: Dictionary of key-value pairs to format.
        unit: Optional unit string to append.

    Returns:
        Formatted statistics string.
    """
    parts = [f"{label}:"]
    for key, val in values.items():
        if isinstance(val, float):
            parts.append(f"{key}={val:.5f}")
        else:
            parts.append(f"{key}={val}")
    if unit:
        parts[-1] += f" {unit}"
    return " | ".join(parts)


def print_replicate_summary(
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
    """Print a summary for a single replicate.

    Args:
        rep_id: Replicate identifier.
        sample_count: Number of samples in the analysis window.
        spikes: List of detected spikes.
        threshold: Detection threshold in Newtons.
        noise_estimate: Optional noise estimate for the replicate.
        filter_cutoff_hz: Optional filter cutoff frequency.
        instrument_peak_hz: Optional instrument peak frequency.
        force_unit_label: Force unit label for display.
        unit_scale: Unit scaling factor for display.
    """
    print_section_header(f"Replicate {rep_id}", level=2)
    display_threshold = scale_force_value(threshold, unit_scale)
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
        std_display = scale_force_value(noise_estimate.std_n, unit_scale)
        bias_display = scale_force_value(noise_estimate.dc_offset_n, unit_scale)
        max_display = scale_force_value(noise_estimate.max_abs_n, unit_scale)
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
        residual_display = scale_force_value(spike.residual_n, unit_scale)
        print(
            f"  time={spike.time_s:.3f} s | disp={spike.disp_mm:.3f} mm | "
            f"residual={residual_display:.4f} {force_unit_label} (idx {spike.index})"
        )
    print()


def print_noise_summary(
    dataset_stem: str,
    noise_entries: list[tuple[str, NoiseEstimate | None]],
    *,
    force_unit_label: str,
    unit_scale: float,
    common_peak_hz: float | None,
    common_cutoff_hz: float | None,
) -> None:
    """Print a summary of noise estimates for all replicates.

    Args:
        dataset_stem: Dataset filename stem.
        noise_entries: List of (replicate_id, noise_estimate) tuples.
        force_unit_label: Force unit label for display.
        unit_scale: Unit scaling factor for display.
        common_peak_hz: Common instrument peak frequency.
        common_cutoff_hz: Common filter cutoff frequency.
    """
    print_section_header(f"Noise estimates for {dataset_stem}")
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
        format_statistics_line(
            "  replicates",
            {
                "count": len(available),
                "median std": float(np.median(stds)),
                "mean std": float(np.mean(stds)),
                "max abs noise": float(np.max(max_abs)),
            },
            force_unit_label,
        )
    )
    print(
        format_statistics_line(
            "  bias",
            {
                "median": float(np.median(biases)),
                "range": f"({float(np.min(biases)):.5f}, {float(np.max(biases)):.5f})",
            },
            force_unit_label,
        )
    )
    print(
        format_statistics_line(
            "  total noise samples",
            {"count": sample_total, "max disp used": float(np.max(disp_limits))},
            "mm",
        )
    )
    if common_peak_hz is not None:
        second_line = f"  instrument peak≈{common_peak_hz:.2f} Hz"
        if common_cutoff_hz is not None:
            second_line += f" | applied cutoff≈{common_cutoff_hz:.2f} Hz"
        print(second_line)
    print()


def print_dataset_summary(dataset_stem: str, summary: list[tuple[str, int]]) -> None:
    """Print a final summary for the entire dataset.

    Args:
        dataset_stem: Dataset filename stem.
        summary: List of (replicate_id, spike_count) tuples.
    """
    print_section_header(f"Summary for {dataset_stem}")
    if not summary:
        print("  No replicates processed.\n")
        return
    total = 0
    for rep_id, count in summary:
        total += count
        plural = pluralize(count, "spike")
        print(f"  {rep_id}: {count} {plural}")
    plural_total = pluralize(total, "spike")
    print(f"  Total: {total} {plural_total}\n")
