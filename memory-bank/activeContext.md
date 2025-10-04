# Active context

## Current work focus
The repository revolves around the single script (`slipstick.py`). A recent update
added optional PNG plots (`--plot-dir`) that mark the force baseline, residual,
and detected spikes per replicate when matplotlib is available.

## Operating constraints
- Assume the CSV layout documented in the project brief.
- Keep the script dependency footprint minimal (NumPy required, SciPy optional).

## Possible next steps
- Validate the plotting output once matplotlib is available in the environment.
- Consider adding a CSV/JSON spike summary export if users need machine-readable
  results.
