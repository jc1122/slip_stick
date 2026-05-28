# Zenodo Archive Contents

This worktree is prepared as the Zenodo staging package for the release-liner
slip-stick manuscript. It contains the measured datasets, reproducible analysis
code, generated publication outputs, and manuscript-facing supplementary files.

## Main Contents

- `datasets/`: the 42 source FTM 10-type CSV datasets used in the manuscript.
- `publication/dataset_manifest.csv`: canonical inclusion matrix for the
  manuscript release-force and slip-stick analyses.
- `scripts/generate_publication_outputs.py`: canonical table and figure
  generator.
- `publication/generated/`: regenerated tables, summary data, figure files,
  captions, manifests, and threshold-sensitivity outputs used to support the
  slip-stick detection method.
- `supplementary_material/`: manuscript-ready supplementary documents, release
  curve figures S1-S21, robustness summaries, and consistency audit outputs.
- `slipstick/`: analysis package used by the generator and CLI.

## Regeneration

Run from the repository root:

```bash
python scripts/generate_publication_outputs.py
```

This regenerates the publication tables and figures from the datasets and
manifest, including the threshold-sensitivity data used by the robustness
supplement. Use `--tables-only` when only the tabular outputs are needed.

## Deliberate Exclusions

The historical `plots/` cache is not part of the Zenodo package. It contained
bulk exploratory/generated plots and is superseded by the canonical outputs in
`publication/generated/` and `supplementary_material/figures/`.

## Before Public Deposition

Replace the manuscript Data Availability placeholder with the reserved Zenodo
DOI, and add the final article DOI to repository metadata if it is already
available at the time of deposition.
