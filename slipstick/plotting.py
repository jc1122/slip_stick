from __future__ import annotations

from concurrent.futures import ProcessPoolExecutor, as_completed
from math import ceil
from pathlib import Path
from typing import Any, Iterable, List, Sequence

import numpy as np

from .models import DetectionResult, NoiseEstimate

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

DEFAULT_SPECTRUM_REFERENCE_BANDS: tuple[tuple[str, float, float], ...] = (
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
)


def _validate_noise_plot_data(noise: NoiseEstimate) -> None:
    """Validate that noise estimate has required plotting data.
    
    Args:
        noise: NoiseEstimate instance to validate.
    
    Raises:
        ValueError: If any required field is missing.
    """
    required_fields = [
        'raw_force', 'baseline_force', 'residual_force',
        'disp_mm', 'time_s'
    ]
    missing = [f for f in required_fields if getattr(noise, f) is None]
    if missing:
        raise ValueError(
            f"NoiseEstimate missing required fields for plotting: {', '.join(missing)}"
        )


def _configure_spectrum_axis(
    ax,
    freqs: np.ndarray,
    power: np.ndarray,
    title: str,
    force_unit_label: str
) -> None:
    """Configure common settings for spectrum plots.
    
    Args:
        ax: Matplotlib axis to configure.
        freqs: Frequency array.
        power: Power spectral density array.
        title: Title for the axis.
        force_unit_label: Label for force units (e.g., 'cN / 25 mm').
    """
    ax.set_xlim(0.0, min(10.0, freqs.max() if freqs.size else 10.0))
    positive_power = power[power > 0]
    if positive_power.size:
        ax.set_ylim(positive_power.min() * 0.8, power.max() * 1.2)
    else:
        ax.set_ylim(1e-9, 1e-3)
    ax.set_title(title)
    ax.set_xlabel("Frequency (Hz)")
    ax.set_ylabel(f"Power ({force_unit_label}²/Hz)")
    ax.grid(True, which="both", linestyle=":", linewidth=0.5)


def _add_frequency_band_shading(
    ax,
    freqs: np.ndarray,
    power: np.ndarray,
    band_min: float | None,
    band_max: float | None,
    reference_bands: Sequence[tuple[str, float, float]],
    has_spikes: bool
) -> None:
    """Add frequency band shading to a spectrum plot.
    
    Args:
        ax: Matplotlib axis to add shading to.
        freqs: Frequency array.
        power: Power spectral density array.
        band_min: Lower bound of primary highlighted band (Hz).
        band_max: Upper bound of primary highlighted band (Hz).
        reference_bands: Sequence of (label, lower, upper) reference bands.
        has_spikes: Whether the replicate has detected spikes.
    """
    # Primary band shading
    if band_min is not None and band_max is not None:
        lower = min(band_min, band_max)
        upper = max(band_min, band_max)
        ax.axvspan(lower, upper, color="#f0c5ff", alpha=0.35)
    
    # Reference bands with annotations (only if spikes detected)
    if reference_bands and has_spikes:
        band_ratios = _compute_band_ratios(freqs, power, reference_bands)
        for label, lower, upper, ratio in band_ratios:
            if ratio < 0.05:
                continue
            ax.axvspan(lower, upper, color="#ffdede", alpha=0.45)
            ax.text(
                (lower + upper) / 2,
                power.max() * 0.75,
                f"{label}\n{ratio*100:.0f}% power",
                color="#b22222",
                fontsize=8,
                ha="center",
                va="center",
            )


def _add_peak_marker(
    ax,
    peak_freq: float,
    power: np.ndarray,
    fontsize: int = 9
) -> None:
    """Add a vertical marker line and label for peak frequency.
    
    Args:
        ax: Matplotlib axis to add marker to.
        peak_freq: Peak frequency in Hz.
        power: Power spectral density array for y-positioning.
        fontsize: Font size for the label.
    """
    ax.axvline(
        peak_freq,
        color="#c23b22",
        linestyle="--",
        linewidth=1.0,
    )
    if power.size > 0:
        ax.text(
            peak_freq,
            power.max(),
            f" {peak_freq:.2f} Hz",
            color="#c23b22",
            fontsize=fontsize,
            ha="left",
            va="bottom",
            rotation=90,
        )


