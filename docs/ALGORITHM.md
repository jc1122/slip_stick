# Algorithm Description

## Overview

The slip-stick spike detection algorithm implements a multi-stage signal processing pipeline designed to identify discontinuous debonding events in tensile adhesion tests. This document provides detailed mathematical formulations and implementation notes.

## Processing Pipeline

### 1. Data Loading and Runtime Preconditions

**Input format:** FTM 10 CSV files with:
- 3-row header
- Comma decimal separators
- Column triples: (time, force, displacement) × N replicates
- Encoding: CP1250

**Implemented checks and assumptions:**
- The loader keeps complete time/force/displacement triples whose headers match the expected labels and units.
- Non-numeric or incomplete rows are skipped while populating each replicate.
- Later analysis stages require a non-empty 50-200 mm analysis window and positive time deltas for sampling-rate estimation.
- The current loader does not hard-fail a file solely for non-monotonic time, negative displacement, or nonuniform sampling.

### 2. Force Normalization

**Purpose:** Scale forces from collection width to reporting width for consistent units.

**Formula:**
```
f_report = f_raw × (w_report / w_collection)
```

**Default values:**
- `w_collection = 90 mm` (specimen width during test)
- `w_report = 25 mm` (standard reporting width)
- Scaling factor: 25/90 ≈ 0.2778

**Implementation:**
```python
force_scaled = force_n * (report_width_mm / collection_width_mm)
```

**Physical interpretation:** Normalizes force per unit width, allowing comparison across different specimen geometries.

### 3. Instrumental Noise Characterization

**Purpose:** Estimate background noise characteristics from pre-test baseline.

**Noise window selection:**
- Default range: 1–5 mm displacement
- Rationale: Specimen not engaged, measures instrument-only noise
- Avoid <1 mm (start-up transients) and >5 mm (specimen engagement)

**Processing steps:**

1. **Sample selection:**
   ```python
   mask = (disp_mm >= noise_disp_min) & (disp_mm <= noise_disp_max)
   noise_samples = force_n[mask]
   ```

2. **Engagement detection:**
   - If `noise_force_onset` is provided, truncate at the first sample exceeding the threshold
   - The CLI and publication generator pass a default onset of 0.2 N at the collection width, scaled to the reporting width
   - Prevents contamination from early specimen contact

3. **Baseline fitting:**
   - Long-window Savitzky-Golay filter (polynomial order 2)
   - Window length: approximately 50% of the selected displacement span
   - Edge handling: `mode="interp"` in the noise-estimation path
   - Removes slow drift and force offset

4. **Residual calculation:**
   ```python
   residual = noise_samples - baseline
   ```

5. **Statistics computation:**
   - Standard deviation: `σ = std(residual)`
   - Fitted-baseline force offset: `μ = mean(baseline)`
   - Maximum absolute: `max_abs = max(|residual|)`

6. **Spectral analysis:**
   - Compute periodogram: `P(f) = |FFT(residual - mean(residual))|²`
   - Identify peak frequency: `f_peak = argmax(P(f))` for f > 0
   - Physical meaning: Dominant instrument vibration frequency

**Output:** `NoiseEstimate` dataclass containing:
```python
@dataclass
class NoiseEstimate:
    std_n: float              # Noise standard deviation
    dc_offset_n: float        # Mean fitted-baseline force offset
    max_abs_n: float          # Maximum absolute residual
    sample_count: int         # Number of samples in noise window
    disp_max_mm: float        # Actual max displacement sampled
    time_span_s: float        # Duration of noise window
    sample_rate_hz: float | None  # Estimated sampling rate
    noise_peak_hz: float | None   # Dominant noise frequency
```

### 4. Dataset-Level Filter Design

**Purpose:** Design a common low-pass filter for all replicates based on instrument characteristics.

**Steps:**

1. **Collect replicate-level peaks:**
   ```python
   peak_frequencies = [est.noise_peak_hz for est in noise_estimates if est.noise_peak_hz]
   ```

2. **Compute central tendency:**
   ```python
   common_peak_hz = np.median(peak_frequencies)
   ```

3. **Derive cutoff frequency:**
   ```python
   cutoff_hz = common_peak_hz * instrument_cutoff_factor
   ```
   - Default `instrument_cutoff_factor = 0.8`
   - Rationale: Conservative cutoff below instrument peak preserves slip-stick band

4. **Safety constraints:**
   ```python
   nyquist = sample_rate_hz / 2
   cutoff_hz = min(cutoff_hz, nyquist * 0.95)  # Stay below Nyquist
   ```

