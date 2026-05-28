# Generated Publication Outputs

Manifest: `publication/dataset_manifest.csv`
Replicate-level rows: 424
Configuration rows: 42
Publication plots generated: yes

## Rules

- Dataset inclusion follows the manifest exactly.
- Release force is the per-replicate mean over 50-200 mm.
- Forces are normalized from 90 mm collection width to 25 mm report width and reported as cN/25 mm.
- Configuration SD is the sample SD across replicate mean-release values.
- Slip-stick peak counts use one contiguous positive residual excursion above threshold as one event.
- No replicate-level outlier exclusions are applied by this generator.

## Excluded Dataset Ledger

- `20250317_C1E_rossella_internal.csv`: Superseded by 20250318_C1E_rossella_internal.csv for the publication matrix.
- `20250514_T1EN_crosil42_internal.csv`: Excluded because it is byte-identical to 20250514_T1EN_crosil42_external.csv; 20250514_T1EN_crosil42_internal_dup1.csv is used as the internal-side measurement.
- `20250319_C1E_silphan_external.csv`: Silphan is outside the manuscript liner matrix.
- `20250328_C1E_silphan_internal.csv`: Silphan is outside the manuscript liner matrix.
- `20250409_T2E_silphan_external.csv`: Silphan is outside the manuscript liner matrix.
