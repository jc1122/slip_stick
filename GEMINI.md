
# GEMINI.md

This file contains the collected memory of the project.

## activeContext.md

# Active context

## Current work focus
The codebase is now a Python package (`slipstick`). The CLI entry point is `slipstick.cli`. The package now:
- Estimates a dataset-level instrumental noise band from the early (1–5 mm)
  window and applies zero‑phase low‑pass filtering.
- Uses a long Savitzky–Golay window (50% of the trimmed trace, minimum 4 s)
  to estimate the baseline, then detects residual peaks.
- Normalises forces to `cN / 25 mm` for reporting; threshold defaults to
  1.4 cN/25 mm.
- Produces publication-ready plots with consistent styling and dataset labels.
- Streams CSV rows to avoid duplicate parsing and rescales forces in place.
- Generates plots in parallel (default four worker processes) and supports PDF/SVG.
Summaries can be redirected to text files for archival alongside the plots.

## Operating constraints
- Assume the CSV layout documented in the project brief.
- Keep the script dependency footprint minimal (NumPy and SciPy required).

## Possible next steps
- Expose alternative displacement windows or interpolation for sparse datasets.
- Add machine-readable outputs (CSV/JSON) for downstream analysis.

## productContext.md

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

## progress.md

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

## projectbrief.md

# Project brief

## Overview
This repo now focuses on a small, lightweight Python package that detects slip–stick
spikes in FTM 10 tensile tester CSV exports. The workflow is limited to loading
the fixed-format file, detrending the 50–200 mm displacement segment with a
Savitzky–Golay filter, and flagging residual force spikes.

## Requirements
- Assume the vendor CSV layout (three header rows, comma decimals, replicate
  blocks consisting of time/force/displacement columns).
- Limit analysis to the 50–200 mm displacement window.
- Apply Savitzky–Golay smoothing to obtain a baseline and subtract it from the
  force trace.
- Report every point where the absolute residual exceeds a configurable
  threshold (default 0.05 N).
- Optionally render simple plots that highlight the baseline, residual, and
  detected spikes for each replicate.

## Goals
- Keep the codebase small (single script plus brief documentation).
- Minimise dependencies (NumPy required, SciPy optional).
- Provide clear CLI usage instructions and sensible defaults.

## Scope
Only the `slipstick` package and its supporting README/Memory Bank remain in
scope. All previous detection scaffolds, extensive documentation, tests, and
auxiliary scripts have been removed to keep the repository lean.

## systemPatterns.md

# System patterns

## Repository layout
- `slipstick/` contains the entire pipeline, split into modules for I/O, core logic, plotting, and CLI.
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

## techContext.md

# Tech context

## Dependencies
- Python 3.11+
- NumPy for array handling and linear algebra
- SciPy (`scipy.signal.savgol_filter`) for Savitzky–Golay smoothing
- Optional matplotlib for writing spike-marked PNG plots when `--plot-dir` is used

Install mandatory dependencies with `python -m pip install -r requirements.txt`; add
`matplotlib` separately if you need plot output.

## Script structure
- The `slipstick` package is organized into modules for models, I/O, core logic, and plotting.
- The main CLI entry point is `slipstick.cli`.
- CSV parsing relies on Python's built-in `csv` module with minor preprocessing to
  handle decimal commas and quoted headers.
- Savitzky–Golay smoothing always uses SciPy's implementation.
- Spike grouping is performed with NumPy boolean masks and `np.split` to separate
  contiguous regions.

## Usage
Run the script directly with `python -m slipstick.cli --input <path>` and adjust
CLI flags for displacement range, smoothing window, or threshold as needed.
