# Zenodo Archive Contents

This worktree is prepared as the Zenodo staging package for the release-liner
slip-stick manuscript. It contains the measured datasets, reproducible analysis
code, and generated publication outputs.

## Main Contents

- `datasets/`: the 42 source FTM 10-type CSV datasets used in the manuscript.
- `publication/dataset_manifest.csv`: canonical inclusion matrix for the
  manuscript release-force and slip-stick analyses.
- `scripts/generate_publication_outputs.py`: canonical table and figure
  generator.
- `publication/generated/`: regenerated tables, summary data, figure files,
  captions, manifests, and threshold-sensitivity outputs used to support the
  slip-stick detection method.
- `slipstick/`: analysis package used by the generator and CLI.
- `LICENSE`: CC BY 4.0 license notice for the archive contents.

## Regeneration

Run from the repository root:

```bash
pip install -r requirements.txt
python scripts/generate_publication_outputs.py
```

This regenerates the publication tables and figures from the datasets and
manifest, including the threshold-sensitivity data used by the robustness
analysis. Use `--tables-only` when only the tabular outputs are needed.

## Deliberate Exclusions

The historical `plots/` cache is not part of the Zenodo package. It contained
bulk exploratory/generated plots and is superseded by the canonical outputs in
`publication/generated/`.

The MDPI supplementary-material submission package is maintained in the parent
paper repository, not in this Zenodo data/code archive.

## Citation Metadata

Zenodo metadata is provided in `.zenodo.json`; citation metadata is provided in
`CITATION.cff`. The article DOI can be added in a later archive version once it
is available.
