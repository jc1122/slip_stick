# Progress

## Recent updates
- Default Savitzky–Golay baseline window now spans 50% of the trimmed trace
  (minimum 4 s) for better detrending of long runs.
- Savitzky–Golay smoothing now relies directly on SciPy, removing the custom
  fallback implementation.
- CSV parser now keeps embedded decimal commas even when fields are
  inconsistently quoted, restoring complete replicate traces (e.g. T2EN data).
- Plots render force/baseline vs displacement and were regenerated for all
  datasets after the parser fix.

## Current status
🟢 Ready for ad-hoc use. The CLI works on the provided CSV format with default
parameters and prints per-replicate spike summaries.

## Open considerations
- Confirm performance on very long runs or replicates with sparse data.
- Validate plotting output once matplotlib is installed.
- Decide later whether exporting results to a file format is necessary.
