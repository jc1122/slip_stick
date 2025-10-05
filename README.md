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
- `--threshold`: absolute residual force threshold (default 0.014 in the reporting units).
- `--plot-dir`: directory for PNG plots with spikes marked (requires matplotlib).
  Plots show force and baseline against displacement plus the residual trace.
- `--noise-disp-min`: lower displacement bound (mm) for the instrumental-noise
  window (defaults to 1 mm).
- `--noise-disp-max`: upper displacement bound (mm) for the instrumental-noise
  window (defaults to 5 mm). The script detrends the force in this window with a
  long Savitzky–Golay filter (window ≈ ½ of the displacement span) before
  reporting noise statistics.
- `--noise-plot-dir`: directory for PNG plots of the inferred noise. Each
  replicate plot shows the raw force against the SavGol baseline, the detrended
  residual trace, and a residual-force histogram; a dataset-level summary
  gathers bias and residual spread (requires
  matplotlib).
- `--noise-force-max`: optional absolute force bound (N) that filters the noise
  window to quieter samples.
- `--noise-min-samples`: minimum number of samples used to characterise the
  noise window (defaults to 40, with a fallback to the earliest samples if the
  displacement bound supplies fewer points).
- `--noise-force-onset`: absolute force (N) that marks the onset of specimen
  engagement. Samples at or above this force are excluded from the noise window
  (defaults to 0.2 N).
- `--instrument-peak-hz`: override for the global instrumental-noise peak (Hz).
- `--instrument-cutoff-hz`: override for the low-pass cutoff used during
  denoising (Hz). When omitted the script derives the cutoff from the measured
  peak and the `--instrument-cutoff-factor` (default 0.8).
- `--instrument-cutoff-factor`: scaling factor applied to the common peak when
  computing the cutoff (default 0.8).
- `--collection-width-mm`: specimen width (mm) that the source data was
  normalised to (default 90 mm).
- `--report-width-mm`: target width (mm) for reporting (default 25 mm). Forces
  and residuals are automatically rescaled and all outputs are expressed in
  `<report-unit> / <report-width>`.
- `--report-unit`: unit used for reporting (default `cN`). Choose `N` to keep
  SI newtons or `cN` to scale values by ×100 for easier readability.

Noise statistics are printed per replicate alongside the spike summary and
collated per dataset to help tune detection thresholds. The script first
collects the noise windows for every replicate, infers the dominant
instrumental-noise peak shared by the machine (median of the replicate peaks),
then applies a consistent 4th-order Butterworth low-pass filter derived from
that peak to every replicate force trace. Forces are rescaled from the
collection width to the reporting width before analysis, so summaries, plots,
and thresholds are expressed in `<report-unit> / <report-width>` (bias is still
reported, not removed); the chosen peak/cutoff is echoed in the summaries for
traceability.

### Instrumental noise estimation

The first few millimetres of displacement (default 1–5 mm) are assumed to
contain only instrumental noise. Inside that window the script:

1. Filters out any samples whose absolute force exceeds `--noise-force-onset`
   (default 0.2 N) or, if provided, `--noise-force-max`.
2. Fits a Savitzky–Golay baseline with a long window (≈ ½ of the remaining
   displacement span) to remove gradual ramps that precede the peel.
3. Treats the residual about that baseline as pure noise.

Per replicate the report provides:

- `bias`: the mean level of the SavGol baseline (instrument zero error).
- `std`: residual standard deviation after detrending.
- `max_abs`: the extreme residual excursion observed.
- `n`: the number of noise samples that satisfied the filters.

When `--noise-plot-dir` is set, each PNG combines the raw and baseline force
traces with a detrended residual plot and residual-force histogram, while the
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

## Usage

Typical end-to-end invocation (publication-ready defaults):

```bash
# Analyse one dataset with denoising, cN/25 mm reporting, and plots
python slipstick.py \
  --input datasets/<file>.csv \
  --plot-dir plots \
  --noise-plot-dir noise_plots \
  --collection-width-mm 90 \
  --report-width-mm 25 \
  --report-unit cN \
  --threshold 0.014 \
  > summaries/<file>.txt
```

Batch process all CSVs under `datasets/` (Bash):

```bash
for f in datasets/*.csv; do \
  base=$(basename "$f" .csv); \
  python slipstick.py --input "$f" \
    --plot-dir plots --noise-plot-dir noise_plots \
    --collection-width-mm 90 --report-width-mm 25 --report-unit cN \
    --threshold 0.014 \
    > "summaries/${base}.txt"; \
done
```

Notes:

- The script normalises forces from the collection width to the reporting
  width, and presents values in the chosen `--report-unit`.
- `--threshold` is applied in reporting units (default `0.014` ≡ 1.4 cN/25 mm).
- Denoising is derived from a dataset-level, machine-dependent noise band and
  applied consistently to all replicates in that dataset.

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
