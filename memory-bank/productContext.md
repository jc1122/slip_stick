# Product context

## Purpose
Offer a quick way to highlight potential slip–stick events in FTM 10 tensile
CSV files without maintaining a large toolkit.

## Problems solved
- Reads the known CSV format and extracts each replicate as standard NumPy
  arrays.
- Removes the slow peel trend so spikes stand out in the residual.
- Flags residual excursions above a small force threshold (0.05 N by default).
- Optionally saves per-replicate PNG plots (via `--plot-dir`) with spikes
  annotated, provided matplotlib is available.

## How it works
`slipstick.py` parses the CSV, keeps samples whose displacement is between 50
and 200 mm, fits a Savitzky–Golay baseline, subtracts it from the force signal,
and groups contiguous samples whose absolute residual is above the threshold.
The peak sample per group is reported.

## User experience goals
- Single command invocation with a handful of optional flags.
- Console output that is easy to copy into reports or spreadsheets.
- Defaults that work out of the box for typical ~100 Hz datasets.
