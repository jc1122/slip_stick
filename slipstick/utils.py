"""Utility functions for the slipstick package."""

from __future__ import annotations

import numpy as np
from typing import cast, Union
from pathlib import Path


def scale_force_value(value: float, scale: float) -> float:
    """Scale a single force value for display.

    Args:
        value: The force value to scale.
        scale: The scaling factor (e.g., 100.0 for cN conversion).

    Returns:
        The scaled force value.
    """
    return value * scale


def scale_force_array(values: np.ndarray, scale: float) -> np.ndarray:
    """Scale an array of force values for display.

    Args:
        values: The array of force values to scale.
        scale: The scaling factor (e.g., 100.0 for cN conversion).

    Returns:
        The scaled force array.
    """
    return values * scale


def pluralize(count: int, singular: str, plural: str | None = None) -> str:
    """Return singular or plural form based on count.

    Args:
        count: The count to check.
        singular: The singular form of the word.
        plural: The plural form of the word. If None, defaults to singular + 's'.

    Returns:
        The appropriate singular or plural form.
    """
    if count == 1:
        return singular
    return plural if plural else f"{singular}s"


def compute_rms(values: np.ndarray) -> float:
    """Compute root mean square of array values.

    Args:
        values: The array of values to compute RMS for.

    Returns:
        The root mean square value.
    """
    return float(np.sqrt(np.mean(values**2)))


def ensure_matplotlib_available(feature_name: str) -> bool:
    """Check if matplotlib is available, print warning if not.

    Args:
        feature_name: Name of the feature requiring matplotlib.

    Returns:
        True if matplotlib is available, False otherwise.
    """
    import importlib.util

    if importlib.util.find_spec("matplotlib") is None:
        print(
            f"matplotlib is required for {feature_name}; skipping output.",
            file=__import__("sys").stderr,
        )
        return False
    return True


def clamp_value(
    value: Union[float, int, None],
    min_val: Union[float, int],
    max_val: Union[float, int, None] = None,
    default: Union[float, int, None] = None,
) -> Union[float, int]:
    """Clamp value to bounds, with optional default for invalid input.

    Args:
        value: The value to clamp.
        min_val: Minimum allowed value.
        max_val: Maximum allowed value (optional).
        default: Default value if input is None or invalid.

    Returns:
        The clamped value.
    """
    if value is None or value <= 0:
        if default is not None:
            return default
        return min_val
    if max_val is not None:
        return min(max(value, min_val), max_val)
    return max(value, min_val)


def is_positive_value(value: Union[float, int, None]) -> bool:
    """Check if value is not None and positive.

    Args:
        value: The value to check.

    Returns:
        True if value is not None and positive, False otherwise.
    """
    return value is not None and value > 0


def get_positive_or_default(
    value: Union[float, int, None], default: Union[float, int]
) -> Union[float, int]:
    """Return value if positive, otherwise return default.

    Args:
        value: The value to check.
        default: Default value to return if value is not positive.

    Returns:
        The value if positive, otherwise the default.
    """
    return cast(Union[float, int], value) if is_positive_value(value) else default


def ensure_parent_dir(file_path: Path) -> None:
    """Ensure parent directory exists for a file path.

    Args:
        file_path: The file path whose parent directory should be created.
    """
    file_path.parent.mkdir(parents=True, exist_ok=True)
