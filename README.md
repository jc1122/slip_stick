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
- `--noise-disp-min`: lower displacement bound (mm) for the instrumental-noise
  window (defaults to 1 mm).
- `--noise-disp-max`: upper displacement bound (mm) for the instrumental-noise
  window (defaults to 5 mm). The script detrends the force in this window with a
  long Savitzky–Golay filter (window ≈ ¼ of the displacement span) before
  reporting noise statistics.
- `--noise-plot-dir`: directory for PNG plots of the inferred noise. Each
  replicate plot shows the raw force, SavGol baseline, and detrended residual
  histogram; a dataset-level summary gathers bias and residual spread (requires
  matplotlib).
- `--noise-force-max`: optional absolute force bound (N) that filters the noise
  window to quieter samples.
- `--noise-min-samples`: minimum number of samples used to characterise the
  noise window (defaults to 40, with a fallback to the earliest samples if the
  displacement bound supplies fewer points).
- `--noise-force-onset`: absolute force (N) that marks the onset of specimen
  engagement. Samples at or above this force are excluded from the noise window
  (defaults to 0.2 N).

Noise statistics are printed per replicate alongside the spike summary and
collated per dataset to help tune detection thresholds.

### Instrumental noise estimation

The first few millimetres of displacement (default 1–5 mm) are assumed to
contain only instrumental noise. Inside that window the script:

1. Filters out any samples whose absolute force exceeds `--noise-force-onset`
   (default 0.2 N) or, if provided, `--noise-force-max`.
2. Fits a Savitzky–Golay baseline with a long window (≈ ¼ of the remaining
   displacement span) to remove gradual ramps that precede the peel.
3. Treats the residual about that baseline as pure noise.

Per replicate the report provides:

- `bias`: the mean level of the SavGol baseline (instrument zero error).
- `std`: residual standard deviation after detrending.
- `max_abs`: the extreme residual excursion observed.
- `n`: the number of noise samples that satisfied the filters.

When `--noise-plot-dir` is set, each PNG highlights the bias (green dotted
line), raw vs baseline force traces, and the residual-force histogram, while the
dataset summary plot stacks the biases and residual spreads for quick
comparison. Use these plots to assess whether the tester was correctly zeroed
and to decide on appropriate spike-detection thresholds.

Output is a short report per replicate listing the time, displacement, and
residual amplitude of each spike above the threshold. If no spikes are found in
that window the replicate is marked clean.

A per-dataset summary follows at the end, listing the spike count detected in
each replicate plus the dataset total.

Use the generated summaries (e.g., redirect to `summaries/<dataset>.txt`) to
store results alongside the PNG plots:

```bash
python slipstick.py --input datasets/<file>.csv --plot-dir plots > summaries/<file>.txt
```

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
