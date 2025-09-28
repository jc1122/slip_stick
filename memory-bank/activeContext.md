# Active context

## Current work focus
Implement slip–stick detection on top of the tidy parser: estimate mid‑band from data,
perform a lossless low/mid/high decomposition, and add a transparent onset detector
with baseline‑aware thresholds, hysteresis, and minimum‑duration gating. Validate on
the external and internal CSVs and document the workflow.

## Operating constraints (agent)
- The coding agent should only preview at most 100 lines from any CSV to avoid
  overflowing the context window. The processing script itself will read full files.
- All data characteristics (columns, units, sampling rate) will be inferred directly
  from the CSV files rather than relying on prior assumptions.

## Near‑term next steps
- Exercise the parser on both external and internal CSVs; capture edge cases and
  promote anomalies into metadata or explicit errors.
- Finalize band estimation (Welch) and lossless three‑way decomposition (low/mid/high)
  on `force_N`, exposed via `detect.py` and `detect_cli.py`.
- Implement the mid‑band energy onset detector (baseline stats, adaptive threshold,
  hysteresis, minimum duration) and export per‑replicate onsets.
- Document updated CLI workflows, fixtures, and testing cadence so future agents can
  extend detection logic without re‑deriving parser details.

## Numbered TODOs — coding model
1. Band estimation (per replicate)
   - Add baseline‑aware option (contrast early window vs full), smoothing, guardrails.
   - Aggregate to a robust experiment‑wide band (median/IQR) with per‑replicate overrides.
2. Lossless decomposition
   - Keep frequency‑domain complementary split; add optional zero‑phase FIR variant.
   - Emit reconstruction RMS and energy partition metrics (E_low/E_mid/E_high).
3. Onset detector
   - Mid‑band envelope (moving RMS; Hilbert optional later), baseline median + k·MAD,
     minimum duration, and hysteresis. Return onset index/time per replicate.
4. CLI wiring
   - Extend `detect_cli` with `--baseline [t0 t1]`, `--k`, `--min-duration`,
     `--hysteresis`, `--write-json` (band + onsets), and band aggregation mode.
5. Tests (unit + CLI)
   - Synthetic bursts to validate band estimation and onset detection.
   - Perfect‑reconstruction assertion (low + mid + high == original; small RMS).
   - CLI smoke tests for estimation, decomposition, and JSON outputs.
6. Validation on real data
   - External/internal CSV runs; snapshot bands and onset counts; record anomalies.
7. Documentation
   - README detection section: flags, defaults, examples; link to Memory Bank.
   - Update `techContext.md`/`systemPatterns.md` if parameters are finalized.
8. Regression harness
   - Persist `.metadata.json` and `.onsets.json` snapshots; add a simple comparator
     script to detect drifts.

## Recent accomplishments — parsing phase
- Dialect sniffing, MultiIndex header reconstruction, and numeric coercion with
  decimal-comma support are in place.
- Long-format DataFrame construction with monotonicity checks and per-replicate
  statistics (Fs, dt, NaN totals) is implemented.
- CLI wiring delivers summary output, Parquet/JSON exports, logging controls, and
  pytest coverage via fixtures sampled from the external dataset.

### Tasks (actionable)
- Harden parser resilience: improve errors for header mismatches, missing replicates,
  and monotonicity drops; surface anomalies in metadata.
- Cross‑validate external vs internal CSV previews (≤100 lines) and record any schema
  differences in `progress.md` plus metadata defaults.
- Implement onset detector and JSON export in `detect_cli` (see Numbered TODOs).
- Document detection usage in README; align the Memory Bank with the detection track.

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

### Detailed TODOs — detection implementation
1. Band estimation (Welch) with optional baseline contrast; robust replicate aggregation.
2. Lossless decomposition metrics and optional FIR variant for cross‑check.
3. Onset detection (envelope, baseline stats, adaptive threshold, hysteresis, duration).
4. CLI flags for baseline/thresholds and `--write-json` outputs.
5. Unit and CLI tests; fixture‑based smoke; synthetic validation.

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
