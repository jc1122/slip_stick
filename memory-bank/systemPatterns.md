# System patterns

## Repository layout
- `slipstick/` contains the entire pipeline, split into modules for I/O, core logic, plotting, CLI, and utilities.
- `memory-bank/` stores lightweight documentation of scope, context, and progress.
- `datasets/` is an optional landing zone for CSV files; the script accepts any
  path supplied via `--input`.

## Processing pattern
1. Load the CSV with a custom parser in the `slipstick.io` module that preserves decimal commas and groups
   time/force/displacement columns into replicates.
2. Characterise instrumental noise from the early displacement window; estimate
   the dominant band via FFT; derive a dataset‑level peak and apply a zero‑phase
   Butterworth low‑pass filter to all replicates.
3. Estimate sampling rate from time deltas; set a long Savitzky–Golay window in
   seconds (converted to samples) to compute the baseline.
4. Restrict analysis to the displacement window; compute residuals; detect
   absolute excursions above the threshold and group contiguous exceedances.
5. Report peak sample per group; optionally render publication‑grade PNG plots
   showing filtered force and baseline plus the residual with threshold lines.

## Operating constraints
- Assumes the CSV export uses the standard three-row header and comma decimals.
- Designed for ~100 Hz sampling; unusual rates work so long as enough samples are
  available to fit the requested Savitzky–Golay window.
- Output is console-only; redirection to a file is left to the caller.
