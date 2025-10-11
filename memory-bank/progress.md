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
- README refreshed with full CLI reference, performance guidance, and examples.

## Current status
🟢 Ready for ad‑hoc and publication workflows. The CLI denoises, scales units,
and produces replicates’ figures and summaries in consistent, paper‑ready form.
Batch plotting is fast (4× speed-up vs serial) while remaining deterministic.

## Open considerations
- Validate instrument band stability across future sessions and rigs; allow
  persisted profiles when needed.
- Consider exporting machine‑readable outputs (CSV/JSON) for downstream analysis.
