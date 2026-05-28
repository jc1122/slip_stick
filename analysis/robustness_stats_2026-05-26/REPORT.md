# Robustness and Simple Statistics Review

Date: 2026-05-26

Scope: manuscript-relevant datasets only.

Included:
- 42 liner-sealant-side configurations.
- 424 replicate traces.
- Liners: Dolpap, Rossella, Crosil 42.
- Sealants: C1E, U2E, C1EN, T1E, T2E, T1EN, T2EN.

Excluded:
- `silphan` datasets, because they are not in the manuscript matrix.
- `20250317_C1E_rossella_internal.csv`, because a later file exists for the same configuration.
- `20250514_T1EN_crosil42_internal_dup1.csv`, because it is explicitly marked as a duplicate.

## Threshold Robustness

The default 1.4 cN/25 mm threshold is well above the measured instrumental noise:

- Median baseline noise SD: 0.066 cN/25 mm.
- 95th percentile baseline noise SD: 0.116 cN/25 mm.
- Maximum observed baseline noise SD: 0.343 cN/25 mm.
- Median baseline max absolute noise: 0.166 cN/25 mm.
- 95th percentile baseline max absolute noise: 0.318 cN/25 mm.
- Maximum baseline max absolute noise: 0.933 cN/25 mm.
- Default threshold / median noise SD: 21.3x.
- Default threshold / 95th percentile noise SD: 12.0x.

Configuration-level mean peak counts remained highly stable around the manuscript threshold:

| Threshold [cN/25 mm] | Spearman rho vs 1.4 cN | Total peaks | Configurations with mean >= 1 peak | Configurations with mean >= 5 peaks |
|---:|---:|---:|---:|---:|
| 0.5 | 0.821 | 10269 | 40 | 34 |
| 1.0 | 0.955 | 3879 | 34 | 18 |
| 1.4 | 1.000 | 2334 | 26 | 14 |
| 2.0 | 0.965 | 1486 | 20 | 8 |
| 3.0 | 0.880 | 1010 | 11 | 4 |

Interpretation:
- The absolute number of peaks changes with threshold, as expected.
- The ranking of unstable configurations is robust for the practical threshold range 1.0-2.0 cN/25 mm.
- This robustness check would benefit the manuscript, preferably as a short sentence in Methods/Results and a supplementary table.

Suggested manuscript sentence:

> A threshold-sensitivity check was performed by repeating the peak-count analysis at 1.0, 1.4 and 2.0 cN/25 mm. Configuration-level mean peak counts remained strongly correlated with the default 1.4 cN/25 mm threshold (Spearman rho = 0.955 for 1.0 cN/25 mm and rho = 0.965 for 2.0 cN/25 mm), confirming that the identification of unstable liner-sealant configurations was not an artefact of a single threshold value.

## Most Robust High-Risk Configurations

Top configurations at the default threshold:

| Sealant | Liner | Side | Mean peaks/rep at 1.0 | Mean peaks/rep at 1.4 | Mean peaks/rep at 2.0 | Mean peaks/rep at 3.0 |
|---|---|---|---:|---:|---:|---:|
| U2E | Rossella | outer | 42.5 | 42.3 | 42.0 | 41.5 |
| U2E | Crosil 42 | outer | 48.6 | 37.3 | 28.5 | 19.6 |
| T1EN | Rossella | outer | 40.5 | 24.1 | 12.7 | 5.7 |
| T2E | Dolpap | inner | 25.5 | 16.2 | 8.6 | 3.5 |
| T1E | Rossella | inner | 27.8 | 11.7 | 6.1 | 2.5 |
| C1EN | Rossella | inner | 14.9 | 10.9 | 8.5 | 6.5 |
| T2EN | Rossella | inner | 12.6 | 9.3 | 6.7 | 4.5 |
| T2E | Rossella | inner | 11.6 | 8.7 | 5.8 | 2.0 |

The U2E/Rossella/outer configuration remains extreme under every threshold tested. This strongly supports the manuscript's qualitative interpretation of this configuration as unstable.

## Simple Statistics

Exploratory non-parametric screening was run on replicate-level values.

Release force:
- Sealant effect: Kruskal-Wallis p = 1.48e-20.
- Liner effect: Kruskal-Wallis p = 1.28e-48.
- Side effect: Kruskal-Wallis p = 0.033.

Peak count at 1.4 cN/25 mm:
- Sealant effect: Kruskal-Wallis p = 0.0051.
- Liner effect: Kruskal-Wallis p = 0.0015.
- Side effect: Kruskal-Wallis p = 0.0083.

Exploratory log-transformed OLS/ANOVA models also showed significant main effects and interactions for both release force and peak counts. This supports the manuscript's statement that release behavior and slip-stick tendency depend on the complete liner-sealant-side configuration.

## Caution on Release-Force Statistics

Do not add the release-force ANOVA to the manuscript yet.

Reason: release-force means computed directly from raw traces over the 50-200 mm analysis window are close to the manuscript table for most configurations, but not identical for every case. The largest discrepancy is the Rossella/U2E/outer outlier, where the calculated mean changes substantially depending on the averaging window. The manuscript's Table 3 should remain the authoritative release-force source unless the exact table-generation procedure is reproduced.

Safe use:
- Use the threshold robustness results.
- Use the peak-count Kruskal screening only as optional support for "configuration dependence."

Avoid for now:
- Adding formal release-force ANOVA values to the main manuscript.
- Claiming statistical significance from a raw-trace window that does not exactly match Table 3.

## Generated Files

- `replicate_level.csv`
- `configuration_summary.csv`
- `threshold_robustness.csv`
- `top_peak_configs.csv`
- `kruskal_screening.csv`
- `anova_log_release_force.csv`
- `anova_log1p_peak_counts.csv`
- `side_differences_config_means.csv`
- `summary.json`
