# Publication Output Regeneration

This repository includes a canonical generator for the manuscript release-force
tables and supplementary force-displacement curve figures.

## Source of Truth

- `publication/dataset_manifest.csv` defines the 42 liner, sealant, and side
  datasets used in the manuscript matrix. The packaged `datasets/` directory is
  pruned to these manifest files.
- `publication/source_data/` provides the processed material-property summary
  values and the processed plus per-replicate water-contact-angle values
  reported as manuscript Tables 1 and 2.
- `publication/main_residual_profiles.csv` selects the three representative
  residual traces used for the main-manuscript residual-profile plot.
- `scripts/generate_publication_outputs.py` computes the tables and regenerates
  the main data plots and supplementary release-curve figures from the manifest.
- `scripts/generate_table2_water_contact_angle.py` regenerates the processed
  manuscript Table 2 contact-angle summary from the replicate-level source CSV.

The generator does not apply replicate-level outlier exclusions. If a trace or
dataset is to be excluded, adjust the manifest and document the reason in the
same commit.

## Regenerate Everything

Run from the repository root:

```bash
python -m pip install -r requirements.txt
python scripts/generate_publication_outputs.py
```

This writes:

- `publication/generated/README.md`
- `publication/generated/data/replicate_metrics.csv`
- `publication/generated/data/configuration_summary.csv`
- `publication/generated/data/threshold_noise_summary.csv`
- `publication/generated/data/threshold_robustness.csv`
- `publication/generated/data/top_peak_configs.csv`
- `publication/generated/data/threshold_robustness_summary.json`
- `publication/generated/data/warnings.csv`
- `publication/generated/data/window_sensitivity.csv`
- `publication/generated/tables/release_force_table.md`
- `publication/generated/tables/release_force_table.csv`
- `publication/generated/tables/release_force_table_numeric.csv`
- `publication/generated/tables/force_ratio_inner_outer_table.md`
- `publication/generated/tables/force_ratio_inner_outer_table.csv`
- `publication/generated/tables/force_ratio_inner_outer_table_numeric.csv`
- `publication/generated/tables/threshold_sensitivity_supplement.md`
- `publication/generated/tables/threshold_sensitivity_supplement.docx`
- `publication/generated/tables/window_sensitivity_supplement.md`
- `publication/generated/figures/main/png/figure2_release_force_heatmap.png`
- `publication/generated/figures/main/png/figure5_residual_profiles.png`
- `publication/generated/figures/main/png/figure8_peak_count_heatmap.png`
- `publication/generated/figures/main/pdf/*.pdf`
- `publication/generated/figures/main_figure_manifest.csv`
- `publication/generated/figures/main_figure_captions.md`
- `publication/generated/figures/release_curves/png/*.png`
- `publication/generated/figures/release_curves/pdf/*.pdf`
- `publication/generated/figures/figure_manifest.csv`
- `publication/generated/figures/release_curve_captions.md`

## Regenerate Tables Only

```bash
python scripts/generate_publication_outputs.py --tables-only
```

This path requires only `numpy` and `scipy`. Figure generation additionally
requires `matplotlib`.

For exact reproduction of the submitted outputs, use the exact lock mirrored in
`requirements.txt` and `requirements-lock.txt`, then run:

```bash
python scripts/verify_publication_outputs.py
```

The verification script checks the submitted-output Python/package versions,
regenerates tabular/data outputs in a temporary directory, compares the
machine-readable CSV/JSON plus Markdown table outputs with
`publication/generated/`, regenerates the processed Table 2 contact-angle
summary from `publication/source_data/table2_water_contact_angle_gonio_raw.csv`,
and checks sentinel values for the Rossella/C1E outer peak count and the default
1.4 cN/25 mm threshold total. Generated figures, captions, the generated README,
and DOCX containers are not byte-compared by this verifier. Use the included
`Dockerfile` for a clean containerized verification run.

## Calculation Rules

- Force values are rescaled from 90 mm collection width to 25 mm report width.
- Release force is reported in cN/25 mm.
- The release-force table uses each replicate's mean force over the available
  portion of the 50-200 mm window and reports values as mean ± sample SD with
  the valid replicate count in each cell. Traces that fail early span only part
  of the window; they are kept as physically meaningful early failures.
- `window_sensitivity.csv` and `window_sensitivity_supplement.md` recompute the
  configuration means using only traces that cover the full 50-200 mm window
  (to within 0.5 mm) and report the difference. They are a sensitivity check on
  the partial-window traces, not a separate release-force statistic.
- Configuration values are the mean and sample SD of those replicate means.
- Slip-stick peak counts use the same 50-200 mm window and the default
  1.4 cN/25 mm residual threshold. A count is one contiguous positive residual
  excursion above threshold, marked at the largest residual in that
  excursion.
- Force ratios are reported in a separate table, calculated from regenerated
  inner and outer mean release forces and rounded to an integer inner:outer
  ratio.
- Main Figure 2 and Figure 8 are generated from
  `publication/generated/data/configuration_summary.csv`.
- Main Figure 5 is generated from the representative traces listed in
  `publication/main_residual_profiles.csv`. Markers indicate positive residual
  excursions above the threshold; negative excursions are visible but are not
  counted as slip-stick peak events.
- Threshold-sensitivity data in `publication/generated/data` are generated from
  the same manifest and processing settings. These tables are intended as
  supplementary support for the operational 1.4 cN/25 mm peak-detection
  threshold, not as a separate release-force statistics analysis.
- Table 2 water-contact-angle values are regenerated by taking the five
  replicate measurements per sample from
  `publication/source_data/table2_water_contact_angle_gonio_raw.csv`, removing
  the lowest and highest contact-angle values, and reporting the mean and sample
  standard deviation of the three central values.
- Supplementary release-curve figures use a comparison-first y-axis policy.
  Every main panel uses the same shared 0-30 cN/25 mm y-axis. Figures
  containing traces above 30 cN/25 mm are flagged in the manifest and captions;
  sides with only brief above-range excursions use paired comparison and
  full-range panels, while sides with at least 5% of samples above 30 cN/25 mm
  are shown only at full range because the comparison-scale panel would not be
  informative.

The generator covers the data-derived manuscript figures. Photographs and
static schematic artwork in the manuscript are not generated by this script.

## Known Inclusion Decisions

- The packaged `datasets/` directory contains only the 42 files listed in
  `publication/dataset_manifest.csv`.
- The manuscript matrix is limited to the three liners reported in the paper:
  Dolpap, Rossella, and Crosil 42.
- No replicate-level outlier exclusions are applied by the canonical generator.
- Table 1 and Table 2 source values are provided in `publication/source_data/`.
  Table 1 is a processed summary from non-public Almara production/QC records;
  Table 2 includes the five canonicalized contact-angle measurements exported
  from the goniometer workbook and the reported central-three summary values.