**Result:** Single cutoff frequency applied to all replicates in dataset.

### 5. Zero-Phase Butterworth Filtering

**Purpose:** Remove high-frequency instrument noise while preserving slip-stick features.

**Filter specification:**
- Type: Butterworth low-pass
- Order: 4
- Cutoff: Derived from instrument peak frequency
- Implementation: `scipy.signal.butter` + `scipy.signal.filtfilt`

**Why zero-phase?**
- Forward-backward filtering (`filtfilt`) eliminates phase shift
- Preserves temporal alignment of slip-stick events
- Critical for accurate time/displacement reporting

**Algorithm:**

1. **Sampling rate estimation:**
   ```python
   dt = np.diff(time_s)
   fs = 1.0 / np.median(dt[dt > 0])
   ```

2. **Normalized cutoff:**
   ```python
   normalized_cutoff = cutoff_hz / (fs / 2)
   normalized_cutoff = min(normalized_cutoff, 0.95)
   ```

3. **Filter design:**
   ```python
   b, a = butter(N=4, Wn=normalized_cutoff, btype='low')
   ```

4. **Zero-phase application:**
   ```python
   filtered_force = filtfilt(b, a, force_n)
   ```

5. **Padding check:**
   - The implementation uses SciPy's default `filtfilt` padding method
   - A replicate is filtered only when its length exceeds
     `3 * max(len(a), len(b))`
   - Skip filtering if insufficient samples

**Physical interpretation:**
- Removes narrowband electrical/mechanical vibrations >cutoff
- Preserves low-frequency slip-stick oscillations <cutoff
- Typical slip-stick: 0.1–5 Hz; typical instrument noise: 5–30 Hz

### 6. Analysis Window Selection

**Purpose:** Restrict analysis to stable test region.

**Default window:** 50–200 mm displacement

**Selection criteria:**
- `disp_min`: Start of plateau region (excludes start-up transients)
- `disp_max`: End before test termination or failure

**Implementation:**
```python
mask = (disp_mm >= disp_min) & (disp_mm <= disp_max)
cropped_time = time_s[mask]
cropped_disp = disp_mm[mask]
cropped_force = force_n[mask]
```

**Validation:**
- Require minimum sample count: `n_samples > polyorder + 1`
- Typically need >100 samples for stable baseline

### 7. Savitzky-Golay Baseline Fitting

**Purpose:** Estimate slowly-varying trend to reveal short-lived spikes.

**Window length selection:**

1. **Automatic (default):**
   ```python
   duration_s = cropped_time[-1] - cropped_time[0]
   window_s = max(0.5 * duration_s, 4.0)  # 50% of duration, min 4 s
   ```

2. **Manual override:**
   - User can specify `--window-seconds`

3. **Convert to samples:**
   ```python
   window_length = int(round(window_s * sample_rate_hz))
   window_length = window_length + 1 if window_length % 2 == 0 else window_length
   ```

4. **Safety constraints:**
   ```python
   min_window = polyorder + 1  # Minimum for fitting
   max_window = len(cropped_force)  # Can't exceed data length
   window_length = max(min_window, min(window_length, max_window))
   if window_length % 2 == 0:
       window_length -= 1  # Must be odd
   ```

**Filter application:**
```python
baseline = savgol_filter(
    cropped_force,
    window_length=window_length,
    polyorder=3,
    mode='mirror'
)
```

**Residual calculation:**
```python
residual = cropped_force - baseline
```

**Implementation note:**
- The main 50-200 mm baseline uses `mode="mirror"` for edge handling.
- The shorter instrumental-noise baseline uses `mode="interp"` because it is
  fitted on a pre-test segment and is used only for noise characterization.

**Physical interpretation:**
- Long window (tens of seconds) averages out short spikes
- Polynomial order 3 captures gentle curvature
- Residual contains high-frequency events (slip-stick spikes)

### 8. Spike Detection

**Purpose:** Identify residual excursions exceeding detection threshold.

**Algorithm:** Threshold-excursion grouping on positive residual

```python
above_threshold = residual >= threshold
starts, ends = contiguous_true_regions(above_threshold)
event_indices = [
    start + np.argmax(residual[start:end])
    for start, end in zip(starts, ends)
]
```

**Threshold selection:**
- Default: 1.4 cN/25 mm (stored by the CLI as 0.0504 N at 90 mm collection width and scaled to 0.014 N in a 25 mm analysis trace)
- Rationale: ~10× typical noise floor (0.05–0.15 cN/25 mm)
- The per-file CLI parses explicit `--threshold` values in the selected force unit at the collection width before width scaling; the publication generator's `--threshold-cN` is direct cN/25 mm

