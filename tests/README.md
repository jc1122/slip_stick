Instruction-only test scaffold
==============================

This directory will contain pytest-based tests for the FTM 10 parser.
Do not add executable tests yet; use this file as guidance.

Planned tests
-------------
- `test_header_parsing.py`: 3-row header detection and name/unit mapping.
- `test_decimal_comma.py`: decimal comma numeric coercion.
- `test_replicates.py`: replicate block counting and grouping.
- `test_timebase.py`: monotonic timebase and Fs ≈ 100 Hz (tolerance).
- `test_long_shape.py`: long-format column set and row count checks.
- `test_cli_summary.py`: CLI `--summary` smoke test on a small fixture.

Fixtures
--------
- Place small CSVs under `tests/fixtures/` with 2–3 replicates and ~1–2 seconds of
  data to keep tests fast. Include at least one file with decimal commas and quoted
  headers, matching the structure observed in `t2en-crosil-42-*.csv`.

Running tests (after implementation)
------------------------------------
```bash
pytest -q
```
