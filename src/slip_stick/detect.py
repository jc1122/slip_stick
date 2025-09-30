"""Detection and decomposition utilities for slip–stick analysis.

The module currently exposes two core operations:

- ``estimate_midband_welch`` estimates the slip–stick band from a force trace using a
  Welch PSD peak and its −3 dB bandwidth.
- ``decompose_complementary`` performs a lossless split of the signal into low/mid/high
  components using complementary, zero‑phase raised‑cosine filters.

Both functions are deterministic, depend only on NumPy, and surface rich diagnostics so
that downstream tooling (CLI, JSON exports) can reason about guardrails and edge cases.
Future iterations will add onset detection on top of these primitives.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, Optional, Tuple

import numpy as np

__all__ = [
    "BandEstimate",
    "DecompositionResult",
    "band_estimate_to_summary",
    "decompose_complementary",
    "decomposition_to_summary",
    "estimate_midband_welch",
]

_EPS = 1e-18


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass
class BandEstimate:
    """Container for band edges and associated diagnostics."""

    f1: float
    f2: float
    f_c: float
    diagnostics: Dict[str, float]

    def as_dict(self) -> Dict[str, float]:
        data = dict(self.diagnostics)
        data.update({"f1": self.f1, "f2": self.f2, "f_c": self.f_c})
        return data


@dataclass
class DecompositionResult:
    """Bundle of complementary components and diagnostics."""

    low: np.ndarray
    mid: np.ndarray
    high: np.ndarray
    recon_rms: float
    diagnostics: Dict[str, float]

    def as_dict(self) -> Dict[str, float]:
        data = dict(self.diagnostics)
        data.setdefault("recon_rms", self.recon_rms)
        return data


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------


def band_estimate_to_summary(estimate: BandEstimate) -> Dict[str, float]:
    """Return a JSON-friendly summary for a :class:`BandEstimate`."""

    return estimate.as_dict()


def decomposition_to_summary(result: DecompositionResult) -> Dict[str, float]:
    """Return a JSON-friendly summary for a :class:`DecompositionResult`."""

    return result.as_dict()


# ---------------------------------------------------------------------------
# Band estimation
# ---------------------------------------------------------------------------


def estimate_midband_welch(
    y: np.ndarray,
    fs: float,
    *,
    search_band: Tuple[float, float] | None = (1.0, 40.0),
    nperseg: int = 1024,
    noverlap: Optional[int] = None,
    smooth_hz: float = 1.0,
    baseline_window: Optional[Tuple[float, float]] = None,
    min_bandwidth_hz: float = 0.5,
) -> BandEstimate:
    """Estimate slip–stick band edges and centre from a Welch PSD.

    Parameters
    ----------
    y
        1‑D force signal (single replicate). NaNs will be replaced with the mean.
    fs
        Sampling rate in Hz (must be positive).
    search_band
        Frequency window in Hz. Defaults to (1, 40); ``None`` expands to (1, 0.45·fs).
    nperseg, noverlap
        Welch segment parameters. Defaults target ~0.1 Hz resolution at fs≈100 Hz.
    smooth_hz
        Moving-average width (Hz) applied before peak picking.
    baseline_window
        Optional ``(t0, t1)`` baseline window in seconds for diagnostics.
    min_bandwidth_hz
        Minimum bandwidth to enforce if the −3 dB window collapses.
    """

    if y.ndim != 1:
        raise ValueError("y must be 1‑D")
    if not np.isfinite(fs) or fs <= 0:
        raise ValueError("fs must be a positive finite number")
    if nperseg <= 0:
        raise ValueError("nperseg must be positive")
    if smooth_hz <= 0:
        raise ValueError("smooth_hz must be positive")
    if min_bandwidth_hz <= 0:
        raise ValueError("min_bandwidth_hz must be positive")

    y = np.asarray(y, dtype=float)
    finite_mask = np.isfinite(y)
    diagnostics: Dict[str, float] = {
        "n_samples": float(y.size),
        "nperseg": float(nperseg),
        "smooth_hz": float(smooth_hz),
        "min_bandwidth_hz": float(min_bandwidth_hz),
    }
    if not np.all(finite_mask):
        diagnostics["n_drop_nonfinite"] = float(np.count_nonzero(~finite_mask))
        if np.any(finite_mask):
            mean = float(np.nanmean(y))
        else:
            mean = 0.0
        y = y.copy()
        y[~finite_mask] = mean
    mean = float(np.mean(y)) if y.size else 0.0
    diagnostics["signal_mean"] = mean
    y = y - mean
    if y.size == 0:
        return BandEstimate(float("nan"), float("nan"), float("nan"), diagnostics=diagnostics)

    if search_band is None:
        search_band = (1.0, 0.45 * fs)
    fmin, fmax = float(search_band[0]), float(search_band[1])
    fmin = max(0.0, fmin)
    fmax = min(max(fmin + 1.0, fmax), 0.45 * fs)
    diagnostics.update({"search_fmin": fmin, "search_fmax": fmax})

    f, P, welch_diag = _welch_psd(y, fs, nperseg=nperseg, noverlap=noverlap)
    diagnostics.update(welch_diag)
    mask = (f >= fmin) & (f <= fmax)
    f_b = f[mask]
    P_b = P[mask]
    if f_b.size == 0:
        diagnostics["has_band"] = 0.0
        return BandEstimate(float("nan"), float("nan"), float("nan"), diagnostics=diagnostics)
    diagnostics["has_band"] = 1.0

    P_s = _smooth_psd(P_b, f_b, smooth_hz=smooth_hz)
    idx_peak = int(np.argmax(P_s))
    P_peak = float(P_s[idx_peak])
    diagnostics["peak_power"] = P_peak
    diagnostics["peak_index"] = float(idx_peak)
    if P_peak <= 0:
        return BandEstimate(float("nan"), float("nan"), float("nan"), diagnostics=diagnostics)

    thr = 0.5 * P_peak
    i1 = idx_peak
    while i1 > 0 and P_s[i1] >= thr:
        i1 -= 1
    i2 = idx_peak
    n = len(P_s)
    while i2 < n - 1 and P_s[i2] >= thr:
        i2 += 1
    i1 = max(0, i1)
    i2 = min(n - 1, i2)

    f1 = float(f_b[i1])
    f2 = float(f_b[i2])
    if f2 <= f1:
        f2 = float(f_b[min(len(f_b) - 1, i1 + 1)])
        if f2 <= f1:
            f2 = f1 + min_bandwidth_hz

    bandwidth = f2 - f1
    if bandwidth < min_bandwidth_hz:
        expand = 0.5 * (min_bandwidth_hz - bandwidth)
        f1 = max(fmin, f1 - expand)
        f2 = min(fmax, f2 + expand)
        bandwidth = f2 - f1
    diagnostics.update({"f1": f1, "f2": f2, "bandwidth_hz": bandwidth})

    P_win = P_b[i1 : i2 + 1]
    f_win = f_b[i1 : i2 + 1]
    num = float(np.sum(P_win * f_win))
    den = float(np.sum(P_win) + _EPS)
    f_c = num / den
    diagnostics["psd_df_hz"] = float(f[1] - f[0]) if f.size >= 2 else float("nan")

    if baseline_window is not None:
        t0, t1 = baseline_window
        if not np.isfinite(t0) or not np.isfinite(t1):
            raise ValueError("baseline_window values must be finite")
        if t1 <= t0:
            raise ValueError("baseline_window must satisfy t1 > t0")
        idx0 = max(0, int(math.floor(t0 * fs)))
        idx1 = min(len(y), int(math.ceil(t1 * fs)))
        diagnostics.update(
            {
                "baseline_t0": float(t0),
                "baseline_t1": float(t1),
                "baseline_samples": float(max(idx1 - idx0, 0)),
            }
        )
        baseline_seg = y[idx0:idx1]
        if baseline_seg.size >= max(8, nperseg // 4):
            f_base, P_base, base_diag = _welch_psd(
                baseline_seg, fs, nperseg=nperseg, noverlap=noverlap
            )
            diagnostics["baseline_segment_count"] = base_diag.get("segment_count", 0.0)
            base_mask = (f_base >= fmin) & (f_base <= fmax)
            if np.any(base_mask):
                P_base_s = _smooth_psd(P_base[base_mask], f_base[base_mask], smooth_hz=smooth_hz)
                baseline_peak = float(np.max(P_base_s))
                diagnostics["baseline_peak_power"] = baseline_peak
                if baseline_peak > 0:
                    diagnostics["baseline_peak_ratio"] = P_peak / baseline_peak
        else:
            diagnostics["baseline_segment_count"] = 0.0

    diagnostics.setdefault("segment_count", 0.0)
    return BandEstimate(f1=f1, f2=f2, f_c=f_c, diagnostics=diagnostics)


def _welch_psd(
    y: np.ndarray, fs: float, *, nperseg: int = 1024, noverlap: Optional[int] = None
) -> Tuple[np.ndarray, np.ndarray, Dict[str, float]]:
    if noverlap is None:
        noverlap = nperseg // 2
    step = nperseg - noverlap
    n = len(y)
    if n < nperseg:
        y = np.pad(y, (0, nperseg - n), mode="constant")
        n = len(y)
    win = np.hanning(nperseg)
    scale = float(np.sum(win**2)) * fs
    psd_accum = None
    count = 0
    for start in range(0, n - nperseg + 1, step):
        seg = y[start : start + nperseg]
        seg = seg - float(np.mean(seg))
        segw = seg * win
        S = np.fft.rfft(segw)
        P = (np.abs(S) ** 2) / scale
        psd_accum = P if psd_accum is None else (psd_accum + P)
        count += 1
    if count == 0:
        f = np.fft.rfftfreq(nperseg, d=1.0 / fs)
        return f, np.zeros_like(f), {"segment_count": 0.0}
    psd = psd_accum / count
    f = np.fft.rfftfreq(nperseg, d=1.0 / fs)
    return f, psd, {"segment_count": float(count)}


def _smooth_psd(P: np.ndarray, f: np.ndarray, *, smooth_hz: float) -> np.ndarray:
    if P.size < 3:
        return P
    df = float(f[1] - f[0]) if f.size >= 2 else 1.0
    w = max(1, int(round(smooth_hz / max(df, 1e-9))))
    if w % 2 == 0:
        w += 1
    k = np.ones(w, dtype=float) / w
    return np.convolve(P, k, mode="same")


# ---------------------------------------------------------------------------
# Lossless decomposition
# ---------------------------------------------------------------------------


def decompose_complementary(
    y: np.ndarray,
    fs: float,
    f1: float,
    f2: float,
    *,
    tw1: Optional[float] = None,
    tw2: Optional[float] = None,
) -> DecompositionResult:
    """Split ``y`` into low/mid/high using complementary raised‑cosine filters."""

    if y.ndim != 1:
        raise ValueError("y must be 1‑D")
    if not np.isfinite(fs) or fs <= 0:
        raise ValueError("fs must be a positive finite number")
    if f2 <= f1:
        raise ValueError("f2 must be greater than f1")

    y = np.asarray(y, dtype=float)
    finite_mask = np.isfinite(y)
    diagnostics: Dict[str, float] = {
        "n_samples": float(len(y)),
        "f1_requested": float(f1),
        "f2_requested": float(f2),
    }
    if not np.all(finite_mask):
        diagnostics["n_drop_nonfinite"] = float(np.count_nonzero(~finite_mask))
        if np.any(finite_mask):
            mean = float(np.nanmean(y))
        else:
            mean = 0.0
        y = y.copy()
        y[~finite_mask] = mean
    else:
        mean = float(np.mean(y)) if y.size else 0.0
    diagnostics["signal_mean"] = mean
    y = y - mean
    if y.size == 0:
        raise ValueError("signal is empty after preprocessing")

    nyq = 0.5 * float(fs)
    f1_used = max(0.2, min(float(f1), nyq * 0.9))
    f2_used = max(f1_used + 0.1, min(float(f2), nyq * 0.95))
    diagnostics.update({"nyquist": nyq, "f1_used": f1_used, "f2_used": f2_used})

    if tw1 is None:
        tw1 = max(0.5, 0.5 * f1_used)
    if tw2 is None:
        tw2 = max(1.0, 0.2 * f2_used)
    if tw1 <= 0 or tw2 <= 0:
        raise ValueError("transition widths must be positive")
    diagnostics.update({"tw1": float(tw1), "tw2": float(tw2)})

    N = len(y)
    nfft = 1 << (N - 1).bit_length()
    diagnostics["nfft"] = float(nfft)
    Y = np.fft.rfft(y, n=nfft)
    f = np.fft.rfftfreq(nfft, d=1.0 / fs)

    def _rc_lowpass(freqs: np.ndarray, fc: float, tw: float) -> np.ndarray:
        H = np.zeros_like(freqs, dtype=float)
        H[freqs <= fc] = 1.0
        ramp = (freqs > fc) & (freqs < fc + tw)
        H[ramp] = 0.5 * (1.0 + np.cos(math.pi * (freqs[ramp] - fc) / tw))
        return H

    L1 = _rc_lowpass(f, f1_used, tw1)
    L2 = _rc_lowpass(f, f2_used, tw2)

    low = np.fft.irfft(Y * L1, n=nfft)[:N]
    mid = np.fft.irfft(Y * (L2 - L1), n=nfft)[:N]
    high = np.fft.irfft(Y * (1.0 - L2), n=nfft)[:N]

    recon = low + mid + high
    err = recon - y
    recon_rms = float(np.sqrt(np.mean(err * err)))

    energy_low = float(np.sum(low * low))
    energy_mid = float(np.sum(mid * mid))
    energy_high = float(np.sum(high * high))
    energy_total = float(np.sum(y * y))
    diagnostics.update(
        {
            "recon_rms": recon_rms,
            "energy_low": energy_low,
            "energy_mid": energy_mid,
            "energy_high": energy_high,
            "energy_total": energy_total,
            "energy_fraction_low": energy_low / energy_total if energy_total > 0 else float("nan"),
            "energy_fraction_mid": energy_mid / energy_total if energy_total > 0 else float("nan"),
            "energy_fraction_high": (
                energy_high / energy_total if energy_total > 0 else float("nan")
            ),
        }
    )

    return DecompositionResult(
        low=low,
        mid=mid,
        high=high,
        recon_rms=recon_rms,
        diagnostics=diagnostics,
    )
