# Slip-stick spike finder

`slipstick.py` is a small command-line helper for spotting slip–stick spikes in
FTM 10 tensile tester exports. The script assumes the standard CSV structure
(three header rows with replicate labels, time/force/displacement columns, and
comma decimals) and keeps the workflow to three steps:

1. Load every replicate from the CSV file.
2. Trim each trace to the 50–200 mm displacement window and estimate a smooth
   baseline with a Savitzky–Golay filter.
3. Report points where the detrended force exceeds the chosen threshold.

## Quick start

```bash
python slipstick.py --input path/to/tensile.csv
```

Optional flags:

- `--disp-min` / `--disp-max`: displacement window (defaults 50–200 mm).
- `--window-seconds`: Savitzky–Golay window length in seconds. Defaults to a long
  window equal to 50% of the trimmed trace duration (minimum 4 s).
- `--polyorder`: Savitzky–Golay polynomial order (default 3).
- `--threshold`: absolute residual force threshold (default 0.05 N).
- `--plot-dir`: directory for PNG plots with spikes marked (requires matplotlib).
  Plots show force and baseline against displacement plus the residual trace.

Output is a short report per replicate listing the time, displacement, and
residual amplitude of each spike above the threshold. If no spikes are found in
that window the replicate is marked clean.

## Dependencies

- Python 3.11+
- NumPy (required)
- SciPy (required for Savitzky–Golay detrending)
- Matplotlib (optional — required only when using `--plot-dir` to emit PNG plots)

Install the required libraries with:

```bash
python -m pip install -r requirements.txt
```

Add `matplotlib` if you plan to generate plots:

```bash
python -m pip install matplotlib
```

## Data

Place CSV files under `datasets/` or pass absolute paths. The script never
writes back to the datasets directory – results are printed to the console so
you can redirect them to a file if needed.
