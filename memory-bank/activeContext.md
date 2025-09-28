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
- Exercise the parser on both external and internal CSVs; capture edge cases and
  promote anomalies into metadata or explicit errors.
- Prototype the band‑limited filtering and onset detection workflow that consumes
  the tidy parser output.
- Document updated CLI workflows, fixtures, and testing cadence so future agents
  can extend detection logic without re-deriving parser details.

## Recent accomplishments — parsing phase
- Dialect sniffing, MultiIndex header reconstruction, and numeric coercion with
  decimal-comma support are in place.
- Long-format DataFrame construction with monotonicity checks and per-replicate
  statistics (Fs, dt, NaN totals) is implemented.
- CLI wiring delivers summary output, Parquet/JSON exports, logging controls, and
  pytest coverage via fixtures sampled from the external dataset.

### Tasks (actionable)
- Harden parser resilience: improve error messages for header mismatches, missing
  replicates, or monotonicity drops; extend metadata to surface anomalies.
- Cross-validate external vs internal CSV previews (≤100 lines) and record any
  schema differences in `progress.md` plus metadata defaults.
- Sketch the filtering/onset detection workflow (functions, CLI extension points,
  testing strategy) using the new tidy outputs.
- Document parser usage in README (flag table, sample summary) and align the Memory
  Bank with the upcoming detection workstream.

## Detailed TODOs — parser hardening and detection
1. Add robust error handling:
   - Missing/extra columns in a block, inconsistent header rows, non-monotonic time, and quoting anomalies.
   - Emit clear messages; continue best-effort where safe, or fail fast with guidance.
2. Document defaults and overrides in README:
   - Decimal handling, header rows, preview lines, and output paths.
3. Run tooling on each iteration:
   - `pre-commit run -a` and `pytest -q`; fix lint/format issues and failing tests.
4. Encoding and BOM handling:
   - Default to `encoding='utf-8'`; also try `utf-8-sig` to strip BOMs if present.
   - Ensure Polish diacritics (e.g., "Siła") are parsed correctly; document fallback.
5. Header cleaning and validation:
   - Strip leading/trailing whitespace and quotes from header labels.
   - Drop all-empty trailing columns; assert `column_count % 3 == 0` or error.
   - Record any anomalies (e.g., missing units) in metadata.
6. Replicate label normalization:
   - Ensure `_normalize_replicate_label(label)` stays deterministic (`"1 _ 1" -> "rep1_1"`).
   - Add a regression test covering tricky labels.
7. Units validation and conversion:
   - Accept synonyms (e.g., `sec`/`s`), and scale if needed (e.g., `kN`→`N`, `µm`→`mm`).
   - Record conversions applied per replicate in metadata.
8. CLI ergonomics and logging:
   - `--quiet/--verbose` implemented; add richer status/error messaging and ensure non-zero exit codes on fatal failures.
9. Output handling:
   - Create parent directories for `--out` if missing.
   - Optional flag `--partition-by-replicate` to write per-replicate Parquet files; otherwise keep the consolidated file.
10. Additional tests:
    - JSON metadata schema and required keys presence.
    - `--out` writes both `.parquet` and `.metadata.json` with expected content.
    - Cross-file consistency: parse both external and internal CSV heads and confirm consistent shapes and replicate detection.
11. Timebase edge cases:
    - Handle duplicate timestamps by dropping subsequent duplicates (record counts).
    - Allow varying lengths per replicate; long format should naturally accommodate.

### Tests (current coverage)
- Pytest suite exercises header parsing, decimal coercion, replicate grouping, timebase
  stats, long-format shape, and CLI summary execution using
  `tests/fixtures/ftm10_external_head.csv`.

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
