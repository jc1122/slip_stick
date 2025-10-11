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
