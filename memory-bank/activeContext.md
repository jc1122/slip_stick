# Active context

## Current work focus
All effort centres on `slipstick.py`. The script now:
- Estimates a dataset-level instrumental noise band from the early (1–5 mm)
  window and applies zero‑phase low‑pass filtering.
- Uses a long Savitzky–Golay window (50% of the trimmed trace, minimum 4 s)
  to estimate the baseline, then detects residual peaks.
- Normalises forces to `cN / 25 mm` for reporting; threshold defaults to
  1.4 cN/25 mm.
- Produces publication-ready plots with consistent styling and dataset labels.
Summaries can be redirected to text files for archival alongside the plots.

## Operating constraints
- Assume the CSV layout documented in the project brief.
- Keep the script dependency footprint minimal (NumPy and SciPy required).

## Possible next steps
- Expose alternative displacement windows or interpolation for sparse datasets.
- Add machine-readable outputs (CSV/JSON) for downstream analysis.
