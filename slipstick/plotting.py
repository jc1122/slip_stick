from __future__ import annotations

from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Any, List

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
        futures = [executor.submit(_run_plot_job, job) for job in jobs]
        for future in as_completed(futures):
            future.result()


def _execute_plot_job(kind: str, payload: tuple[Any, ...]) -> None:
    if plt is None:
        return
    if kind == "analysis":
        out_path, dataset_stem, rep_id, result, threshold_value, force_unit_label, unit_scale = payload
        _save_plot(
            out_path,
            dataset_stem,
            rep_id,
            result,
            threshold_value,
            force_unit_label=force_unit_label,
            value_scale=unit_scale,
        )
    elif kind == "noise":
        (
            out_path,
            dataset_stem,
            rep_id,
            noise_estimate,
            force_unit_label,
            unit_scale,
        ) = payload
        _save_noise_plot(
            out_path,
            dataset_stem,
            rep_id,
            noise_estimate,
            force_unit_label=force_unit_label,
            value_scale=unit_scale,
        )
    else:  # pragma: no cover - defensive
        raise ValueError(f"Unknown plot job type: {kind}")


def _run_plot_job(job: tuple[str, tuple[Any, ...]]) -> None:
    kind, payload = job
    _execute_plot_job(kind, payload)


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

    if (
        noise.raw_force is None
        or noise.baseline_force is None
        or noise.residual_force is None
        or noise.disp_mm is None
        or noise.time_s is None
    ):
        raise ValueError("NoiseEstimate raw data required for plotting is missing.")

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
