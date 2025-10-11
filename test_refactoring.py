#!/usr/bin/env python3
"""Quick test to verify DRY refactoring works correctly."""

import numpy as np
from pathlib import Path

# Test utils module
from slipstick.utils import scale_force_value, scale_force_array

print("Testing utils.py helpers...")
assert scale_force_value(1.0, 100.0) == 100.0
assert scale_force_value(0.05, 100.0) == 5.0
arr = np.array([1.0, 2.0, 3.0])
scaled = scale_force_array(arr, 100.0)
assert np.allclose(scaled, np.array([100.0, 200.0, 300.0]))
print("✓ Force scaling helpers work correctly")

# Test core.py helpers
from slipstick.core import (
    _compute_savgol_window,
    _compute_baseline_and_residual,
    _find_peak_frequency
)

print("\nTesting core.py helpers...")
# Test window computation
window = _compute_savgol_window(100, 50, 3)
assert window % 2 == 1  # Must be odd
assert window >= 3
assert window <= 100
print(f"✓ Savitzky-Golay window computation: {window} samples")

# Test baseline and residual
test_force = np.sin(np.linspace(0, 10, 100)) + np.linspace(0, 5, 100)
baseline, residual = _compute_baseline_and_residual(test_force, 51, 3, mode="mirror")
assert baseline.shape == test_force.shape
assert residual.shape == test_force.shape
assert np.allclose(test_force, baseline + residual)
print("✓ Baseline and residual computation works")

# Test peak frequency detection
test_residual = np.sin(2 * np.pi * 5 * np.linspace(0, 1, 1000))  # 5 Hz signal
freqs, power, peak_freq = _find_peak_frequency(test_residual, 1000.0)
assert freqs.size > 0
assert power.size > 0
assert peak_freq is not None
assert 4.5 < peak_freq < 5.5  # Should detect ~5 Hz
print(f"✓ Peak frequency detection: {peak_freq:.2f} Hz (expected ~5 Hz)")

# Test plotting.py helpers (if matplotlib available)
try:
    from slipstick.plotting import (
        _validate_noise_plot_data,
        _configure_spectrum_axis,
        _add_frequency_band_shading,
        _add_peak_marker
    )
    from slipstick.models import NoiseEstimate
    
    print("\nTesting plotting.py helpers...")
    
    # Test validation
    noise = NoiseEstimate(
        std_n=0.1,
        dc_offset_n=0.0,
        max_abs_n=0.2,
        sample_count=100,
        disp_max_mm=5.0,
        time_span_s=1.0,
        sample_rate_hz=100.0,
        noise_peak_hz=10.0,
        raw_force=np.random.randn(100),
        baseline_force=np.zeros(100),
        residual_force=np.random.randn(100),
        time_s=np.linspace(0, 1, 100),
        disp_mm=np.linspace(0, 5, 100)
    )
    _validate_noise_plot_data(noise)
    print("✓ Noise plot data validation works")
    
    # Test incomplete noise data
    incomplete_noise = NoiseEstimate(
        std_n=0.1,
        dc_offset_n=0.0,
        max_abs_n=0.2,
        sample_count=100,
        disp_max_mm=5.0,
        time_span_s=1.0,
        sample_rate_hz=100.0,
        noise_peak_hz=10.0
    )
    try:
        _validate_noise_plot_data(incomplete_noise)
        print("✗ Validation should have failed for incomplete data")
    except ValueError as e:
        print(f"✓ Validation correctly rejects incomplete data: {str(e)[:50]}...")
    
except ImportError:
    print("\n⚠ Skipping plotting tests (matplotlib not available)")

# Test cli.py helpers
from slipstick.cli import _build_plot_path

print("\nTesting cli.py helpers...")
path = _build_plot_path(
    Path("/tmp/plots"),
    "dataset_2025",
    "rep_1",
    "noise",
    "png"
)
assert str(path) == "/tmp/plots/dataset_2025_rep_1_noise.png"
print(f"✓ Plot path construction: {path}")

path_no_type = _build_plot_path(
    Path("/tmp/plots"),
    "dataset_2025",
    "rep_1",
    "",
    "pdf"
)
assert str(path_no_type) == "/tmp/plots/dataset_2025_rep_1.pdf"
print(f"✓ Plot path without type: {path_no_type}")

print("\n" + "="*60)
print("All DRY refactoring tests passed! ✓")
print("="*60)
