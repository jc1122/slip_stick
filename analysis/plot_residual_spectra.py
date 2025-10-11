#!/usr/bin/env python3
"""Plot residual spectra for a slipstick dataset with the 1.8–2.4 Hz band highlighted."""

from __future__ import annotations

import argparse
from math import ceil
from pathlib import Path
from typing import Iterable

import numpy as np
from matplotlib import pyplot as plt
from scipy.signal import periodogram

from slipstick.cli import DEFAULT_NOISE_FORCE_ONSET_N, DEFAULT_THRESHOLD_FORCE_N
from slipstick.core import (
    _analyse_replicate,
    _estimate_sampling_rate,
    estimate_instrumental_noise,
    process_replicates,
)
from slipstick.io import load_replicates


SPIKE_BANDS: list[tuple[str, float, float]] = [
    ("mode ≈2.1 Hz", 2.05, 2.15),
    ("mode ≈2.2 Hz", 2.15, 2.25),
    ("sideband ≈2.7–2.9 Hz", 2.65, 2.95),
    ("harmonic ≈3.7 Hz", 3.60, 3.80),
    ("harmonic ≈4.7 Hz", 4.60, 4.80),
    ("harmonic ≈5.6 Hz", 5.50, 5.70),
    ("harmonic ≈6.5 Hz", 6.40, 6.60),
    ("harmonic ≈7.5 Hz", 7.40, 7.60),
    ("harmonic ≈8.4 Hz", 8.30, 8.50),
    ("harmonic ≈9.3 Hz", 9.20, 9.40),
]


def _common_cutoff(
    replicates: Iterable,
    *,
    force_scale: float,
    band_factor: float,
) -> float | None:
    peaks: list[float] = []
    for rep in replicates:
        noise = estimate_instrumental_noise(
            rep,
            disp_min=1.0,
            disp_max=5.0,
            force_abs_max=None,
            min_samples=40,
            force_onset=DEFAULT_NOISE_FORCE_ONSET_N * force_scale,
            retain_segments=False,
        )
        if noise and noise.noise_peak_hz:
            peaks.append(float(noise.noise_peak_hz))
    if not peaks:
        return None
    instrument_peak = float(np.median(peaks))
    return instrument_peak * band_factor


def _analyse_residual(
    rep,
    *,
    force_scale: float,
) -> tuple[np.ndarray, np.ndarray, float | None, float, int]:
    analysis_rep = rep
    result = _analyse_replicate(
        analysis_rep,
        displacement_window=(50.0, 200.0),
        window_seconds=None,
        polyorder=3,
        threshold=DEFAULT_THRESHOLD_FORCE_N * force_scale,
    )
    if result is None:
        return np.array([]), np.array([]), None, 0.0, 0

    fs = _estimate_sampling_rate(result.time)
    if fs is None or fs <= 0:
        return np.array([]), np.array([]), None, 0.0, len(result.spikes)

    residual = result.residual - np.mean(result.residual)
    freqs, power = periodogram(residual, fs=fs, scaling="spectrum")
    if power.size:
        power[0] = 0.0
    peak_idx = int(np.argmax(power)) if power.size else -1
    peak_freq = float(freqs[peak_idx]) if peak_idx >= 0 else None
    rms = float(np.sqrt(np.mean(residual**2))) if residual.size else 0.0
    return freqs, power, peak_freq, rms, len(result.spikes)


