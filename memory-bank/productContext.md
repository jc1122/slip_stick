# Product context

## Purpose
Offer a quick way to highlight potential slip–stick events in FTM 10 tensile
CSV files without maintaining a large toolkit.

## Problems solved
- Reads the known CSV format and extracts each replicate as standard NumPy
  arrays.
- Separates instrumental noise (dataset-level FFT-derived band) from specimen
  signal, and applies a zero-phase 4th-order Butterworth low-pass filter.
- Removes the slow peel trend so spikes stand out in the residual.
- Flags residual excursions above a small force threshold (default 1.4 cN/25 mm;
  configurable via `--threshold`).
- Normalises forces from the collection width to a reporting width (default
  25 mm) and presents values in `cN` by default for readability.
- Optionally saves per-replicate PNG plots (via `--plot-dir`) with spikes
  annotated, provided matplotlib is available.

## How it works
`slipstick.cli` parses the CSV; rescales forces to the reporting width/unit; uses
the early (1–5 mm) window to estimate noise and a common instrument band per
dataset; applies zero-phase low-pass filtering; keeps the 50–200 mm window;
fits a Savitzky–Golay baseline; computes residuals; and groups contiguous
exceedances above the threshold, reporting the peak sample per group.

## User experience goals
- Single command invocation with a handful of optional flags.
- Console output that is easy to copy into reports or spreadsheets.
- Defaults that work out of the box for typical ~100 Hz datasets, with outputs
  formatted for publication (consistent colours, titles, and cN/25 mm axes).
