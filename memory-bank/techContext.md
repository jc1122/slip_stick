# Tech context

## Primary tools
- Python 3.10+ with pandas, numpy; pyarrow for Parquet outputs.
- (Detection phase) scipy.signal and optional matplotlib for quick‑look plots.
- Markdown for documentation; git for tracking; pre‑commit for local checks.

## Data ingestion
- CSV files from a tensile tester; schema inferred at runtime.
- Parser handles triple‑row headers (label/name/unit), heavy quoting, and decimal
  commas; detects delimiter/encoding and reconstructs a MultiIndex.
- Time/force/disp are mapped per replicate; sampling rate derived from median dt.

## Signal processing approach
- Low‑frequency peel: estimate via low‑pass Butterworth or Savitzky–Golay trend.
- High‑frequency noise: attenuate via low‑pass smoothing before band‑pass.
- Slip–stick band: band‑pass Butterworth on detrended signal; envelope via Hilbert.
- Onset detection: adaptive threshold from baseline energy (e.g., median + k·MAD),
  with minimum duration and hysteresis to suppress spurious triggers.

## CLI interfaces
- Parser (implemented): `python -m slip_stick.parse_ftm10 --input <file> [flags]`
  - Flags: `--summary`, `--out <base>`, `--preview-lines`, `--decimal-*`,
    `--header-rows`, `--quiet/--verbose`, `--version`.
  - Outputs: tidy Parquet and JSON metadata; summary to stdout.
- Detection (planned): extends CLI with filter params and onset export.

## Development setup
- Location: /workspaces/slip_stick (VS Code workspace).
- Memory Bank path: memory-bank/.
- Validate Markdown with markdownlint when available.

## Dev tooling
- Ruff for linting and quick fixes; Black for formatting (line length 100).
- Pre‑commit hooks (`.pre-commit-config.yaml`) to enforce style locally.
- Pytest with small CSV fixtures under `tests/fixtures/`.
