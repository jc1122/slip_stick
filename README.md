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
1. Parse all replicates from the raw CSVs into a canonical long format with
   `replicate_id`, `time_s`, `force_N`, and `disp_mm` columns.
2. Compute per replicate diagnostics (dt median, dt std, sampling rate, NaN counts,
   sample totals) and provide summary output via CLI.
3. Establish reversible decomposition methods (wavelet MRA by default, VMD optional)
   that separate low frequency peel, mid frequency slip–stick, and high frequency
   noise components without losing information (components must reconstruct the
   original signal).

## Planned CLI and API
- Module entrypoint: `python -m slip_stick.parse_ftm10 --input <file> --summary`.
- Outputs: textual summary to stdout plus optional Parquet dataset and JSON metadata
  (`--out parsed.parquet` stores both `.parquet` and `.json`).
- Library API (planned): `load_ftm10_csv(path) -> (df_long, metadata)`.

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

## Tooling baseline (to be implemented)
- `pyproject.toml` with ruff (lint) and black (format) configuration.
- `.pre-commit-config.yaml` with hooks for ruff, black, trailing whitespace, end of file
  fixer, and YAML/TOML/JSON checks.
- Pytest fixtures containing small representative CSV slices for deterministic tests.
- Continuous documentation updates in `memory-bank/` following the dependency order.

## Roadmap
1. Scaffold package structure (`src/slip_stick/`, `tests/`, `pyproject.toml`).
2. Implement CSV loader and CLI with full replicate support and diagnostics.
3. Add decomposition module (wavelet MRA) plus metrics for each component.
4. Integrate adaptive onset detection leveraging the mid band energy with hysteresis.
5. Document usage patterns, defaults, and extend to internal dataset validation.

## Contributing
- Keep prose ASCII and wrap lines near 100 characters.
- Reference affected files in commit messages (e.g., `docs: update active context`).
- Update `memory-bank/progress.md` and `memory-bank/activeContext.md` after significant
  changes.
- Run `pre-commit run -a` and `pytest` before committing.
