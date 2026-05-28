# Quick Reference Guide

## Installation

```bash
# Clone repository
git clone https://github.com/jc1122/slip_stick.git
cd slip_stick

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Optional: Install plotting support
pip install matplotlib
```

## Basic Usage

### Single File Analysis

```bash
# Analyze one dataset
python -m slipstick.cli --input datasets/your_file.csv

# With plots
python -m slipstick.cli --input datasets/your_file.csv --plot-dir plots/

# Save all outputs
python -m slipstick.cli --input datasets/your_file.csv \
    --plot-dir plots/analysis/ \
    --noise-plot-dir plots/noise/ \
    --spectra-plot-dir plots/spectra/ \
    > results/summary.txt
```

### Batch Processing

```bash
# Process all datasets (recommended)
python scripts/run_all.py --slipstick-workers 4 --plot-workers 4

# Process limited number
python scripts/run_all.py --max-datasets 10

# Adjust for your system
# For 16-core system: --slipstick-workers 4 --plot-workers 4
# For 8-core system:  --slipstick-workers 2 --plot-workers 4
# For 4-core system:  --slipstick-workers 1 --plot-workers 4
```

### Generate Spike Summary

```bash
# Create heatmap visualizations
python scripts/plot_spike_summary.py
# Outputs: spike_summary_internal.png, spike_summary_external.png
```

## Common Options

| Option | Description | Default |
|--------|-------------|---------|
| `--input, -i` | Input CSV file path | Required |
| `--threshold` | Detection threshold (cN/25 mm) | 1.4 |
| `--disp-min` | Analysis start (mm) | 50.0 |
| `--disp-max` | Analysis end (mm) | 200.0 |
| `--noise-disp-min` | Noise window start (mm) | 1.0 |
| `--noise-disp-max` | Noise window end (mm) | 5.0 |
| `--plot-dir` | Analysis plots directory | None |
| `--plot-format` | Plot format (png/pdf/svg) | png |
| `--report-unit` | Output unit (N/cN) | cN |
| `--collection-width-mm` | Test specimen width | 90.0 |
| `--report-width-mm` | Reporting width | 25.0 |

## Output Files

### Text Summaries

Location: `summaries/dataset_name.txt`

Contains:
- Per-replicate spike counts and locations
- Noise statistics (std, bias, max)
- Filter settings (if applied)
- Dataset-level summary

### Analysis Plots

Location: `plots/analysis/dataset_replicate.png`

Shows:
- Force trace with Savitzky-Golay baseline
- Residual with detection threshold
- Detected spikes marked with symbols

### Noise Plots

Location: `plots/noise/dataset_replicate_noise.png`

Shows:
- Raw force in noise window (1-5 mm)
- Baseline fit
- Residual distribution
- Noise statistics

### Spectra Plots

Location: `plots/spectra/dataset_replicate_spectrum.png`

Shows:
- Residual periodogram (power vs frequency)
- Dominant peak frequency
- Analysis band of interest

## Parameter Tuning

### Adjusting Detection Threshold

**Too few spikes detected:**
```bash
python -m slipstick.cli --input data.csv --threshold 1.0
```

**Too many false positives:**
```bash
python -m slipstick.cli --input data.csv --threshold 2.0
```

**Rule of thumb:** Set threshold to 5-10× noise standard deviation

### Adjusting Analysis Window

**For shorter tests:**
```bash
python -m slipstick.cli --input data.csv --disp-min 30 --disp-max 150
```

**For longer tests:**
```bash
python -m slipstick.cli --input data.csv --disp-min 50 --disp-max 300
```

**Guideline:** Include only stable plateau region

### Adjusting Noise Window

**If specimen engages early:**
```bash
python -m slipstick.cli --input data.csv --noise-disp-min 0.5 --noise-disp-max 3.0
```

**If start-up transients extend further:**
```bash
python -m slipstick.cli --input data.csv --noise-disp-min 2.0 --noise-disp-max 7.0
```

**Guideline:** Choose range with flat, low-amplitude force

## Troubleshooting

### No spikes detected

**Possible causes:**
- Threshold too high
- Analysis window misses spike region
- Baseline tracking spikes instead of trend

**Solutions:**
```bash
# Lower threshold
--threshold 1.0

# Adjust analysis window
--disp-min 30 --disp-max 180

# Check plots to verify baseline is smooth
--plot-dir debug/
```

### Too many false positives

**Possible causes:**
- Threshold too low
- High instrument noise
- Noise window contaminated

**Solutions:**
```bash
# Raise threshold
--threshold 2.0

# More aggressive filtering
--instrument-cutoff-factor 0.6

# Adjust noise window
--noise-disp-min 2.0 --noise-disp-max 4.0
```

### Processing errors

**"No replicates found":**
- Check CSV format (3 header rows, time/force/displacement columns)
- Verify file encoding (should be CP1250 or UTF-8)

**"Insufficient samples":**
- Analysis window may be too narrow
- Check replicate has data in specified displacement range

**"Cannot apply filter":**
- Replicate too short for filter padding
- Increase sample count or skip filtering for short traces