def _render_plot_jobs(
    jobs: List[tuple[str, tuple[Any, ...]]], *, max_workers: int
) -> None:
    if not jobs:
        return
    if max_workers <= 1:
        for kind, payload in jobs:
            _execute_plot_job(kind, payload)
        return
    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(_execute_plot_job, *job) for job in jobs]
        for future in as_completed(futures):
            future.result()


def _execute_plot_job(kind: str, payload: tuple[Any, ...]) -> None:
    if plt is None:
        return
    if kind == "analysis":
        _save_plot(*payload)
    elif kind == "noise":
        _save_noise_plot(*payload)
    elif kind == "spectrum":
        _save_residual_spectrum_plot(*payload)
    else:  # pragma: no cover - defensive
        raise ValueError(f"Unknown plot job type: {kind}")


def _compute_band_ratios(
    freqs: np.ndarray,
    power: np.ndarray,
    bands: Iterable[tuple[str, float, float]],
) -> list[tuple[str, float, float, float]]:
    if freqs.size == 0 or power.size == 0:
        return []
    total_power = float(np.sum(power))
    if total_power <= 0.0:
        return []
    ratios: list[tuple[str, float, float, float]] = []
    for label, lower, upper in bands:
        mask = (freqs >= lower) & (freqs <= upper)
        if not np.any(mask):
            continue
        band_power = float(np.sum(power[mask]))
        if band_power <= 0.0:
            continue
        ratios.append((label, lower, upper, band_power / total_power))
    return ratios


def _save_residual_spectrum_plot(
    out_path: Path,
    dataset_stem: str,
    rep_id: str,
    result: DetectionResult,
    force_unit_label: str,
    value_scale: float,
    band_min: float | None,
    band_max: float | None,
    reference_bands: Sequence[tuple[str, float, float]] = DEFAULT_SPECTRUM_REFERENCE_BANDS,
) -> None:
    assert plt is not None

    if result.residual_freqs is None or result.residual_power is None:
        return

    fig, ax = plt.subplots(figsize=(10, 5))

    ax.semilogy(
        result.residual_freqs,
        result.residual_power,
        color="#2a5599",
        linewidth=1.2,
    )

    _add_frequency_band_shading(
        ax,
        result.residual_freqs,
        result.residual_power,
        band_min,
        band_max,
        reference_bands,
        has_spikes=bool(result.spikes)
    )

    if result.peak_freq_hz is not None:
        _add_peak_marker(ax, result.peak_freq_hz, result.residual_power)

    rms = np.sqrt(np.mean(result.residual**2))
    _configure_spectrum_axis(
        ax,
        result.residual_freqs,
        result.residual_power,
        f"Replicate {rep_id} (RMS {rms * value_scale:.2f} {force_unit_label})",
        force_unit_label
    )

    fig.suptitle(
        f"Residual Spectrum – {dataset_stem}",
        fontsize=15,
        fontweight="semibold",
    )
    fig.tight_layout(rect=[0, 0, 1, 0.96])
    fig.savefig(out_path, dpi=110)
    plt.close(fig)





