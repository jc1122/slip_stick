"""Savitzky–Golay smoothing helpers with an optional SciPy acceleration.

If :mod:`scipy` is available we delegate to ``scipy.signal.savgol_filter`` for maximum
feature parity. Otherwise we fall back to a lightweight NumPy implementation that
supports the smoothing (0th derivative) case used in this project.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

import numpy as np

__all__ = ["savgol_filter_1d"]

Mode = Literal["reflect", "nearest"]

try:  # Prefer SciPy when available
    from scipy.signal import savgol_filter as _scipy_savgol_filter  # type: ignore
except Exception:  # pragma: no cover - SciPy absent in minimal envs
    _scipy_savgol_filter = None


def savgol_filter_1d(
    y: np.ndarray,
    window_length: int,
    polyorder: int,
    *,
    mode: Mode = "reflect",
) -> np.ndarray:
    """Apply a Savitzky–Golay smoothing filter to a 1-D array.

    Parameters
    ----------
    y
        Input data (1-D). The array is converted to ``float``.
    window_length
        Odd number >= polyorder + 1. The function adjusts even lengths by adding 1.
    polyorder
        Polynomial order of the smoothing filter.
    mode
        Padding strategy at the boundaries. ``"reflect"`` mirrors the sequence;
        ``"nearest"`` extends edge values.
    """

    y = np.asarray(y, dtype=float)
    if y.ndim != 1:
        raise ValueError("y must be 1-D")
    if y.size == 0:
        return np.empty_like(y)

    if _scipy_savgol_filter is not None:
        # Translate our simplified mode choices to SciPy keywords
        boundary = "mirror" if mode == "reflect" else "nearest"
        return _scipy_savgol_filter(
            y,
            window_length=window_length,
            polyorder=polyorder,
            mode=boundary,
        )

    return _manual_savgol(y, window_length, polyorder, mode=mode)


@lru_cache(maxsize=None)
def _savgol_coefficients(window_length: int, polyorder: int) -> np.ndarray:
    """Return convolution coefficients for the central Savitzky–Golay tap."""

    half = window_length // 2
    x = np.arange(-half, half + 1, dtype=float)
    A = np.vander(x, polyorder + 1, increasing=True)
    ATA = A.T @ A
    ATA_pinv = np.linalg.pinv(ATA)
    pseudo = ATA_pinv @ A.T
    return pseudo[0]


def _manual_savgol(
    y: np.ndarray,
    window_length: int,
    polyorder: int,
    *,
    mode: Mode,
) -> np.ndarray:
    if window_length <= 0:
        raise ValueError("window_length must be positive")
    if polyorder < 0:
        raise ValueError("polyorder must be non-negative")

    if window_length % 2 == 0:
        window_length += 1

    if window_length < polyorder + 1:
        raise ValueError("window_length must be at least polyorder + 1")

    if window_length > y.size:
        window_length = y.size if y.size % 2 == 1 else y.size - 1
        if window_length < polyorder + 1:
            raise ValueError("window_length must be <= len(y) and >= polyorder + 1")

    half = window_length // 2
    if mode == "reflect":
        padded = np.pad(y, (half, half), mode="reflect")
    elif mode == "nearest":
        padded = np.pad(y, (half, half), mode="edge")
    else:  # pragma: no cover - should not happen with current literals
        raise ValueError(f"unsupported mode: {mode}")

    coeffs = _savgol_coefficients(window_length, polyorder)
    filtered = np.convolve(padded, coeffs[::-1], mode="valid")
    if filtered.size != y.size:
        filtered = filtered[: y.size]
    return filtered
