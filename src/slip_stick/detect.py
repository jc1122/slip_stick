"""Detection and decomposition scaffolding for slip–stick analysis.

This module focuses on two core capabilities:

1) Estimating the frequency band of the mid‑frequency slip–stick component from data
   (e.g., via a Welch PSD peak and its −3 dB bandwidth).
2) Performing a lossless three‑way split of the force signal into low/mid/high using
   complementary, zero‑phase filters implemented in the frequency domain. By
   construction, ``low + mid + high == original`` to numerical precision.

The intent is to keep the implementation dependency‑light (numpy only), transparent,
and reproducible. We avoid SciPy by providing a small Welch implementation. Onset
logic will be added in a follow‑up iteration, once decomposition and band estimation
are wired and tested.

Public API (initial):

- ``estimate_midband_welch(y, fs, ...) -> (f1, f2, f_c, diagnostics)``
- ``decompose_complementary(y, fs, f1, f2, ...) -> (low, mid, high, recon_rms)``

Both are pure functions that operate on a single replicate array.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional, Sequence, Tuple

import math
import numpy as np

__all__ = ["estimate_midband_welch", "decompose_complementary"]


# ---------------------------------------------------------------------------
# Band estimation
# ---------------------------------------------------------------------------


@dataclass
class BandEstimate:
    f1: float
    f2: float
    f_c: float
    diagnostics: Dict[str, float]


def estimate_midband_welch(
    y: np.ndarray,
    fs: float,
    *,
    search_band: Tuple[float, float] | None = (1.0, 40.0),
    nperseg: int = 1024,
    noverlap: Optional[int] = None,
    smooth_hz: float = 1.0,
) -> BandEstimate:
    """Estimate slip–stick band edges and center from a Welch PSD.

    Parameters
    ----------
    y
        1‑D force signal (single replicate). Mean will be removed internally.
    fs
        Sampling rate in Hz.
    search_band
        Frequency window to search (Hz). If None, uses (1.0, 0.45*fs).
    nperseg, noverlap
        Welch segment length and overlap. Defaults aim for ~0.1 Hz resolution at fs≈100.
    smooth_hz
        Moving‑average smoothing width (Hz) applied to the PSD before peak picking.

    Returns
    -------
    BandEstimate
        ``f1`` and ``f2`` are the −3 dB bandwidth around the dominant peak within
        the search band. ``f_c`` is the power‑weighted centroid within [f1, f2].
    """

    if y.ndim != 1:
        raise ValueError("y must be 1‑D")
    y = y.astype(float, copy=False)
    y = y - np.nanmean(y)
    if not np.isfinite(fs) or fs <= 0:
        raise ValueError("fs must be a positive finite number")

    if search_band is None:
        search_band = (1.0, 0.45 * fs)
    fmin, fmax = float(search_band[0]), float(search_band[1])
    fmax = min(fmax, 0.45 * fs)

    f, P = _welch_psd(y, fs, nperseg=nperseg, noverlap=noverlap)
    mask = (f >= fmin) & (f <= fmax)
    f_b = f[mask]
    P_b = P[mask]
    if f_b.size == 0:
        return BandEstimate(float("nan"), float("nan"), float("nan"), diagnostics={})

    P_s = _smooth_psd(P_b, f_b, smooth_hz=smooth_hz)
    idx_peak = int(np.argmax(P_s))
    P_peak = float(P_s[idx_peak])
    if P_peak <= 0:
        return BandEstimate(float("nan"), float("nan"), float("nan"), diagnostics={})

    thr = 0.5 * P_peak  # −3 dB bandwidth
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
    P_win = P_b[i1 : i2 + 1]
    f_win = f_b[i1 : i2 + 1]
    num = float(np.sum(P_win * f_win))
    den = float(np.sum(P_win) + 1e-18)
    f_c = num / den

    diag = {
        "peak_power": P_peak,
        "search_fmin": fmin,
        "search_fmax": fmax,
    }
    return BandEstimate(f1=f1, f2=f2, f_c=f_c, diagnostics=diag)


def _welch_psd(
    y: np.ndarray, fs: float, *, nperseg: int = 1024, noverlap: Optional[int] = None
) -> Tuple[np.ndarray, np.ndarray]:
    if noverlap is None:
        noverlap = nperseg // 2
    step = nperseg - noverlap
    n = len(y)
    if n < nperseg:
        y = np.pad(y, (0, nperseg - n), mode="constant")
        n = len(y)
    win = np.hanning(nperseg)
    scale = float(np.sum(win ** 2)) * fs
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
        return f, np.zeros_like(f)
    psd = psd_accum / count
    f = np.fft.rfftfreq(nperseg, d=1.0 / fs)
    return f, psd


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
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, float]:
    """Split ``y`` into low/mid/high using complementary raised‑cosine filters.

    Low is a low‑pass with cutoff ``f1``. Mid is the difference between two low‑passes
    at ``f2`` and ``f1``. High is the residual above ``f2``. The sum of components
    reconstructs the original to numerical precision.

    Parameters
    ----------
    y, fs
        Signal and sampling rate (Hz).
    f1, f2
        Band edges in Hz where f1 < f2 < 0.5*fs. Guardrails are applied internally.
    tw1, tw2
        Transition widths (Hz) for the raised‑cosine ramps. If None, choose sensible
        defaults relative to f1/f2.

    Returns
    -------
    (low, mid, high, recon_rms)
        The three components and the RMS of the reconstruction error.
    """

    if y.ndim != 1:
        raise ValueError("y must be 1‑D")
    y = y.astype(float, copy=False)
    y = y - np.nanmean(y)
    nyq = 0.5 * float(fs)
    f1 = max(0.2, min(float(f1), nyq * 0.9))
    f2 = max(f1 + 0.1, min(float(f2), nyq * 0.95))

    if tw1 is None:
        tw1 = max(0.5, 0.5 * f1)
    if tw2 is None:
        tw2 = max(1.0, 0.2 * f2)

    N = len(y)
    nfft = 1 << (N - 1).bit_length()
    Y = np.fft.rfft(y, n=nfft)
    f = np.fft.rfftfreq(nfft, d=1.0 / fs)

    def _rc_lowpass(freqs: np.ndarray, fc: float, tw: float) -> np.ndarray:
        H = np.zeros_like(freqs, dtype=float)
        H[freqs <= fc] = 1.0
        ramp = (freqs > fc) & (freqs < fc + tw)
        # cosine goes from 1 at fc to 0 at fc+tw
        H[ramp] = 0.5 * (1.0 + np.cos(math.pi * (freqs[ramp] - fc) / tw))
        return H

    L1 = _rc_lowpass(f, f1, tw1)
    L2 = _rc_lowpass(f, f2, tw2)

    low = np.fft.irfft(Y * L1, n=nfft)[:N]
    mid = np.fft.irfft(Y * (L2 - L1), n=nfft)[:N]
    high = np.fft.irfft(Y * (1.0 - L2), n=nfft)[:N]

    recon = low + mid + high
    err = recon - y
    recon_rms = float(np.sqrt(np.mean(err * err)))
    return low, mid, high, recon_rms

