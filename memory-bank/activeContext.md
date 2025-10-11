## Current Focus

- **DRY Principle Refactoring Completed (October 2025)**: Successfully eliminated code duplication across the codebase with 11 new helper functions, reducing ~140 lines of duplicated code while maintaining full backward compatibility.
- Residual spectrum plotting integrated into main CLI with `--spectra-plot-dir` and `--spectra-summary` options.
- `analysis/plot_residual_spectra.py` serves as a thin wrapper forwarding to the CLI.
- All core functionality validated and working correctly.

## Next Steps
- Consider CLI orchestration refactoring if additional entry points emerge
- Evaluate adding machine-readable outputs (CSV/JSON) for automation users
- Monitor instrument band stability across different rigs and sessions
