# Generated Publication Outputs

Manifest: `publication/dataset_manifest.csv`
Replicate-level rows: 424
Configuration rows: 42
Publication plots generated: yes

## Rules

- Dataset inclusion follows the manifest exactly.
- Release force is the per-replicate mean over the available portion of the 50-200 mm window.
- Forces are normalized from 90 mm collection width to 25 mm report width and reported as cN/25 mm.
- Configuration SD is the sample SD across replicate mean-release values.
- Slip-stick peak counts use one contiguous positive residual excursion above threshold as one event.
- Threshold-robustness outputs repeat the peak-count analysis across nearby thresholds from the same manifest.
- `data/window_sensitivity.csv` and `tables/window_sensitivity_supplement.md` compare the reported configuration means against a strict full-window subset of traces.
- No replicate-level outlier exclusions are applied by this generator.