def _save_plot(
    out_path: Path,
    dataset_stem: str,
    rep_id: str,
    result: DetectionResult,
    threshold: float,
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
        ax_force.scatter(
            spike_disp,
            force_series[spike_indices],
            color="#d62728",
            marker="x",
            label="spikes",
        )
    ax_force.set_ylabel(f"Force ({force_unit_label})")
    ax_force.set_title("Force vs displacement")
    ax_force.legend(loc="upper left")

    ax_residual.plot(result.disp, residual_series, color="#9467bd", label="residual")
    ax_residual.axhline(
        threshold_display, color="0.3", linestyle="--", linewidth=1.0, label="threshold"
    )
    ax_residual.axhline(-threshold_display, color="0.3", linestyle="--", linewidth=1.0)
    if spike_indices:
        ax_residual.scatter(
            spike_disp, residual_series[spike_indices], color="#d62728", marker="x"
        )
    ax_residual.set_xlabel("Displacement (mm)")
    ax_residual.set_ylabel(f"Residual ({force_unit_label})")
    ax_residual.legend(loc="upper left")

    fig.suptitle(
        f"{dataset_stem} – replicate {rep_id}", fontsize=15, fontweight="semibold"
    )
    fig.tight_layout(rect=[0, 0, 1, 0.97])
    fig.savefig(out_path, dpi=110)
    plt.close(fig)


def save_residual_spectra_summary(
    out_path: Path,
    dataset_stem: str,
    entries: Sequence[tuple[str, DetectionResult]],
    *,
    force_unit_label: str,
    value_scale: float,
    band_min: float | None,
    band_max: float | None,
    reference_bands: Sequence[tuple[str, float, float]] = DEFAULT_SPECTRUM_REFERENCE_BANDS,
) -> None:
    assert plt is not None

    valid_entries = [
        (rep_id, result)
        for rep_id, result in entries
        if result.residual_freqs is not None
        and result.residual_power is not None
        and result.residual_freqs.size
        and result.residual_power.size
    ]
    if not valid_entries:
        return

    n_cols = min(3, len(valid_entries))
    n_rows = ceil(len(valid_entries) / n_cols)
    fig, axes = plt.subplots(n_rows, n_cols, figsize=(n_cols * 4.2, n_rows * 3.5))
    axes = np.atleast_1d(axes).ravel()

    for ax in axes[len(valid_entries) :]:
        ax.axis("off")

    for ax, (rep_id, result) in zip(axes, valid_entries):
        ax.semilogy(
            result.residual_freqs,
            result.residual_power,
            color="#2a5599",
            linewidth=1.2,
        )
        
        spike_count = len(result.spikes)
        _add_frequency_band_shading(
            ax,
            result.residual_freqs,
            result.residual_power,
            band_min,
            band_max,
            reference_bands,
            has_spikes=spike_count > 0
        )

        if result.peak_freq_hz is not None:
            _add_peak_marker(ax, result.peak_freq_hz, result.residual_power, fontsize=8)

        if spike_count > 0:
            ax.text(
                0.02,
                0.92,
                f"{spike_count} spike{'s' if spike_count != 1 else ''}",
                transform=ax.transAxes,
                fontsize=8,
                fontweight="semibold",
                color="#b22222",
            )

        rms = float(np.sqrt(np.mean(result.residual**2)))
        _configure_spectrum_axis(
            ax,
            result.residual_freqs,
            result.residual_power,
            f"Rep {rep_id} (RMS {rms * value_scale:.2f} {force_unit_label})",
            force_unit_label
        )

    fig.suptitle(
        f"Residual spectra – {dataset_stem}",
        fontsize=15,
        fontweight="semibold",
    )
    fig.tight_layout(rect=[0, 0, 1, 0.96])
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=130)
    plt.close(fig)


def _save_noise_plot(
    out_path: Path,
    dataset_stem: str,
    rep_id: str,
    noise: NoiseEstimate,
    force_unit_label: str,
    value_scale: float,
) -> None:
    assert plt is not None

    _validate_noise_plot_data(noise)

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
    fig.savefig(out_path, dpi=110)
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
    biases = (
        np.array([est.dc_offset_n for _, est in available], dtype=float) * value_scale
    )
    stds = np.array([est.std_n for _, est in available], dtype=float) * value_scale
    max_abs = (
        np.array([est.max_abs_n for _, est in available], dtype=float) * value_scale
    )

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
    fig.savefig(out_path, dpi=110)
    plt.close(fig)
