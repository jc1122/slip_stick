from __future__ import annotations

from typing import List

import numpy as np
from scipy.signal import find_peaks, periodogram, savgol_filter

from .models import DetectionResult, NoiseEstimate, Replicate, Spike


def estimate_instrumental_noise(
    replicate: Replicate,
    *,
    disp_min: float,
    disp_max: float,
    force_abs_max: float | None,
    min_samples: int,
    force_onset: float | None,
    retain_segments: bool = False,
) -> NoiseEstimate | None:
    if replicate.force_n.size == 0:
        return None

    disp_limit_min = max(disp_min, 0.0)
    disp_limit_max = max(disp_max, disp_limit_min)
    if min_samples <= 0:
        min_samples = 1

    primary_mask = (replicate.disp_mm >= disp_limit_min) & (
        replicate.disp_mm <= disp_limit_max
    )
    if force_abs_max is not None and force_abs_max > 0:
        primary_mask &= np.abs(replicate.force_n) <= force_abs_max

    indices = np.flatnonzero(primary_mask)
    target_count = min(min_samples, replicate.force_n.size)
    if indices.size == 0:
        fallback_mask = (replicate.disp_mm >= disp_limit_min) & (
            replicate.disp_mm <= disp_limit_max
        )
        indices = np.flatnonzero(fallback_mask)[:target_count]

    if indices.size == 0:
        return None

    force_segment = replicate.force_n[indices]
    time_segment = replicate.time_s[indices]
    disp_segment = replicate.disp_mm[indices]

    if force_onset is not None and force_onset > 0 and force_segment.size:
        onset_mask = np.abs(force_segment) >= force_onset
        if np.any(onset_mask):
            first_contact_rel = int(np.flatnonzero(onset_mask)[0])
            force_segment = force_segment[:first_contact_rel]
            time_segment = time_segment[:first_contact_rel]
            disp_segment = disp_segment[:first_contact_rel]

    if force_segment.size == 0:
        return None

    disp_span = (
        float(np.max(disp_segment) - np.min(disp_segment)) if disp_segment.size else 0.0
    )
    if disp_span <= 0.0:
        disp_span = max(float(disp_limit_max - disp_limit_min), 1.0)

    polyorder = 2
    mean_force = float(np.mean(force_segment))
    baseline_force = np.full_like(force_segment, mean_force)
    residual_force = force_segment - baseline_force

    if force_segment.size >= 5:
        delta_disp = np.diff(disp_segment)
        step = (
            np.median(np.abs(delta_disp[delta_disp != 0])) if delta_disp.size else 0.0
        )
        if step <= 0.0:
            step = disp_span / max(force_segment.size - 1, 1)
        # Use a long SavGol window (≈ 50% of the displacement span) to better remove slow ramps.
        window_disp = max(disp_span * 0.5, step)
        window_samples = (
            int(round(window_disp / step)) if step > 0 else force_segment.size
        )
        window_samples = max(window_samples, polyorder + 1, 3)
        if window_samples % 2 == 0:
            window_samples += 1
        if window_samples > force_segment.size:
            window_samples = (
                force_segment.size
                if force_segment.size % 2 == 1
                else force_segment.size - 1
            )
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
        freqs, power = periodogram(centered, fs=sample_rate, scaling="spectrum")
        if power.size > 1:
            power[0] = 0.0  # ignore DC
            peak_index = int(np.argmax(power))
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
        raw_force=np.asarray(force_segment, dtype=float)
        if retain_segments
        else None,
        baseline_force=np.asarray(baseline_force, dtype=float)
        if retain_segments
        else None,
        residual_force=np.asarray(residual_force, dtype=float)
        if retain_segments
        else None,
        time_s=np.asarray(time_segment, dtype=float) if retain_segments else None,
        disp_mm=np.asarray(disp_segment, dtype=float) if retain_segments else None,
    )


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
    abs_residual = np.abs(residual)
    peak_indices, properties = find_peaks(abs_residual, height=threshold)
    if peak_indices.size == 0:
        return []

    spikes: List[Spike] = []
    for idx in peak_indices:
        spikes.append(
            Spike(
                index=int(idx),
                time_s=float(time[idx]),
                disp_mm=float(disp[idx]),
                residual_n=float(residual[idx]),
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
    return savgol_filter(
        y, window_length=window_length, polyorder=polyorder, mode="mirror"
    )
