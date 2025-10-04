# Tech context

## Dependencies
- Python 3.11+
- NumPy for array handling and linear algebra
- Optional SciPy (`scipy.signal.savgol_filter`) for faster Savitzky–Golay smoothing
- Optional matplotlib for writing spike-marked PNG plots when `--plot-dir` is used

## Script structure
- CSV parsing relies on Python's built-in `csv` module with minor preprocessing to
  handle decimal commas and quoted headers.
- Savitzky–Golay coefficients fall back to a NumPy implementation if SciPy is not
  available.
- Spike grouping is performed with NumPy boolean masks and `np.split` to separate
  contiguous regions.

## Usage
Run the script directly with `python slipstick.py --input <path>` and adjust
CLI flags for displacement range, smoothing window, or threshold as needed.
