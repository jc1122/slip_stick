Fixture guidance
================

Use small CSV slices for deterministic tests. Fixtures should:
- Contain 2–3 replicates (6–9 columns of data) with a 3-row header
  (replicate label, name, unit) and decimal commas.
- Include ~1–2 seconds of data to keep tests fast.

Quick-start (derive from repository CSVs):
```bash
# External dataset: keep first ~120 lines for a small sample
mkdir -p tests/fixtures
head -n 120 t2en-crosil-42-external.csv > tests/fixtures/ftm10_external_head.csv

# Internal dataset: same idea (optional)
head -n 120 t2en-crosil-42-internal.csv > tests/fixtures/ftm10_internal_head.csv
```

Optional (reduce to first 2 replicates only):
- Implement a small Python helper to parse the MultiIndex header, then slice to
  the first 6 columns and write a compact fixture. This keeps quoting intact and
  avoids issues with `cut` on quoted CSV.

Expected structure (for 2 replicates):
- Row 1: replicate labels: e.g., "1 _ 1",, , "1 _ 2",, ,
- Row 2: names per column: "Czas","Siła","Przemieszczenie", repeated per replicate.
- Row 3: units per column: "sec","N","mm", repeated per replicate.
- Rows 4+: numeric data with decimal commas.

