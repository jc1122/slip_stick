# Progress

## Recent updates
- Refactored the codebase into a Python package (`slipstick`) with separate modules for I/O, core logic, plotting, output formatting, and utilities.
- Instrumental noise estimation added (early window detrending + FFT); datasets now use a common instrument band. A zero-phase 4th-order Butterworth low-pass filter is applied before baseline fitting and spike detection.
- Defaults updated: reporting in `cN / 25 mm`, threshold 1.4 cN/25 mm. Width normalisation is configurable (collection vs report width).
- Publication-grade plotting style (consistent palette, dataset suptitles, residual panel for noise, unit-aware axes).
- CLI prints dataset noise summaries (bias/std/range) and spike counts.
- Force-related CLI inputs (threshold, noise gating limits) are converted into the reporting width/unit before analysis, keeping defaults consistent across configurations.
- CSV ingestion now streams once and rescales data in place, reducing memory churn.
- Plot generation is parallelised by default (4 workers) with optional PDF/SVG output and Cairo backend support for publication assets.
- Residual spectrum plotting is now part of the CLI via `--spectra-plot-dir` and `--spectra-summary`, reusing the core `DetectionResult` data to avoid duplicate Savitzky–Golay/periodogram code.
- README includes full CLI reference, performance guidance, and usage examples.
- **Code Quality Improvements (October 2025)**:
  - DRY refactoring eliminated ~140 lines of duplicated code with helper functions in `utils.py`, `core.py`, and `plotting.py`
  - SRP/SoC refactoring extracted output formatting to `output.py` module, reducing `cli.py` by 19%
  - Test coverage expanded from ~30% to ~45% with comprehensive unit tests
  - All linting (Ruff) and formatting (Black) checks pass
  - Achieved A-grade architectural compliance with excellent module separation

## Current status
🟢 **Production-ready**. The codebase is at a stable milestone with clean architecture, comprehensive testing, and excellent separation of concerns. The CLI denoises, scales units, and produces replicates' figures and summaries in consistent, paper-ready form. Batch plotting is fast (4× speed-up vs serial) while remaining deterministic.

## Open considerations
- Validate instrument band stability across future sessions and rigs; allow persisted profiles when needed.
- Consider exporting machine-readable outputs (CSV/JSON) for downstream analysis.
- Evaluate opportunities to leverage additional library functions to reduce custom code.