**Peak properties:**
```python
for idx in event_indices:
    spike = Spike(
        index=idx,
        time_s=cropped_time[idx],
        disp_mm=cropped_disp[idx],
        residual_n=residual[idx]
    )
```

**Physical interpretation:**
- **Positive residual spikes:** Stick events with force above the local baseline
- **Negative residual excursions:** Force drops below the local baseline; these are not counted as slip-stick spike events by this method
- **Spike magnitude:** Energy dissipated per event
- **Inter-spike interval:** Period of stick-slip cycle

### 9. Residual Spectrum Analysis

**Purpose:** Characterize frequency content of slip-stick behavior.

**Periodogram computation:**

1. **Demean residual:**
   ```python
   residual_centered = residual - np.mean(residual)
   ```

2. **Compute periodogram:**
   ```python
   freqs, power = periodogram(
       residual_centered,
       fs=sample_rate_hz,
       scaling='spectrum'
   )
   ```

3. **Identify peak (excluding DC):**
   ```python
   peak_idx = np.argmax(power[freqs > 0])
   peak_freq = freqs[freqs > 0][peak_idx]
   ```

**Physical interpretation:**
- Peak frequency: Dominant slip-stick cycle rate
- Typical range: 0.1–2 Hz for polymer films
- Broad peaks: Irregular slip-stick
- Sharp peaks: Periodic slip-stick

## Mathematical Foundations

### Savitzky-Golay Filter

**Least-squares polynomial fitting:**

For window of 2m+1 points centered at n:
```
y_smooth[n] = Σ(i=-m to m) c_i × y[n+i]
```

Coefficients `c_i` determined by least-squares fit of polynomial:
```
p(x) = a_0 + a_1×x + a_2×x² + ... + a_k×x^k
```

**Properties:**
- Preserves high-order moments (area, slope, curvature)
- Smooths noise while maintaining shape
- Polynomial order k << window length for smoothing

### Butterworth Filter

**Transfer function:**
```
|H(ω)|² = 1 / (1 + (ω/ω_c)^(2n))
```

Where:
- ω = frequency
- ω_c = cutoff frequency
- n = filter order

**Properties:**
- Maximally flat passband (no ripples)
- Monotonic rolloff in stopband
- Order n=4 gives ~80 dB/decade attenuation

**Zero-phase implementation:**
```
y_filtered = filter_forward(filter_backward(y))
```
- Phase shift: 0° (no temporal distortion)
- Amplitude response: squared (steeper rolloff)

### Peak Detection

**Threshold excursion criteria:**
```
one event is counted for each contiguous interval where:
  residual[i] >= threshold

the event marker is placed at:
  argmax(residual) within that interval
```

**Advantages:**
- Simple and robust
- No assumptions about peak shape
- Handles varying peak widths

## Parameter Selection Guidelines

### Noise Window (`--noise-disp-min`, `--noise-disp-max`)

**Default:** 1–5 mm

**Adjustment criteria:**
- **Reduce lower bound** if start-up transients extend beyond 1 mm
- **Increase upper bound** if specimen engages earlier than 5 mm
- **Verify:** Noise plot should show flat, low-amplitude trace

### Analysis Window (`--disp-min`, `--disp-max`)

**Default:** 50–200 mm

**Adjustment criteria:**
- **Increase lower bound** if transients extend beyond 50 mm
- **Decrease upper bound** if test ends before 200 mm
- **Verify:** Window should contain stable plateau region

### Detection Threshold (`--threshold`)

**Default:** 1.4 cN/25 mm

In the per-file CLI, explicit `--threshold` values are parsed in `--report-unit`
at the collection width and then scaled by `report_width_mm / collection_width_mm`.
With default widths, `--threshold 5.04 --report-unit cN` displays as
1.400 cN/25 mm. Publication table regeneration uses `--threshold-cN` directly
in cN/25 mm.

**Adjustment criteria:**
- **Decrease** to detect smaller spikes (may increase false positives)
- **Increase** to focus on larger events (may miss subtle slip-stick)
- **Rule of thumb:** 5–10× noise standard deviation

### Filter Cutoff (`--instrument-cutoff-factor`)

**Default:** 0.8

**Adjustment criteria:**
- **Decrease** (<0.8) for aggressive filtering (use if high instrument noise)
- **Increase** (>0.8) for mild filtering (preserve more high-frequency content)
- **Verify:** Filtered force should preserve slip-stick events, remove vibrations

## Implemented Checks and Expected Data Conditions

