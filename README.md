# slip_stick FTM 10 onset detection

## Overview
Slip_stick builds reproducible tooling for finding the onset of the slip–stick
phenomenon in FTM 10 tensile tester data. The project is documentation first and uses
the Memory Bank in `memory-bank/` to track decisions, constraints, and active work.

## Data characteristics
- Source files: `t2en-crosil-42-*.csv` from the tensile tester.
- Each CSV contains multiple replicates (10 in the external dataset), arranged as
  repeated blocks of three columns: time (`Czas`/`sec`), force (`Siła`/`N`), and
  displacement (`Przemieszczenie`/`mm`).
- Sampling rate is approximately 100 Hz (derived from the `Czas` column increments).
- Files decode cleanly with CP1250 encoding; this preserves Polish diacritics in the
  headers.
- Decimal separator is a comma; headers are quoted and span three rows (group label,
  column name, unit).
- Agents preview at most 100 lines from any CSV to preserve context, but scripts will
  process entire files.
- External runs contain the full ~60 s pull per replicate, while the internal export
  terminates around 54–57 s because several hundred blank timestamp rows are dropped.

## Current focus
1. Validate parsed replicates across external/internal datasets and capture edge
   cases (missing columns, extra replicates) in metadata.
2. Design the frequency-aware filtering and onset detection pipeline that rides on
   the tidy `df_long` output (band-pass, envelope, hysteresis rules).
3. Document CLI workflows and integrate the parser outputs into the planned
   decomposition + detection notebooks.

## Parser CLI and API
- Module entrypoint: `python3.11 -m slip_stick.parse_ftm10 --input <file> [flags]` (use
  Python 3.11+ so the parser can rely on `zip(..., strict=True)`).
- Flags:
  - `--summary` prints replicate counts, sampling stats, and NaN totals.
  - `--out PATH` writes `<PATH>.parquet` (tidy data) and `<PATH>.metadata.json`.
  - `--preview-lines`, `--decimal-comma`, `--decimal-dot`, and `--header-rows`
    allow manual overrides when sniffing unusual files.
  - `--quiet`/`--verbose` adjust logging; `--version` reports the package version.
- Library API: `load_ftm10_csv(path, preview_lines=100, *, decimal_override=None,
  header_rows_override=None) -> (df_long, metadata)`.
- Example summary:
  ```bash
  python3.11 -m slip_stick.parse_ftm10 --input tests/fixtures/ftm10_external_head.csv \
    --summary --preview-lines 80
  ```
  Example with outputs:
  ```bash
  python3.11 -m slip_stick.parse_ftm10 --input t2en-crosil-42-external.csv \
    --summary --out outputs/external
  ```

## Detection scaffold
- Module: `src/slip_stick/detect.py` implements two primitives:
  - `estimate_midband_welch(y, fs, *, baseline_window=None, ...) -> BandEstimate`
    wraps a Welch PSD, smooths the spectrum, and reports `f1`, `f2`, `f_c`, and diagnostics
    (segment count, bandwidth, optional baseline peak ratios).
  - `decompose_complementary(y, fs, f1, f2, ...) -> DecompositionResult` performs the
    lossless low/mid/high split (raised‑cosine filters) and returns components plus energy
    partition metrics and reconstruction RMS.
- CLI (scaffold): `python -m slip_stick.detect_cli --input <file> [--estimate-bands] \
  [--rep <id|index> | --all-reps] [--f1 <Hz>] [--f2 <Hz>] [--write-npz <path>] \
  [--write-json <path>]`.
- Example:
  ```bash
  PYTHONPATH=src python -m slip_stick.detect_cli \
    --input t2en-crosil-42-external.csv --rep 1 --estimate-bands \
    --write-npz outputs/rep1_components
  ```
  Multi-replicate summary with JSON diagnostics:
  ```bash
  PYTHONPATH=src python -m slip_stick.detect_cli \
    --input t2en-crosil-42-external.csv --all-reps --estimate-bands \
    --write-json outputs/external_summary.json
  ```

## Savitzky–Golay workflow
- Detrending and visualisation are handled by `scripts/detrend_savgol.py`. The default
  configuration uses displacement on the x-axis and a 50–200 mm window to isolate
  slip–stick spikes while keeping the peel baseline flat.
- `scripts/run_savgol_workflow.py` orchestrates the full analysis:
  ```bash
  python3.12 scripts/run_savgol_workflow.py \
    --window-seconds 5.0 --polyorder 3 --distance-range 50 200 \
    --summary-json outputs/savgol/workflow_summary.json
  ```
  The script performs three steps in sequence:
  1. Detrend every dataset into `outputs/savgol/<dataset>/`, writing NPZ payloads and SVG
     overlays (original, baseline, residual) keyed by replicate.
  2. Compute mean force across 50–200 mm and scale by `25/90`; results appear in the CLI
     output and in the JSON summary.
  3. Analyse residual spikes with thresholds `ratio ≥ 10` and `|residual| ≥ 0.05 N`,
     flagging replicates that exhibit slip–stick bursts. Per-replicate metrics are stored in
     `outputs/savgol/residual_spike_summary.json` and included in the workflow summary.
- The individual building blocks remain available:
  - `scripts/average_force.py` reports mean/ scaled force for a displacement window.
  - `scripts/analyze_residual_spikes.py` inspects NPZ residuals and highlights spike
    candidates with configurable thresholds.

## Development workflow
1. Create a virtual environment (Python 3.11+):
  ```bash
  python3.11 -m venv .venv
  source .venv/bin/activate
  python -m pip install -U pip
  ```
2. Install the project in editable mode with dev extras (once the packaging scaffold
   is committed):
   ```bash
   pip install -e .[dev]
   ```
3. Activate pre commit hooks:
   ```bash
   pre-commit install
   pre-commit run -a
   ```
4. Run the test suite:
   ```bash
   pytest -q
   ```

## Tooling baseline
- `pyproject.toml` with ruff (lint) and black (format) configuration, pytest defaults,
  and optional dev extras.
- `.pre-commit-config.yaml` with hooks for ruff, black, trailing whitespace,
  end-of-file fixer, and YAML/TOML/JSON checks.
- Pytest suite covering header sniffing, decimal parsing, replicate grouping, long
  format integrity, and CLI summary output (fixtures live in `tests/fixtures/`).
- Continuous documentation updates in `memory-bank/` following the dependency order.

## Roadmap
1. Scaffold package structure (`src/slip_stick/`, `tests/`, `pyproject.toml`) — done.
2. Implement CSV loader and CLI with full replicate support and diagnostics — done.
3. Add decomposition module and band estimation — scaffolded (see `detect.py`).
4. Integrate adaptive onset detection leveraging the mid band energy with hysteresis.
5. Document usage patterns, defaults, and extend to internal dataset validation.
6. Automate regression tests that span external/internal datasets and persist
   baseline metadata snapshots.

## Contributing
- Keep prose ASCII and wrap lines near 100 characters.
- Reference affected files in commit messages (e.g., `docs: update active context`).
- Update `memory-bank/progress.md` and `memory-bank/activeContext.md` after significant
  changes.
- Run `pre-commit run -a` and `pytest` before committing.
