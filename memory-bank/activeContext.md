# Active context

## Current work focus
All effort centres on `slipstick.py`. The script now defaults to a long
Savitzky–Golay window (50% of the trimmed trace, minimum 4 s), stabilises the
manual SavGol fallback, and produces force-vs-displacement plots (baseline plus
residual with spike markers) when `--plot-dir` is used.

## Operating constraints
- Assume the CSV layout documented in the project brief.
- Keep the script dependency footprint minimal (NumPy required, SciPy optional).

## Possible next steps
- Decide whether to expose alternative displacement windows or interpolation for
  sparse datasets.
- Consider adding machine-readable summaries (CSV/JSON) if reporting needs grow.