## Performance Tips

### For large batch processing:

```bash
# Optimal for 16-core system
python scripts/run_all.py --slipstick-workers 4 --plot-workers 4

# Reduce memory usage
python scripts/run_all.py --slipstick-workers 2 --plot-workers 2

# Process subset for testing
python scripts/run_all.py --max-datasets 5
```

### For publication-quality plots:

```bash
# Generate PDF plots
python -m slipstick.cli --input data.csv \
    --plot-dir figures/ \
    --plot-format pdf \
    --report-unit cN

# Generate SVG for editing
python -m slipstick.cli --input data.csv \
    --plot-dir figures/ \
    --plot-format svg
```

### For minimal output:

```bash
# Text only (no plots)
python -m slipstick.cli --input data.csv > summary.txt

# Quiet mode (errors only)
python -m slipstick.cli --input data.csv 2>&1 | grep -i error
```

## File Format Requirements

### Input CSV Structure

```
Header Row 1,Header Row 2,Header Row 3,...
Time,Force,Displacement,Time,Force,Displacement,...
0.00,0.123,0.00,0.00,0.145,0.00,...
0.01,0.125,0.05,0.01,0.147,0.05,...
...
```

**Requirements:**
- 3 header rows
- Column triples: (Time, Force, Displacement) per replicate
- Comma decimal separators (automatically handled)
- Encoding: CP1250 or UTF-8

### Output Directory Structure

```
project/
├── datasets/          # Input CSV files
├── summaries/         # Text output (auto-created)
├── plots/
│   ├── analysis/      # Force + baseline + residual plots
│   ├── noise/         # Noise characterization plots
│   └── spectra/       # Residual frequency spectrum plots
├── spike_summary_internal.png   # Summary heatmap
└── spike_summary_external.png   # Summary heatmap
```

## Quick Diagnostics

### Check installation:

```bash
python -c "import slipstick; print('OK')"
python -c "import numpy, scipy; print('OK')"
python -c "import matplotlib; print('Plotting available')"
```

### Test on sample data:

```bash
# Should complete without errors
python -m slipstick.cli --input datasets/20250318_C1E_rossella_internal.csv

# Should generate plots
python -m slipstick.cli \
    --input datasets/20250318_C1E_rossella_internal.csv \
    --plot-dir test_plots/
```

### Verify outputs:

```bash
# Check summary was created
ls summaries/*.txt

# Check plots were generated
ls plots/analysis/*.png
ls plots/noise/*.png
ls plots/spectra/*.png

# Count total files
echo "Summaries: $(ls summaries/*.txt | wc -l)"
echo "Plots: $(ls plots/**/*.png | wc -l)"
```

## Getting Help

### Documentation

- **README.md** - Overview and quick start
- **docs/ALGORITHM.md** - Detailed algorithm description
- **docs/VALIDATION.md** - Validation methodology
- **CONTRIBUTING.md** - Contributing guidelines
- **memory-bank/** - Development context

### Command-line help

```bash
# Full help
python -m slipstick.cli --help

# Version info
python -c "import slipstick; print(slipstick.__version__)"
```

### Support

- **GitHub Issues**: https://github.com/jc1122/slip_stick/issues
- **Email**: [contact email from README]

## Citation

```bibtex
@software{slipstick2025,
  author = {[Author Names]},
  title = {Slip-Stick Spike Detection: Automated Analysis of Tensile Test Data},
  year = {2025},
  version = {1.0.0},
  url = {https://github.com/jc1122/slip_stick}
}
```

See `CITATION.cff` for complete citation metadata.

## Examples

### Example 1: Quick analysis

```bash
python -m slipstick.cli \
    --input datasets/sample.csv \
    --threshold 1.5 \
    > results/sample_summary.txt
```

### Example 2: Full analysis with plots

```bash
python -m slipstick.cli \
    --input datasets/sample.csv \
    --plot-dir plots/analysis/ \
    --noise-plot-dir plots/noise/ \
    --spectra-plot-dir plots/spectra/ \
    --plot-format png \
    --threshold 1.4 \
    --report-unit cN \
    > summaries/sample.txt
```

### Example 3: Custom parameters

```bash
python -m slipstick.cli \
    --input datasets/sample.csv \
    --disp-min 30 \
    --disp-max 180 \
    --threshold 2.0 \
    --noise-disp-min 2.0 \
    --noise-disp-max 6.0 \
    --instrument-cutoff-factor 0.7 \
    --plot-dir custom_analysis/
```

### Example 4: Batch processing

```bash
# Process all with default settings
python scripts/run_all.py

# Custom worker configuration
python scripts/run_all.py \
    --slipstick-workers 2 \
    --plot-workers 4 \
    --max-datasets 20

# Generate spike summaries
python scripts/plot_spike_summary.py
```

## Version History

- **v1.0.0 (2025-10-21)**: Initial publication release
  - Complete signal processing pipeline
  - Comprehensive documentation
  - Validated on 42 publication datasets
  - Publication-ready outputs
