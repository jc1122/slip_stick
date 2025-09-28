# Product context

## Purpose
Build a robust, documented workflow and script that find the onset of slip–stick in
FTM 10 tensile tester data. The solution must separate three signal bands present in
the CSV: low‑frequency peel, mid‑frequency slip–stick candidates, and high‑frequency
instrumental noise, then detect when mid‑band energy rises above baseline.

## Problems solved
- Operationalizes slip–stick onset detection for noisy tensile data.
- Encodes assumptions so future agents can reproduce results.
- Avoids context overflows by limiting previews of large CSVs to 100 lines.

## How it works
Documentation captures decisions and constraints. A Python CLI will read CSV data,
infer schema and sampling rate, separate frequency bands via filtering, compute an
envelope/energy measure for the mid‑band, and declare onset using adaptive
thresholds with minimum duration and hysteresis. Results export timestamps/indices
and optional plots.

## User experience goals
- Minimal required inputs; sensible defaults inferred from data.
- Transparent filtering with parameters that can be inspected and tuned.
- Deterministic outputs suitable for reports and further analysis.
