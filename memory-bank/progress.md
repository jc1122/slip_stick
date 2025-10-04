# Progress

## Recent updates
- Removed legacy parsing and detection scaffolding, tests, scripts, and tooling.
- Added a single self-contained script (`slipstick.py`) that loads the CSV,
  detrends the 50–200 mm displacement window, and reports residual spikes.
- Introduced an optional `--plot-dir` flag that writes spike-marked PNG plots when
  matplotlib is available.
- Trimmed the README and Memory Bank to match the lightweight workflow.

## Current status
🟢 Ready for ad-hoc use. The CLI works on the provided CSV format with default
parameters and prints per-replicate spike summaries.

## Open considerations
- Confirm performance on very long runs or replicates with sparse data.
- Validate plotting output once matplotlib is installed.
- Decide later whether exporting results to a file format is necessary.
