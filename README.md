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
- Decimal separator is a comma; headers are quoted and span three rows (group label,
  column name, unit).
- Agents preview at most 100 lines from any CSV to preserve context, but scripts will
  process entire files.

## Current focus
1. Validate parsed replicates across external/internal datasets and capture edge
   cases (missing columns, extra replicates) in metadata.
2. Design the frequency-aware filtering and onset detection pipeline that rides on
   the tidy `df_long` output (band-pass, envelope, hysteresis rules).
3. Document CLI workflows and integrate the parser outputs into the planned
   decomposition + detection notebooks.

## Parser CLI and API
- Module entrypoint: `python -m slip_stick.parse_ftm10 --input <file> [flags]`.
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
  python -m slip_stick.parse_ftm10 --input tests/fixtures/ftm10_external_head.csv \
    --summary --preview-lines 80
  ```
  Example with outputs:
  ```bash
  python -m slip_stick.parse_ftm10 --input t2en-crosil-42-external.csv \
    --summary --out outputs/external
  ```

## Detection scaffold
- Module: `src/slip_stick/detect.py` implements two primitives:
  - `estimate_midband_welch(y, fs)` to locate the mid‑band (dominant peak + −3 dB edges).
  - `decompose_complementary(y, fs, f1, f2)` for a lossless split into low/mid/high
    via complementary raised‑cosine filters (low + mid + high = original).
- CLI (scaffold): `python -m slip_stick.detect_cli --input <file> [--estimate-bands] \
  [--rep <id|index>] [--f1 <Hz>] [--f2 <Hz>] [--write-npz <path>]`.
- Example:
  ```bash
  PYTHONPATH=src python -m slip_stick.detect_cli \
    --input t2en-crosil-42-external.csv --rep 1 --estimate-bands \
    --write-npz outputs/rep1_components
  ```

## Development workflow
1. Create a virtual environment:
   ```bash
   python -m venv .venv
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
