# Slip-stick Spike Detection - AI Coding Guidelines

## Project Overview
This Python package analyzes tensile tester CSV data to detect slip-stick spikes. It processes force-displacement traces using Savitzky-Golay baseline fitting and instrumental noise-aware filtering.

## Architecture
- **Core modules**: `slipstick/core.py` (signal processing & analysis), `slipstick/io.py` (CSV parsing), `slipstick/models.py` (dataclasses)
- **CLI**: `slipstick/cli.py` (main entry point with argparse)
- **Output**: `slipstick/output.py` (formatting and console output)
- **Plotting**: `slipstick/plotting.py` (matplotlib-based visualization)
- **Utils**: `slipstick/utils.py` (force scaling, validation, and helper functions)

## Memory Bank Usage
The `memory-bank/` directory contains essential project context that AI agents should read before making changes:

- **`projectbrief.md`**: Project scope, requirements, and goals
- **`techContext.md`**: Technical dependencies, architecture decisions, and usage patterns
- **`systemPatterns.md`**: Repository layout, processing workflows, and operating constraints
- **`productContext.md`**: User-facing purpose, problems solved, and experience goals
- **`progress.md`**: Recent changes, current status, and development history
- **`activeContext.md`**: Current focus areas and next steps

**Always read these files first** when working on the codebase to understand the "why" behind architectural decisions and current development priorities.

## Key Patterns

### Force Scaling
Always scale forces for reporting width using `scale_force_value()` or `scale_force_array()`:
```python
from slipstick.utils import scale_force_value
display_force = scale_force_value(analysis_force_n, config.unit_scale)
```

### Data Flow
1. Load replicates from CSV (`load_replicates()`)
2. Estimate instrumental noise (`estimate_instrumental_noise()`)
3. Apply Butterworth filtering (`process_replicates()`)
4. Analyze each replicate (`_analyse_replicate()`)
5. Generate plots in parallel (`_render_plot_jobs()`)

### CLI Configuration
Use `CliConfig` dataclass for all analysis parameters. Force values are always in Newtons internally, scaled for display.

### Testing
Run tests with `python test_refactoring.py`. Focus on helper functions in `utils.py`, `core.py`, `output.py`, and `plotting.py`.

## Development Workflow

### Running the Tool
```bash
# Single dataset
python -m slipstick.cli --input datasets/20250317_C1E_rossella_internal.csv

# With plots
python -m slipstick.cli --input datasets/file.csv --plot-dir plots/ --plot-workers 4

# Batch processing
for f in datasets/*.csv; do
  python -m slipstick.cli --input "$f" > "summaries/$(basename "$f" .csv).txt"
done
```

### Code Quality
- **Formatting**: Black + Ruff (via pre-commit)
- **Linting**: Ruff with `--fix`
- **Testing**: Comprehensive unit tests in `test_refactoring.py`
- **Architecture**: Clean separation of concerns with dedicated modules for I/O, analysis, plotting, and output

### Common Tasks
- **Add plot type**: Extend `plotting.py` helpers, update CLI args in `cli.py`
- **Modify analysis**: Update signal processing functions in `core.py`
- **Change output format**: Modify functions in `output.py`
- **Change defaults**: Update constants in `cli.py` (forces in Newtons)

## File Organization
- `datasets/`: Input CSV files (FTM 10 format)
- `plots/`: Generated analysis plots
- `summaries/`: Text output logs
- `memory-bank/`: Project documentation
- `analysis/`: Auxiliary scripts
- `slipstick/`: Main package code

## Dependencies
- NumPy + SciPy (required for signal processing)
- matplotlib (optional, for plotting)
- Install: `pip install -r requirements.txt`

## Code Quality Standards
- All modules follow Single Responsibility Principle (SRP)
- DRY principle applied - no code duplication
- Test coverage ~45% with comprehensive unit tests
- All code passes Ruff linting and Black formatting</content>
<parameter name="filePath">/workspaces/slip_stick/.github/copilot-instructions.md
