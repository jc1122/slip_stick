# Source Data for Manuscript Tables 1 and 2

This directory provides machine-readable processed source values for the
non-force-displacement tables reported in the manuscript.

- `table1_material_properties.csv` reproduces the commercial sealant
  characterization values reported in manuscript Table 1.
- `table2_water_contact_angle.csv` reproduces the static water contact-angle
  values reported in manuscript Table 2.
- `table2_water_contact_angle_gonio_raw.csv` contains the five individual
  contact-angle measurements per manuscript sample exported from the goniometer
  workbook and canonicalized to the sample names used in the paper.

These files are processed summary/source values and canonicalized exports, not
raw instrument-project files. The force-displacement raw CSV datasets used for
Table 3, Table 4, and the
slip-stick analyses are archived separately in `datasets/` and are controlled
by `publication/dataset_manifest.csv`.

Table 1 provenance: Mooney viscosity, penetration, density, melt volume-flow
rate, peel adhesion, and failure-mode values were obtained from the material
characterization described in the manuscript methods and from Almara internal
commercial-material production records. The deposited Table 1 file is a
processed summary table only; raw Almara production/QC datasets are
company-internal records and are not part of this open archive. Peel adhesion
values are reported in N/24 mm as mean and sample standard deviation for
n = 10, consistent with the 24 mm EN 1939 specimen width used for this
characterization; the other quantitative parameters are reported as mean and
sample standard deviation for n = 3.

Table 2 provenance: static water contact angles were measured by the sessile-drop
technique with a Krüss DSA100 goniometer, using a 5 µL distilled-water drop at
room temperature and atmospheric pressure (recorded at 23 deg C). Five
measurements were acquired for each sample. Following the predefined processing
rule used for the reported table, the two extreme values were discarded and the
table reports the mean and sample standard deviation of the three central values. The individual
measurements used for this calculation are provided in
`table2_water_contact_angle_gonio_raw.csv`. Regenerate the processed Table 2
summary with:

```bash
python scripts/generate_table2_water_contact_angle.py
```

Source workbook names that match the
manuscript samples exactly are retained in `source_sample_name`; additional
non-manuscript workbook entries were not included because they do not support
the reported paper tables.