### Input and Sampling
- Complete header triples are required for a replicate to be loaded
- Rows with unparsable numeric values are skipped
- Sampling rate is estimated from positive time differences
- Analysis requires at least `polyorder + 2` samples in the selected displacement window

### Processing Validation
- Filter cutoff is bounded below 95% of Nyquist
- Filtering is skipped when the trace is too short for SciPy's `filtfilt` padding
- Baseline fitting falls back to a mean baseline if Savitzky-Golay fitting raises `ValueError`
- Noise estimates use the requested minimum sample count before force-onset truncation; a smaller retained segment can still be reported

### Output Validation
- Detected spikes are threshold maxima within contiguous positive residual excursions
- Spike times and displacements are inside the selected analysis window
- Noise and residual spectra are diagnostic outputs, not additional gates

## Performance Characteristics

### Computational Complexity

- **Data loading:** O(n) where n = file size
- **Noise estimation:** O(m) where m = noise window samples
- **Filtering:** O(n) for the applied IIR forward-backward filter
- **Baseline fitting:** O(n) for Savitzky-Golay
- **Spike detection:** O(n) for peak finding
- **Overall:** O(n) per replicate for the implemented processing path

### Memory Usage

- **Storage:** ~3 arrays per replicate (time, force, displacement)
- **Peak memory:** During filtering (temporary buffers)
- **Typical:** <10 MB per dataset with 10 replicates

### Parallel Scaling

- **Plot generation:** Near-linear speedup with 4 workers
- **Batch processing:** Linear speedup up to number of datasets
- **I/O bound:** For small files, disk I/O may limit speedup

## References

### Signal Processing Methods

1. **Savitzky-Golay filtering:**
   - Savitzky, A., & Golay, M. J. E. (1964). "Smoothing and Differentiation of Data by Simplified Least Squares Procedures." *Analytical Chemistry*, 36(8), 1627-1639.

2. **Butterworth filters:**
   - Butterworth, S. (1930). "On the Theory of Filter Amplifiers." *Experimental Wireless and the Wireless Engineer*, 7, 536-541.

3. **Peak detection algorithms:**
   - Virtanen, P., et al. (2020). "SciPy 1.0: Fundamental Algorithms for Scientific Computing in Python." *Nature Methods*, 17, 261-272.

### Application Domain

4. **Slip-stick friction:**
   - Schallamach, A. (1971). "How does rubber slide?" *Wear*, 17(4), 301-312.
   - Persson, B. N. J. (2000). *Sliding Friction: Physical Principles and Applications*. Springer.

5. **Adhesion testing:**
   - ASTM D6862-11: Standard Test Method for 90 Degree Peel Resistance of Adhesives.

## Appendix: Code Examples

### Minimal spike detection example

```python
from slipstick.io import load_replicates
from slipstick.core import estimate_instrumental_noise, _analyse_replicate
from slipstick.core import process_replicates

# Load data
replicates = load_replicates("data.csv")

# Scale force from 90 mm collection width to 25 mm reporting width
processed = process_replicates(
    replicates,
    force_scale=25.0 / 90.0,
    cutoff_hz=None,
)

# Analyze first replicate
result = _analyse_replicate(
    replicate=processed[0],
    displacement_window=(50.0, 200.0),
    window_seconds=None,
    polyorder=3,
    threshold=0.014,  # 1.4 cN/25 mm in the scaled 25 mm trace
)

# Access results
print(f"Detected {len(result.spikes)} spikes")
for spike in result.spikes:
    print(f"  t={spike.time_s:.2f} s, d={spike.disp_mm:.1f} mm, F={spike.residual_n:.3f} N")
```

### Custom threshold example

```python
from slipstick.io import load_replicates
from slipstick.core import estimate_instrumental_noise, _analyse_replicate, process_replicates

# Estimate noise in the same scaled force units used for analysis
replicate = process_replicates(
    load_replicates("data.csv"),
    force_scale=25.0 / 90.0,
    cutoff_hz=None,
)[0]
noise_est = estimate_instrumental_noise(
    replicate=replicate,
    disp_min=1.0,
    disp_max=5.0,
    force_abs_max=None,
    min_samples=40,
    force_onset=None,
)

# Set threshold as 10× noise floor
threshold = 10 * noise_est.std_n
print(f"Adaptive threshold: {threshold:.4f} N")

# Use in analysis
result = _analyse_replicate(
    replicate=replicate,
    displacement_window=(50.0, 200.0),
    window_seconds=None,
    polyorder=3,
    threshold=threshold,
)
```
