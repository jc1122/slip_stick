# Supplementary Material

## Threshold Robustness of Slip-Stick Peak Detection

This supplementary material supports the manuscript *Slip-Stick Dynamics in Butyl Pressure-Sensitive Adhesive-Silicone Release Liner Systems: A New Approach to Analyzing the Performance of Release Liners*. It documents the noise floor, threshold-sensitivity check and exploratory configuration-level statistics for the slip-stick peak-count descriptor.

### S1. Dataset Scope

The analysis used the manuscript-relevant force-displacement datasets from the `slip_stick` repository. The `silphan` datasets were excluded because they are not part of the manuscript matrix. One older repeated C1E/Rossella/internal file and one file explicitly marked as a duplicate were also excluded. The final analysis included 42 liner-sealant-side configurations and 424 replicate traces.

For every trace, the same processing settings as in the manuscript were used: normalization to cN/25 mm, analysis over the 50-200 mm displacement window, a long Savitzky-Golay baseline, and peak detection on the residual force signal. The default threshold was 1.4 cN/25 mm.

### S2. Instrumental Noise and Threshold Margin

Table S1. Baseline noise summary from the initial near-zero-force segment of each raw trace.

| Metric                                          | Value          |
|:------------------------------------------------|:---------------|
| Number of replicate traces                      | 424            |
| Number of liner-sealant-side configurations     | 42             |
| Median baseline noise SD                        | 0.066 cN/25 mm |
| 95th percentile baseline noise SD               | 0.116 cN/25 mm |
| Maximum baseline noise SD                       | 0.343 cN/25 mm |
| Median baseline maximum absolute noise          | 0.166 cN/25 mm |
| 95th percentile baseline maximum absolute noise | 0.318 cN/25 mm |
| Maximum baseline maximum absolute noise         | 0.933 cN/25 mm |
| Threshold / median noise SD                     | 21.3x          |
| Threshold / 95th percentile noise SD            | 12.0x          |

The default 1.4 cN/25 mm threshold was therefore well above the measured noise level. It was about 21 times the median baseline noise SD and about 12 times the 95th percentile baseline noise SD.

### S3. Threshold Sensitivity

Table S2. Sensitivity of peak counts to the detection threshold. Spearman rho was computed across configuration-level mean peak counts relative to the default 1.4 cN/25 mm threshold.

|   Threshold [cN/25 mm] |   Spearman rho vs 1.4 | p value   |   Total peaks |   Configs mean >= 1 peak |   Configs mean >= 5 peaks |
|-----------------------:|----------------------:|:----------|--------------:|-------------------------:|--------------------------:|
|                    0.5 |                 0.821 | <0.001    |         10269 |                       40 |                        34 |
|                    1   |                 0.955 | <0.001    |          3879 |                       34 |                        18 |
|                    1.4 |                 1     | <0.001    |          2334 |                       26 |                        14 |
|                    2   |                 0.965 | <0.001    |          1486 |                       20 |                         8 |
|                    3   |                 0.88  | <0.001    |          1010 |                       11 |                         4 |

The absolute number of detected peaks decreased as the threshold increased, as expected. The ranking of configurations remained stable in the practical threshold range around the selected value: rho = 0.955 for 1.0 cN/25 mm and rho = 0.965 for 2.0 cN/25 mm, both relative to the 1.4 cN/25 mm analysis.

### S4. Configurations with the Highest Peak Counts

Table S3. Ten configurations with the highest mean peak counts at the default 1.4 cN/25 mm threshold. Values are means per replicate unless otherwise stated.

| Sealant   | Liner     | Side   |   n |   Mean peaks 1.0 |   Mean peaks 1.4 |   Mean peaks 2.0 |   Mean peaks 3.0 |   Mean force [cN/25 mm] |   Median noise SD |
|:----------|:----------|:-------|----:|-----------------:|-----------------:|-----------------:|-----------------:|------------------------:|------------------:|
| U2E       | Rossella  | outer  |  10 |             42.5 |             42.3 |             42   |           41.5   |                   238.4 |             0.059 |
| U2E       | Crosil 42 | outer  |  10 |             48.6 |             37.3 |             28.5 |           19.6   |                    17.8 |             0.075 |
| T1EN      | Rossella  | outer  |  10 |             40.5 |             24.1 |             12.7 |            5.7   |                    25.9 |             0.056 |
| T2E       | Dolpap    | inner  |  10 |             25.5 |             16.2 |              8.6 |            3.5   |                     7   |             0.065 |
| T1E       | Rossella  | inner  |  10 |             27.8 |             11.7 |              6.1 |            2.5   |                     9   |             0.08  |
| C1EN      | Rossella  | inner  |  10 |             14.9 |             10.9 |              8.5 |            6.5   |                    15   |             0.059 |
| T2EN      | Rossella  | inner  |  10 |             12.6 |              9.3 |              6.7 |            4.5   |                    12.9 |             0.071 |
| T2E       | Rossella  | inner  |  10 |             11.6 |              8.7 |              5.8 |            2     |                    10.8 |             0.066 |
| C1E       | Rossella  | outer  |  12 |             23.6 |              7.2 |              1.2 |            0.333 |                    12.5 |             0.08  |
| T2EN      | Crosil 42 | outer  |  10 |             15.7 |              7   |              1.8 |            0.6   |                     8.3 |             0.072 |

The Rossella/U2E/outer configuration remained extreme at every threshold tested. Other configurations changed in absolute peak count with threshold, but the same high-instability group remained visible across the 1.0-2.0 cN/25 mm range. High peak count should not be read as identical to high mean release force; it describes instability of the force trace after baseline correction.

### S5. Exploratory Configuration-Level Statistics

Table S4. Exploratory paired tests for the configuration-level peak-count descriptor at the default 1.4 cN/25 mm threshold.

| Effect tested                           | Test                 |   Blocks |   Statistic |   p value |
|:----------------------------------------|:---------------------|---------:|------------:|----------:|
| liner paired within sealant-side blocks | Friedman             |       14 |       3.857 |     0.145 |
| sealant paired within liner-side blocks | Friedman             |        6 |       4.599 |     0.596 |
| side paired within sealant-liner blocks | Wilcoxon signed-rank |       21 |      99.5   |     0.837 |

No single main factor by itself explained the peak-count descriptor at the configuration-mean level. This supports the interpretation used in the manuscript: slip-stick tendency is governed by the specific sealant-liner-side configuration rather than by liner type, sealant type or liner side alone.

### S6. Machine-Readable Supplementary Data

The following files accompany this supplement:

- `data/threshold_robustness.csv`: threshold-sensitivity summary.
- `data/top_peak_configs.csv`: ranked configuration summary by default-threshold peak count.
- `data/paired_configuration_tests.csv`: exploratory paired tests on configuration-level means.
- `data/configuration_summary.csv`: configuration-level release-force, noise and peak-count summaries.
- `data/replicate_level.csv`: replicate-level processed metrics.
- `data/summary.json`: machine-readable summary of the analysis run.
