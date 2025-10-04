# System patterns

## Repository layout
- Top-level `slipstick.py` contains the entire pipeline (CSV loader, Savitzky–Golay
  smoother, spike detector, CLI).
- `memory-bank/` stores lightweight documentation of scope, context, and progress.
- `datasets/` is an optional landing zone for CSV files; the script accepts any
  path supplied via `--input`.

## Processing pattern
1. Load the CSV with a tiny custom parser that normalises decimal commas and
   groups columns into replicates.
2. Estimate the sampling rate from time differences to derive the Savitzky–Golay
   window length from seconds.
3. Restrict samples to the displacement window, smooth the force trace, subtract
   the baseline, and locate residual peaks higher than the threshold.
4. Collapse contiguous exceedances to a single spike event and print the summary.
5. When requested, render PNG plots showing force/baseline and residual traces
   with spike markers.

## Operating constraints
- Assumes the CSV export uses the standard three-row header and comma decimals.
- Designed for ~100 Hz sampling; unusual rates work so long as enough samples are
  available to fit the requested Savitzky–Golay window.
- Output is console-only; redirection to a file is left to the caller.
