# Release-Force Window-Coverage Sensitivity

The per-trace release force reported in the manuscript is the mean over the available portion of the 50-200 mm displacement window. Most traces span the whole window, but some terminate before 200 mm because the peel failed early; these early/cohesive failures are physically meaningful and are kept in the reported means. This note checks whether that choice affects the configuration values.

The table compares each affected configuration as reported (all valid traces) against a strict subset that keeps only traces covering the full 50-200 mm window to within 0.5 mm. Values are mean ± sample SD in cN/25 mm.

Of 416 valid traces, 17 are partial-window traces, spread over 7 of 42 configurations. The full machine-readable comparison for all configurations is in `publication/generated/data/window_sensitivity.csv`.

| Liner | Sealant | Side | As reported | Strict full-window | Partial traces |
|---|---|---|---|---|---|
| Rossella | U2E | outer | 238.4 ± 73.9 (n=10) | 173.4 ± 51.3 (n=4) | 6 |
| Crosil 42 | T2E | outer | 8.3 ± 1.2 (n=11) | 8.6 ± 0.9 (n=8) | 3 |
| Dolpap | T1E | inner | 6.0 ± 0.7 (n=10) | 6.3 ± 0.6 (n=7) | 3 |
| Crosil 42 | T1E | outer | 5.3 ± 0.5 (n=10) | 5.3 ± 0.5 (n=9) | 1 |
| Dolpap | C1EN | inner | 6.6 ± 1.3 (n=10) | 6.5 ± 1.3 (n=9) | 1 |
| Crosil 42 | C1E | outer | 6.4 ± 0.6 (n=11) | 6.4 ± 0.6 (n=9) | 2 |
| Dolpap | T1E | outer | 5.4 ± 0.3 (n=10) | 5.4 ± 0.3 (n=9) | 1 |

Only Rossella/U2E outer changes materially: the high-force traces are the ones that fail early, so the strict subset gives a lower mean with a wider relative spread on fewer traces. The configuration stays the clear extreme of the matrix under either treatment, and the rank order of the highest-force configurations is unchanged. The remaining affected configurations shift by at most a few tenths of a cN/25 mm.
