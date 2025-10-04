# Project brief

## Overview
This repo now focuses on a single, lightweight script that detects slip–stick
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
Only the `slipstick.py` script and its supporting README/Memory Bank remain in
scope. All previous detection scaffolds, extensive documentation, tests, and
auxiliary scripts have been removed to keep the repository lean.
