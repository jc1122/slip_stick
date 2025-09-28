# Active context

## Current work focus
Prepare a plan and workflow for FTM 10 data processing to detect the onset of the
slip–stick phenomenon in tensile tester data. Define filtering strategy to separate
low‑frequency peel, mid‑frequency slip–stick, and high‑frequency instrumental noise.

## Operating constraints (agent)
- The coding agent should only preview at most 100 lines from any CSV to avoid
  overflowing the context window. The processing script itself will read full files.
- All data characteristics (columns, units, sampling rate) will be inferred directly
  from the CSV files rather than relying on prior assumptions.

## Near‑term next steps
- Derive a frequency‑aware filtering pipeline and onset detection criterion.
- Validate assumptions on a small preview (≤100 lines) from the uploaded CSVs.
- Outline CLI design, parameters, and outputs for the detection script.

## Action plan — parsing phase
- Parse CSV dialect and headers for all replicates.
- Normalize names/units; extract all 3‑column replicate blocks.
- Convert to numeric; build canonical long format with `replicate_id`.
- Validate timebase (monotonic), compute dt stats and Fs per replicate.
- CLI summary output and optional Parquet + JSON metadata export.
- Add tests for each step; scaffold dev tooling (ruff, black, pre‑commit).

### Tasks (actionable)
- Add Python scaffolding: `src/slip_stick/` and tests with pytest.
- Implement `load_ftm10_csv(path)` returning `(df_long, metadata)`.
- Build CLI `parse_ftm10.py` with `--input`, `--summary`, `--out`.
- Handle decimal comma, quotes, 3‑row headers, and replicate detection.
- Create small CSV fixtures (2–3 replicates) for unit tests.
- Compute per‑replicate metrics: `dt_median`, `dt_std`, `Fs`, `n_samples`, `n_nans`.
- Write Parquet and JSON metadata when `--out` is provided.
- Add ruff + black configs in `pyproject.toml`; set sensible defaults.
- Add `.pre-commit-config.yaml` and enable hooks; document commands.

### Tests (initial)
- `test_header_parsing()` detects 3‑row header and maps names/units.
- `test_decimal_comma_parsing()` loads numeric values correctly.
- `test_replicates_count()` finds all replicate blocks.
- `test_timebase_stats()` verifies monotonic time and Fs ≈ 100 Hz (tolerance).
- `test_long_format_shape()` checks columns and row counts.
- `test_cli_summary()` runs `--summary` on fixture and checks key lines.

### Dev tooling (to implement next)
- Ruff: enable linting and `--fix`; default select `E,F,W,I` and `B` if using flake8‑bugbear.
- Black: line length 100, target Python 3.10+.
- Pre‑commit: ruff, black, end‑of‑file‑fixer, trailing‑whitespace, check‑yaml/toml/json.

### Example commands
```bash
python -m venv .venv && source .venv/bin/activate
python -m pip install -U pip
# after coding model adds pyproject and extras
pip install -e .[dev]
pre-commit install
pre-commit run -a
pytest -q
python -m slip_stick.parse_ftm10 --input t2en-crosil-42-external.csv --summary
```

### Pre‑commit config (to create)
```yaml
repos:
  - repo: https://github.com/psf/black
    rev: 24.8.0
    hooks:
      - id: black
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.6.2
    hooks:
      - id: ruff
        args: ["--fix"]
      - id: ruff-format
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.6.0
    hooks:
      - id: check-yaml
      - id: check-toml
      - id: check-json
      - id: end-of-file-fixer
      - id: trailing-whitespace
```

## Recent changes
- Established project goal: onset detection for slip–stick from FTM 10 data.
- Captured the 100‑line CSV preview constraint in the Memory Bank.
- Drafted repository `README.md` covering data structure, workflow, and roadmap.

## Important patterns and preferences
- Documentation‑first workflow with small, verifiable steps.
- Adaptive thresholds computed from pre‑event baseline statistics.
- Reproducible filtering using standard, inspectable methods (e.g., Butterworth,
  Savitzky–Golay, and Hilbert envelope for energy).

## Learnings and project insights
- Slip–stick expresses as sustained mid‑frequency energy riding on a slowly varying
  peel trend and contaminated by faster instrumental noise. A band‑limited energy
  detector with hysteresis is an appropriate onset criterion.
