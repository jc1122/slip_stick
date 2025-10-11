# Slip-stick spike finder

`slipstick.py` is a command-line helper for spotting slip–stick spikes in fixed-format
FTM 10 CSV exports. It:

- streams each replicate from the CSV (time, force, displacement) and rescales forces
  to the requested reporting width/unit,
- trims the trace to a configurable displacement window (default 50–200 mm),
- estimates and subtracts a smooth Savitzky–Golay baseline,
- applies an instrumental-noise-aware low-pass filter before spike detection, and
- reports residual excursions above a force threshold (defaults to 1.4 cN / 25 mm).

Optionally it renders per-replicate plots and noise diagnostics with a parallel
matplotlib backend (default 4 worker processes), which keeps batch workflows fast.

---

## Quick start

```bash
python slipstick.py --input datasets/20250317_C1E_rossella_internal.csv
```

The command prints replicate summaries (noise statistics + spike list) and a
dataset-level total. To archive the text output, redirect the CLI to `summaries/`.

```bash
python slipstick.py --input datasets/<file>.csv > summaries/<file>.txt
```

---

## CLI reference

| Flag | Description | Default |
|------|-------------|---------|
| `--input`, `-i` | Path to the CSV file (required). | – |
| `--disp-min` | Lower displacement bound (mm). | `50.0` |
| `--disp-max` | Upper displacement bound (mm). | `200.0` |
| `--window-seconds` | Savitzky–Golay window length in seconds (rounded to nearest odd sample count). If omitted, uses 50% of the trimmed trace, min 4 s. | auto |
| `--polyorder` | Savitzky–Golay polynomial order. | `3` |
| `--threshold` | Residual spike threshold in reporting units. The internal default is `0.0504 N`, equivalent to **1.4 cN / 25 mm** after scaling. | auto |
| `--plot-dir` | Directory for analysis plots (force, baseline, residual). Creates `<dataset>_<replicate>.<ext>`. | not saved |
| `--plot-workers` | Number of processes for plot generation. Useful values are 2–6; the default of 4 balances throughput and memory. | `4` |
| `--plot-format` | Plot image format: `png`, `pdf`, or `svg`. | `png` |
| `--noise-plot-dir` | Directory for instrumental-noise plots plus dataset summary. | not saved |
| `--noise-disp-min` | Lower displacement bound (mm) for the noise window. | `1.0` |
| `--noise-disp-max` | Upper displacement bound (mm) for the noise window. | `5.0` |
| `--noise-force-max` | Optional absolute force limit (in reporting units) to keep quiet samples in the noise window. | none |
| `--noise-min-samples` | Minimum number of samples used to characterise the noise window (falls back to earliest samples). | `40` |
| `--noise-force-onset` | Absolute force (reporting units) that marks first specimen contact; samples above this are excluded from the noise estimate. | `0.2 N` at collection width |
| `--instrument-peak-hz` | Global instrumental noise peak (Hz). Overrides replicate-level peak detection. | auto |
| `--instrument-cutoff-hz` | Explicit low-pass cutoff (Hz). Overrides the derived cutoff. | auto |
| `--instrument-cutoff-factor` | Scale factor applied to the common peak when deriving the low-pass cutoff. | `0.8` |
| `--collection-width-mm` | Specimen width used to normalise the raw forces. | `90.0` |
| `--report-width-mm` | Target width for reporting (forces are linearly rescaled). | `25.0` |
| `--report-unit` | Output force unit: `N` or `cN`. | `cN` |

Notes:

- Any force threshold/gating argument is interpreted in the reporting width/unit.
- When `--plot-dir` or `--noise-plot-dir` is supplied, the script spawns a pool of
  worker processes; the job queue is flushed before returning, and failures bubble up.
- Vector formats (`--plot-format pdf`/`svg`) can be combined with Cairo backends, e.g.
  `MPLBACKEND=module://mplcairo.base python slipstick.py ...`.

---

## Usage examples

### Single dataset with plots

```bash
python slipstick.py \
  --input datasets/20250617_C1E_dolpap_external.csv \
  --plot-dir plots/full_run/20250617_C1E_dolpap_external \
  --noise-plot-dir noise_plots/full_run/20250617_C1E_dolpap_external
```

### Publication-friendly vector output

```bash
MPLBACKEND=module://mplcairo.base \
python slipstick.py \
  --input datasets/20250318_C1E_rossella_external.csv \
  --plot-dir plots/pdf/20250318_C1E_rossella_external \
  --noise-plot-dir noise_plots/pdf/20250318_C1E_rossella_external \
  --plot-format pdf \
  --plot-workers 4
```

### Batch all datasets

```bash
for f in datasets/*.csv; do
  stem=$(basename "$f" .csv)
  python slipstick.py \
    --input "$f" \
    --plot-dir "plots/full_run/$stem" \
    --noise-plot-dir "noise_plots/full_run/$stem" \
    --plot-workers 4 \
    > "summaries/$stem.txt"
done
```

---

## Instrumental-noise workflow (summary)

1. Gather samples inside `--noise-disp-min/max` before specimen engagement.
2. Optionally clip by `--noise-force-max` and `--noise-force-onset`.
3. Remove slow ramps with a long Savitzky–Golay filter and compute residual stats
   (bias, standard deviation, max absolute residual).
4. Estimate the dominant noise peak via FFT. The median peak across replicates
   defines a Butterworth low-pass filter (scaled by `--instrument-cutoff-factor`).
5. Apply the filter to every replicate before baseline fitting and peak detection.

Per-replicate and dataset-level summaries print the key noise metrics and the
applied cutoff so you can confirm the analysis band quickly.

---

## Performance tips

- Leaving `--plot-workers` at 4 is a good default. Increase to ~6 if you have spare
  CPU/RAM, or reduce to 1 when running in very tight environments.
- Vector formats (PDF/SVG) typically render faster when using the Cairo backend
  (`MPLBACKEND=module://mplcairo.base`) because they avoid rasterisation overhead.
- The CSV loader streams rows, so memory use scales with the number of active replicates,
  not the total row count.

---

## Dependencies

- Python 3.9+
- NumPy
- SciPy
- Matplotlib (only required when using `--plot-dir` and/or `--noise-plot-dir`)
- Optional: `mplcairo` for fast vector backends (`pip install mplcairo`)

Install the essentials with:

```bash
python -m pip install -r requirements.txt
```

---

## Data layout

Place raw CSV files in `datasets/` (or supply absolute paths). The tool never mutates
the input files; all artefacts are written to the directories you pass via the CLI
and the textual summary goes to stdout.
