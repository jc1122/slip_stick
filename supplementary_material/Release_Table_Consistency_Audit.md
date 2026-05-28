# Release Table Consistency Audit

Status: resolved.

The current Table 3 in `Publikacja JCZ_Applied Science_v4.docx` was regenerated from `publication/generated/tables/release_force_table.csv` and verified against that canonical CSV. The earlier mismatch audit is obsolete because the manuscript table has now been replaced with the dataset-derived values.

## Current Source of Truth

- Generator: `scripts/generate_publication_outputs.py`
- Manifest: `publication/dataset_manifest.csv`
- Display table: `publication/generated/tables/release_force_table.csv`
- Numeric table: `publication/generated/tables/release_force_table_numeric.csv`
- Verification data: `supplementary_material/data/release_table_consistency_audit.csv`

## Status Counts

- MATCHES_CANONICAL_GENERATOR: 63 table cells/ratio entries
- FLAGGED_MISMATCH: 0

## Notes

- Values are per-replicate mean release force over 50-200 mm, normalized to cN/25 mm.
- Displayed values are rounded as mean ± sample SD.
- Ratio rows are generated from the inner/outer means and shown as integer-rounded inner:outer ratios.
- The high Rossella/U2E outer-side value is now reported as 238.4 ± 73.9 cN/25 mm.
