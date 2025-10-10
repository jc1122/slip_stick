# Progress

## Recent updates
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

## Current status
🟢 Ready for ad‑hoc and publication workflows. The CLI denoises, scales units,
and produces replicates’ figures and summaries in consistent, paper‑ready form.

## Open considerations
- Validate instrument band stability across future sessions and rigs; allow
  persisted profiles when needed.
- Consider exporting machine‑readable outputs (CSV/JSON) and vector plots (PDF/SVG).