def plot_residual_spectra(
    dataset_path: Path,
    *,
    output_path: Path,
    band_min: float,
    band_max: float,
) -> None:
    replicates = load_replicates(dataset_path)
    if not replicates:
        raise SystemExit(f"No replicates found in {dataset_path}")

    collection_width_mm = 90.0
    report_width_mm = 25.0
    force_scale = report_width_mm / collection_width_mm

    cutoff = _common_cutoff(replicates, force_scale=force_scale, band_factor=0.8)

    processed_replicates = process_replicates(
        replicates, force_scale=force_scale, cutoff_hz=cutoff
    )

    spectra: list[
        tuple[
            str,
            np.ndarray,
            np.ndarray,
            float | None,
            float,
            int,
            list[tuple[str, float, float, float]],
        ]
    ] = []
    for rep in processed_replicates:
        freqs, power, peak_freq, rms, spike_count = _analyse_residual(
            rep, force_scale=force_scale
        )
        if freqs.size:
            total_power = float(np.sum(power)) if power.size else 0.0
            band_ratios: list[tuple[str, float, float, float]] = []
            if total_power > 0:
                for label, lower, upper in SPIKE_BANDS:
                    mask = (freqs >= lower) & (freqs <= upper)
                    if not np.any(mask):
                        continue
                    band_power = float(np.sum(power[mask]))
                    band_ratio = band_power / total_power if total_power > 0 else 0.0
                    if band_ratio <= 0:
                        continue
                    band_ratios.append((label, lower, upper, band_ratio))
            spectra.append(
                (rep.rep_id, freqs, power, peak_freq, rms, spike_count, band_ratios)
            )

    if not spectra:
        raise SystemExit("No spectra available after filtering.")

    n_cols = 3
    n_rows = ceil(len(spectra) / n_cols)
    fig, axes = plt.subplots(n_rows, n_cols, figsize=(n_cols * 4.2, n_rows * 3.5))
    axes = np.atleast_1d(axes).ravel()

    for ax in axes[len(spectra) :]:
        ax.axis("off")

    for ax, (rep_id, freqs, power, peak_freq, rms, spike_count, band_ratios) in zip(
        axes, spectra
    ):
        ax.axvspan(
            band_min,
            band_max,
            color="#f0c5ff",
            alpha=0.35,
            label=f"{band_min:.1f}–{band_max:.1f} Hz band",
        )
        ax.semilogy(freqs, power, color="#2a5599", linewidth=1.2)
        if peak_freq is not None:
            ax.axvline(peak_freq, color="#c23b22", linestyle="--", linewidth=1.0)
            ax.text(
                peak_freq,
                power.max(),
                f"{peak_freq:.2f} Hz",
                color="#c23b22",
                fontsize=9,
                ha="left",
                va="bottom",
                rotation=90,
            )
        if spike_count > 0:
            highlighted = False
            for label, lower, upper, ratio in band_ratios:
                if ratio < 0.05:
                    continue
                ax.axvspan(
                    lower,
                    upper,
                    color="#ffdede",
                    alpha=0.45,
                )
                ax.text(
                    (lower + upper) / 2,
                    power.max() * 0.8,
                    f"{label}\n{ratio*100:.0f}% power",
                    color="#b22222",
                    fontsize=8,
                    ha="center",
                    va="center",
                )
                highlighted = True
            if highlighted:
                ax.text(
                    0.02,
                    0.95,
                    f"{spike_count} spikes",
                    transform=ax.transAxes,
                    fontsize=9,
                    fontweight="semibold",
                    color="#b22222",
                )
        ax.set_xlim(0.0, min(10.0, freqs.max()))
        positive = power[power > 0]
        if positive.size:
            ax.set_ylim(positive.min() * 0.8, power.max() * 1.2)
        else:  # pragma: no cover - defensive fallback for degenerate spectra
            ax.set_ylim(1e-6, 1e-2)
        ax.set_title(f"Rep {rep_id} (RMS {rms*1000:.2f} mN)")
        ax.set_xlabel("Frequency (Hz)")
        ax.set_ylabel("Power (N²/Hz)")
        ax.grid(True, which="both", linestyle=":", linewidth=0.5)

    fig.suptitle(
        f"Residual spectra – {dataset_path.stem}",
        fontsize=15,
        fontweight="semibold",
    )
    fig.tight_layout(rect=[0, 0, 1, 0.96])
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=130)
    plt.close(fig)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Plot residual spectra for each replicate with the slip–stick pipeline "
            "and highlight a frequency band of interest."
        )
    )
    parser.add_argument("dataset", help="Path to the dataset CSV.")
    parser.add_argument(
        "--output",
        "-o",
        default="plots/residual_spectra.png",
        help="Output image path (default: plots/residual_spectra.png).",
    )
    parser.add_argument(
        "--band-min",
        type=float,
        default=1.8,
        help="Lower bound of the highlighted frequency band (Hz).",
    )
    parser.add_argument(
        "--band-max",
        type=float,
        default=2.4,
        help="Upper bound of the highlighted frequency band (Hz).",
    )
    args = parser.parse_args(argv)

    dataset_path = Path(args.dataset)
    output_path = Path(args.output)
    plot_residual_spectra(
        dataset_path,
        output_path=output_path,
        band_min=args.band_min,
        band_max=args.band_max,
    )
    print(f"Wrote {output_path}")


if __name__ == "__main__":
    main()
