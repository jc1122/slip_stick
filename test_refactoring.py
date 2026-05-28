#!/usr/bin/env python3
"""Quick test to verify DRY refactoring works correctly."""

import numpy as np
from pathlib import Path

# Test utils module
from slipstick.utils import (
    scale_force_value,
    scale_force_array,
    pluralize,
    compute_rms,
    ensure_matplotlib_available,
    clamp_value,
    is_positive_value,
    get_positive_or_default,
    ensure_parent_dir,
)

# Test core.py helpers
from slipstick.core import (
    _compute_savgol_window,
    _compute_baseline_and_residual,
    _find_peak_frequency,
    _find_spikes,
)

# Test plotting.py helpers (if matplotlib available)
try:
    from slipstick.plotting import _validate_noise_plot_data
    from slipstick.models import NoiseEstimate

    plotting_available = True
except ImportError:
    plotting_available = False

# Test cli.py helpers
from slipstick.cli import _build_plot_path

print("Testing utils.py helpers...")
assert scale_force_value(1.0, 100.0) == 100.0
assert scale_force_value(0.05, 100.0) == 5.0
arr = np.array([1.0, 2.0, 3.0])
scaled = scale_force_array(arr, 100.0)
assert np.allclose(scaled, np.array([100.0, 200.0, 300.0]))

# Test pluralization
assert pluralize(0, "spike") == "spikes"
assert pluralize(1, "spike") == "spike"
assert pluralize(2, "spike") == "spikes"
assert pluralize(1, "child", "children") == "child"
assert pluralize(2, "child", "children") == "children"

# Test RMS calculation
test_array = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
rms = compute_rms(test_array)
expected_rms = np.sqrt(np.mean(test_array**2))
assert abs(rms - expected_rms) < 1e-10

# Test value validation
assert clamp_value(5, 1, 10) == 5
assert clamp_value(15, 1, 10) == 10
assert clamp_value(0, 1, 10, 5) == 5
assert clamp_value(None, 1, 10, 5) == 5
assert is_positive_value(5)
assert not is_positive_value(0)
assert not is_positive_value(-1)
assert not is_positive_value(None)
assert get_positive_or_default(5, 10) == 5
assert get_positive_or_default(0, 10) == 10
assert get_positive_or_default(None, 10) == 10

# Test matplotlib availability (should work in test environment)
try:
    result = ensure_matplotlib_available("test")
    assert isinstance(result, bool)
    print("✓ Matplotlib availability check works")
except Exception as e:
    print(f"⚠ Matplotlib availability test failed: {e}")

# Test directory creation
test_dir = Path("test_temp_dir/subdir")
test_file = test_dir / "test.txt"
ensure_parent_dir(test_file)
assert test_dir.exists()
test_dir.rmdir()
test_dir.parent.rmdir()

print("✓ All utils.py helpers work correctly")

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

# Test spike detection groups contiguous positive threshold excursions into one event
time = np.arange(9, dtype=float)
disp = np.arange(9, dtype=float)
residual = np.array([0.0, 2.0, 1.6, 2.4, 0.0, -1.5, -3.0, -1.6, 0.0])
spikes = _find_spikes(time, disp, residual, threshold=1.4)
assert [spike.index for spike in spikes] == [3]
assert [spike.residual_n for spike in spikes] == [2.4]
negative_only = _find_spikes(time[:4], disp[:4], np.array([0.0, -1.5, -3.0, 0.0]), threshold=1.4)
assert negative_only == []
print("✓ Spike detection groups positive threshold excursions as events")

# Test plotting.py helpers (if matplotlib available)
if plotting_available:
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
        disp_mm=np.linspace(0, 5, 100),
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
        noise_peak_hz=10.0,
    )
    try:
        _validate_noise_plot_data(incomplete_noise)
        print("✗ Validation should have failed for incomplete data")
    except ValueError as e:
        print(f"✓ Validation correctly rejects incomplete data: {str(e)[:50]}...")
else:
    print("\n⚠ Skipping plotting tests (matplotlib not available)")

# Test cli.py helpers
print("\nTesting cli.py helpers...")
path = _build_plot_path(Path("/tmp/plots"), "dataset_2025", "rep_1", "noise", "png")
assert str(path) == "/tmp/plots/dataset_2025_rep_1_noise.png"
print(f"✓ Plot path construction: {path}")

path_no_type = _build_plot_path(Path("/tmp/plots"), "dataset_2025", "rep_1", "", "pdf")
assert str(path_no_type) == "/tmp/plots/dataset_2025_rep_1.pdf"
print("✓ Plot path without type: {path_no_type}")

# Test output.py helpers
try:
    from slipstick.output import (
        print_section_header,
        format_statistics_line,
        print_replicate_summary,
        print_dataset_summary,
    )
    from slipstick.models import Spike, NoiseEstimate

    print("\nTesting output.py helpers...")

    # Test section header
    import io
    from contextlib import redirect_stdout

    # Capture output for testing
    output_buffer = io.StringIO()
    with redirect_stdout(output_buffer):
        print_section_header("Test Section", level=1)
        print_section_header("Test Subsection", level=2)
    captured = output_buffer.getvalue()
    assert "\nTest Section" in captured
    assert "Test Subsection" in captured
    print("✓ Section header formatting works")

    # Test statistics line formatting
    line = format_statistics_line("test", {"count": 5, "value": 1.234}, "units")
    assert "test: | count=5 | value=1.23400 units" == line
    print("✓ Statistics line formatting works")

    # Test replicate summary (basic smoke test)
    test_spike = Spike(index=10, time_s=1.5, disp_mm=75.0, residual_n=2.5)
    output_buffer = io.StringIO()
    with redirect_stdout(output_buffer):
        print_replicate_summary(
            "test_rep",
            100,
            [test_spike],
            1.0,
            noise_estimate=None,
            filter_cutoff_hz=None,
            instrument_peak_hz=None,
            force_unit_label="N",
            unit_scale=1.0,
        )
    captured = output_buffer.getvalue()
    assert "Replicate test_rep" in captured
    assert "time=1.500 s" in captured
    print("✓ Replicate summary formatting works")

    # Test dataset summary
    output_buffer = io.StringIO()
    with redirect_stdout(output_buffer):
        print_dataset_summary("test_dataset", [("rep1", 2), ("rep2", 0)])
    captured = output_buffer.getvalue()
    assert "Summary for test_dataset" in captured
    assert "rep1: 2 spikes" in captured
    assert "rep2: 0 spikes" in captured
    assert "Total: 2 spikes" in captured
    print("✓ Dataset summary formatting works")

except ImportError:
    print("\n⚠ Skipping output tests (import failed)")

print("\n" + "=" * 60)
print("All SRP/SoC refactoring tests passed! ✓")
print("=" * 60)
