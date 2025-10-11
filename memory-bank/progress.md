# Progress

## Recent updates
- Refactored the codebase into a Python package (`slipstick`) with separate modules for I/O, core logic, and plotting.
- Instrumental noise estimation added (early window detrending + FFT); datasets
  now use a common instrument band. A zero-phase 4th-order Butterworth low-pass
  filter is applied before baseline fitting and spike detection.
- Defaults updated: reporting in `cN / 25 mm`, threshold 1.4 cN/25 mm. Width
  normalisation is configurable (collection vs report width).
- Publication-grade plotting style (consistent palette, dataset suptitles,
  residual panel for noise, unit-aware axes).
- CLI prints dataset noise summaries (bias/std/range) and spike counts.
- Force-related CLI inputs (threshold, noise gating limits) are converted into
  the reporting width/unit before analysis, keeping defaults consistent across
  configurations.
- CSV ingestion now streams once and rescales data in place, reducing memory churn.
- Plot generation is parallelised by default (4 workers) with optional PDF/SVG output
  and Cairo backend support for publication assets.
- Residual spectrum plotting is now part of the CLI via `--spectra-plot-dir` and
  `--spectra-summary`, reusing the core `DetectionResult` data to avoid duplicate
  Savitzky–Golay/periodogram code. The legacy analysis script simply forwards to
  the CLI so behaviour stays accessible without parallel maintenance.
- README refreshed with full CLI reference, performance guidance, and examples.
- **Refactored for code clarity and maintainability**:
  - **`slipstick/cli.py`**:
    - Extracted duplicated directory creation logic into a helper function.
    - Decomposed the long `main` function into smaller, more focused functions.
  - **`slipstick/io.py`**:
    - Simplified the `load_replicates` function by breaking it into smaller, single-responsibility functions.
  - **`slipstick/plotting.py`**:
    - Simplified the parallel plot generation logic.
- **DRY Principle Refactoring (October 2025)**:
  - Created `slipstick/utils.py` with force scaling helpers to eliminate repeated `value * scale` patterns
  - Added core analysis helpers in `slipstick/core.py`:
    - `_compute_savgol_window()`: Centralized window length calculation
    - `_compute_baseline_and_residual()`: Single function for Savitzky-Golay processing
    - `_find_peak_frequency()`: Unified periodogram analysis and peak detection
  - Added plotting helpers in `slipstick/plotting.py`:
    - `_validate_noise_plot_data()`: Validation for noise estimate plotting
    - `_configure_spectrum_axis()`: Standardized spectrum axis configuration
    - `_add_frequency_band_shading()`: Reusable band highlighting logic
    - `_add_peak_marker()`: Consistent peak frequency markers
  - Added CLI helper `_build_plot_path()` for standardized path construction
  - **Impact**: Eliminated ~140 lines of code duplication, improved testability and maintainability
  - All existing functionality preserved and validated with comprehensive tests

## Current status
🟢 Ready for ad‑hoc and publication workflows. The CLI denoises, scales units,
and produces replicates’ figures and summaries in consistent, paper‑ready form.
Batch plotting is fast (4× speed-up vs serial) while remaining deterministic.

## Open considerations
- Validate instrument band stability across future sessions and rigs; allow
  persisted profiles when needed.
- Consider exporting machine‑readable outputs (CSV/JSON) for downstream analysis.
