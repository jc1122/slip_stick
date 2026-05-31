# Zenodo Archive Contents

This worktree is prepared as the Zenodo staging package for the release-liner
slip-stick manuscript. It contains the measured datasets, reproducible analysis
code, and generated publication outputs.

## Main Contents

- `datasets/`: the 42 source CSV datasets from the modified FINAT FTM 10-type
  180° peel integration tests used in the manuscript. The design targeted ten
  traces per configuration; a few files hold nine, eleven, or twelve, and the
  tables report the actual valid n. The single `_dup1` filename is an export
  naming artifact with unique content (see `README.md`, "Dataset notes").
- `publication/dataset_manifest.csv`: canonical inclusion matrix for the
  manuscript release-force and slip-stick analyses.
- `publication/source_data/`: processed source values for the
  material-property and water-contact-angle data reported in manuscript Tables
  1 and 2. Table 1 is a processed summary from non-public Almara production/QC
  records; Table 2 includes the five canonicalized contact-angle measurements
  exported from the goniometer workbook.
- `scripts/generate_publication_outputs.py`: canonical table and figure
  generator.
- `scripts/generate_table2_water_contact_angle.py`: regeneration script for the
  processed manuscript Table 2 contact-angle summary from the replicate-level
  source CSV.
- `scripts/verify_publication_outputs.py`: regeneration check for the archived
  tabular outputs, the processed Table 2 contact-angle summary, and sentinel
  spike-count values.
- `verification_report_2026-05-31.txt`: passing verification report generated
  in the exact Python 3.14.4 locked environment.
- `publication/generated/`: regenerated tables, summary data, figure files,
  captions, manifests, threshold-sensitivity outputs, and the release-force
  window-coverage sensitivity check (`data/window_sensitivity.csv`,
  `tables/window_sensitivity_supplement.md`) used to support the manuscript.
- `slipstick/`: analysis package used by the generator and CLI.
- `LICENSE`: split license notice. Data, generated outputs, documentation, and
  metadata are CC BY 4.0; software code under `slipstick/` and `scripts/` is
  MIT licensed.

## Regeneration

Run from the repository root:

```bash
python -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python scripts/verify_publication_outputs.py
python scripts/generate_table2_water_contact_angle.py
python scripts/generate_publication_outputs.py
```

This regenerates the publication tables and figures from the datasets and
manifest, and regenerates the processed water-contact-angle Table 2 source
summary from the replicate-level source CSV. It also includes the
threshold-sensitivity data used by the robustness analysis. Use `--tables-only`
when only the force-release tabular outputs are needed.

The requirements files record the exact environment used for the submitted
outputs: Python 3.14.4, NumPy 2.4.6, SciPy 1.17.1, and Matplotlib 3.10.9.
The verification script fails before regeneration if Python or the core package
versions do not match this lock. For a clean containerized check, run:

```bash
docker build -t slipstick-publication .
docker run --rm slipstick-publication
```

## Zenodo Upload Unit

Build the Zenodo staging ZIP from committed contents and upload it as one file:

```bash
git archive --format=zip --prefix=slipstick_zenodo_staging_2026-05-30/ \
  --output ../slipstick_zenodo_staging_2026-05-30.zip HEAD
unzip -t ../slipstick_zenodo_staging_2026-05-30.zip
```

Do not upload the extracted archive contents as individual Zenodo files: the
extracted tree contains more than 100 files, while the single ZIP keeps the
upload below Zenodo's per-record file-count limit and preserves the internal
directory structure. Do not create the upload package with a raw working-tree
`zip -r`: the `git archive` command above excludes ignored local deposition
state, Python caches, and other untracked files.

## DOI Reservation and Upload Helper

The helper `scripts/zenodo_deposit.py` uses the Zenodo REST API directly. It can
reserve a draft DOI and upload the final single ZIP once a personal access token
is available:

```bash
export ZENODO_ACCESS_TOKEN=...
python scripts/zenodo_deposit.py reserve
python scripts/zenodo_deposit.py upload --file ../slipstick_zenodo_staging_2026-05-30.zip
```

The script writes `zenodo_deposition_draft.json` and `zenodo_reserved_doi.txt`
locally; these files are intentionally ignored by git. The script does not
publish the record unless `python scripts/zenodo_deposit.py publish --publish`
is run explicitly.

## Deliberate Exclusions

The historical `plots/` cache is not part of the Zenodo package. It contained
bulk exploratory/generated plots and is superseded by the canonical outputs in
`publication/generated/`.

The MDPI supplementary-material submission package is maintained in the parent
paper repository, not in this Zenodo data/code archive.

## Citation Metadata

Zenodo metadata is provided in `.zenodo.json`; citation metadata is provided in
`CITATION.cff`.

Reserved archive DOI: https://doi.org/10.5281/zenodo.20448892

The article DOI can be added separately in a later archive version once it is
available.
