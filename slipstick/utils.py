"""Utility functions for the slipstick package."""

from __future__ import annotations

import numpy as np


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
