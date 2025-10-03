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

## Near-term next steps
- Parser validation on `t2en-crosil-42-{external,internal}.csv` confirms CP1250
  encoding, decimal commas, and dropped blank timestamps (up to 500 per replicate);
  promote these findings into metadata warnings or docs.
- Design experiment-level band aggregation using the JSON summaries (median/IQR plus
  outlier flags) and surface the results in CLI output.
- Implement the mid-band energy onset detector (baseline stats, adaptive threshold,
  hysteresis, minimum duration) and extend JSON exports with per-replicate onsets.
- Document detection defaults, JSON schema, and regression workflow so future agents
  extend detection logic without re-deriving parser details.

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
     `--hysteresis`, `--env-win`, `--method {rms,hilbert}`, and band aggregation mode;
     reuse existing `--all-reps/--write-json` plumbing to emit onset diagnostics.
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
- Real-data audit on the Crosil 42 external/internal exports verifies the CLI output
  under Python 3.11+, highlights CP1250 metadata, and quantifies blank timestamp
  drops per replicate.

## Recent accomplishments — detection phase
- Welch band estimation now enforces guardrails, optional baseline windows, and richer
  diagnostics (bandwidth, segment counts, baseline peak ratios).
- Complementary decomposition returns a structured result with reconstruction RMS and
  energy partition metrics; CLI surfaces mid-band energy fractions and writes the
  diagnostics into NPZ artifacts.
- `detect_cli` iterates over all replicates, writes per-replicate NPZ payloads, and can
  emit JSON summaries that capture band estimates and decomposition diagnostics for
  downstream comparison tooling.
- Added a Savitzky–Golay detrending script that sweeps every dataset, saves per-replicate
  baselines/residuals, and renders SVG overlays so the slip–stick spikes can be reviewed
  independently of the peel trend.
- Savitzky–Golay overlays now accept a displacement axis and optional distance window,
  letting us focus plots (e.g. 50–200 mm) while still exporting cropped NPZ data.
- Introduced `scripts/run_savgol_workflow.py` to automate detrending (distance axis,
  50–200 mm window), scaled average-force reporting, and residual spike analysis with
  thresholds `ratio ≥ 10` and `|residual| ≥ 0.05 N`.
- Latest workflow run confirmed the automation reproduces the manual findings: all ten
  internal T1EN replicates and key external ones (e.g., Crosil 42 external 1_10 and
  Rossella external 1_9) exceed the spike thresholds, and the scaled mean forces match
  the earlier 25/90 calculations.

### Tasks (actionable)
- Harden parser resilience: improve errors for header mismatches, missing replicates,
  and monotonicity drops; surface anomalies in metadata.
- Cross‑validate external vs internal CSV previews (≤100 lines) and record any schema
  differences in `progress.md` plus metadata defaults.
- Implement onset detector and extend `detect_cli` JSON output with onset timings and
  detection diagnostics (see Numbered TODOs).
- Document detection usage in README; align Memory Bank and regression workflow notes.

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

## Actionable TODOs — band estimation and onset detection (scaffold)

### Band estimation
- Add baseline‑aware option: estimate bands with and without a baseline window `(t0, t1)`.
- Improve peak picking: smooth PSD, find −3 dB crossings; enforce `0 < f1 < f2 < 0.45·Fs`.
- Handle edge cases: flat PSD, short records, narrow spectral lines; return NaN‑safe outputs.
- Aggregate across replicates: median/IQR by default with per‑replicate overrides.
- Expose diagnostics: resolution, smooth width, segment count, peak power, search band.
- Keep JSON‑friendly outputs: `BandEstimate` plus a dict helper for serialization.

### Onset detection
- Envelope/energy: moving‑RMS by default; optional Hilbert envelope; parametrize window (s).
- Baseline statistics: compute median and MAD over baseline window; record sample count.
- Adaptive threshold: `thr = median + k·MAD`; clamp to non‑negative; record `k` and window.
- Hysteresis and minimum duration: rising‑edge trigger with hold and duration gating.
- Per‑replicate outputs: onset index/time, thresholds used, baseline window, method params.
- JSON writer: persist `{replicate_id: {...}}` with version and diagnostics.

### CLI wiring
- Flags: `--baseline t0 t1`, `--k K`, `--min-duration S`, `--hysteresis R`,
  `--method {rms,hilbert}`, `--env-win S`, `--all-reps`, `--write-json PATH`.
- Defaults: estimate bands when `--f1/--f2` absent; sensible `k`, `min-duration`, and
  `hysteresis` based on Fs.
- Output: per‑replicate summary of band, onset time, thresholds, and key diagnostics.

### Tests and validation
- Synthetic signals: known mid‑band bursts at varied SNR; multi‑burst (choose first);
  no‑onset case (expect None).
- Reconstruction property: assert `low + mid + high ≈ original` (small RMS) before
  detection.
- Robustness: short records, NaNs at tails, lower Fs; threshold monotonicity with `k`.
- CLI smoke: run detect with `--estimate-bands --all-reps --write-json` on fixture and
  validate schema.
- Baseline sensitivity: compare with/without baseline window; record differences.

### Diagnostics and guardrails
- Log chosen bands, thresholds, baseline window, envelope method, durations; warn on
  clamping/NaNs.
- Validate parameters: `0 < f1 < f2 < 0.5·Fs`, `min-duration > 0`, `k ≥ 0`,
  `0 ≤ hysteresis < 1`.
- Determinism: fixed windows, no randomness; document exact defaults.

### Definition of done
- Band estimation runs per replicate with aggregation and emits diagnostics.
- Onset detector returns stable onset times on synthetic cases and the fixture set.
- Decomposition validated: `low + mid + high` reconstructs original with small RMS.
- Detect CLI processes one/all replicates, writes JSON, and prints concise summaries.
- Unit and CLI tests pass; README updated with detection usage and defaults.
