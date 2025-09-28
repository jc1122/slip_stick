# Tech context

## Primary tools
- Python 3.10+ with pandas, numpy, scipy.signal, and matplotlib (for quick‑look plots).
- Markdown for documentation; git for tracking.

## Data ingestion
- CSV files from a tensile tester; schema inferred at runtime.
- Script will detect likely time and load/force columns via name matching and units.
- Sampling rate derived from the time column (median dt) or sequence index if absent.

## Signal processing approach
- Low‑frequency peel: estimate via low‑pass Butterworth or Savitzky–Golay trend.
- High‑frequency noise: attenuate via low‑pass smoothing before band‑pass.
- Slip–stick band: band‑pass Butterworth on detrended signal; envelope via Hilbert.
- Onset detection: adaptive threshold from baseline energy (e.g., median + k·MAD),
  with minimum duration and hysteresis to suppress spurious triggers.

## CLI interface (planned)
- Input: path(s) to CSV, optional column overrides, and filter parameters.
- Output: onset index/time, CSV/JSON summary, and optional plots.
- Safety: agent previews cap at 100 lines; processing reads the full file.

## Development setup
- Location: /workspaces/slip_stick (VS Code workspace).
- Memory Bank path: memory-bank/.
- Validate Markdown with markdownlint when available.

## Dev tooling (planned)
- Ruff for linting and quick fixes; Black for formatting (line length 100).
- Pre‑commit hooks to enforce style locally before commits.
- Pytest for unit tests; small CSV fixtures to avoid large file dependence.
