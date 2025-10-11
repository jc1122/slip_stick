# Slip-stick Spike Detection

A command-line tool for detecting slip-stick spikes in tensile tester data from FTM 10 instruments. Analyzes force-displacement traces to identify sudden force excursions that indicate slip-stick behavior in adhesive materials.

## What It Does

- **Loads** FTM 10 CSV files with automatic handling of European decimal format (commas)
- **Filters** instrumental noise using dataset-level frequency analysis
- **Detrends** force traces using Savitzky-Golay smoothing
- **Detects** residual spikes above configurable thresholds
- **Reports** spike locations, magnitudes, and statistics
- **Visualizes** results with publication-quality plots (optional)

## Quick Start

### Basic Analysis
```bash
# Analyze a single CSV file
python -m slipstick.cli --input datasets/20250317_C1E_rossella_internal.csv
```

### With Visual Output
```bash
# Generate analysis plots
python -m slipstick.cli \
  --input datasets/20250317_C1E_rossella_internal.csv \
  --plot-dir plots/
```

### Batch Processing
```bash
# Process all CSV files in a directory
for file in datasets/*.csv; do
  python -m slipstick.cli --input "$file" > "results/$(basename "$file" .csv).txt"
done
```

## Use Cases

### 1. **Quality Control** - Detect Adhesive Failures
Monitor adhesive performance by identifying slip-stick events that indicate poor bonding or material defects.

```bash
# Check for spikes in production samples
python -m slipstick.cli \
  --input production_sample.csv \
  --threshold 2.0 \
  --disp-min 20 \
  --disp-max 150
```

### 2. **Research Analysis** - Material Characterization
Analyze how different formulations affect slip-stick behavior across multiple replicates.

```bash
# Compare material formulations
python -m slipstick.cli \
  --input formulation_A.csv \
  --plot-dir results/formulation_A/ \
  --spectra-summary results/formulation_A/spectra.png
```

### 3. **Instrument Validation** - Noise Characterization
Understand instrumental noise characteristics and validate measurement quality.

```bash
# Analyze noise profile
python -m slipstick.cli \
  --input baseline_measurement.csv \
  --noise-plot-dir noise_analysis/ \
  --spectra-plot-dir frequency_analysis/
```

### 4. **Publication Figures** - High-Quality Visualizations
Generate publication-ready plots with consistent styling and proper units.

```bash
# Create vector plots for publication
MPLBACKEND=module://mplcairo.base python -m slipstick.cli \
  --input sample_data.csv \
  --plot-dir figures/ \
  --plot-format pdf \
  --report-unit cN \
  --report-width-mm 25
```

## Command Reference

### Core Options
| Option | Description | Default |
|--------|-------------|---------|
| `--input`, `-i` | Path to FTM 10 CSV file (required) | - |
| `--disp-min` | Minimum displacement for analysis (mm) | 50.0 |
| `--disp-max` | Maximum displacement for analysis (mm) | 200.0 |
| `--threshold` | Spike detection threshold (reporting units) | 1.4 cN/25mm |

### Analysis Options
| Option | Description | Default |
|--------|-------------|---------|
| `--window-seconds` | Savitzky-Golay window length (seconds) | auto (50% of trace) |
| `--polyorder` | Savitzky-Golay polynomial order | 3 |
| `--collection-width-mm` | Original specimen width (mm) | 90.0 |
| `--report-width-mm` | Normalized reporting width (mm) | 25.0 |
| `--report-unit` | Force unit: `N` or `cN` | cN |

### Noise Filtering
| Option | Description | Default |
|--------|-------------|---------|
| `--noise-disp-min` | Noise window start (mm) | 1.0 |
| `--noise-disp-max` | Noise window end (mm) | 5.0 |
| `--instrument-cutoff-factor` | Filter cutoff scaling | 0.8 |

### Output Options
| Option | Description | Default |
|--------|-------------|---------|
| `--plot-dir` | Directory for analysis plots | not saved |
| `--noise-plot-dir` | Directory for noise diagnostic plots | not saved |
| `--spectra-plot-dir` | Directory for frequency spectrum plots | not saved |
| `--spectra-summary` | Multi-panel spectrum summary image | not saved |
| `--plot-format` | Image format: `png`, `pdf`, `svg` | png |
| `--plot-workers` | Parallel plot generation workers | 4 |

## Example Workflows

### Routine Quality Control
```bash
#!/bin/bash
# Daily QC check for adhesive samples

SAMPLE_DIR="daily_samples"
RESULTS_DIR="qc_results"

for csv_file in "$SAMPLE_DIR"/*.csv; do
    base_name=$(basename "$csv_file" .csv)

    # Run analysis with standard settings
    python -m slipstick.cli \
        --input "$csv_file" \
        --plot-dir "$RESULTS_DIR/plots/$base_name" \
        --threshold 1.5 \
        > "$RESULTS_DIR/reports/$base_name.txt"

    # Check for excessive spikes (more than 5)
    spike_count=$(grep "spikes found" "$RESULTS_DIR/reports/$base_name.txt" | cut -d' ' -f1)
    if [ "$spike_count" -gt 5 ]; then
        echo "WARNING: $base_name has $spike_count spikes - investigate!"
    fi
done
```

### Research Study Analysis
```bash
#!/bin/bash
# Analyze multiple conditions in a material study

STUDY_DIR="material_study"
OUTPUT_DIR="analysis_results"

# Process each experimental condition
for condition in A B C; do
    echo "Analyzing condition $condition..."

    python -m slipstick.cli \
        --input "$STUDY_DIR/condition_${condition}.csv" \
        --plot-dir "$OUTPUT_DIR/plots/condition_${condition}" \
        --spectra-summary "$OUTPUT_DIR/spectra/condition_${condition}_spectra.png" \
        --spectra-band-min 1.5 \
        --spectra-band-max 2.5 \
        --report-width-mm 25 \
        > "$OUTPUT_DIR/reports/condition_${condition}.txt"
done

echo "Analysis complete. Check $OUTPUT_DIR for results."
```

### Instrument Calibration Check
```bash
# Verify instrument noise is within acceptable limits

python -m slipstick.cli \
    --input calibration_run.csv \
    --noise-plot-dir calibration_check/ \
    --noise-disp-min 0.5 \
    --noise-disp-max 3.0 \
    --instrument-cutoff-factor 0.7
```

## Output Format

### Console Output
```
Replicate 1 _ 1
  samples=1250 | threshold=1.400 cN / 25 mm
  noise: std=0.045 cN / 25 mm | bias=0.012 cN / 25 mm | max_abs=0.234 cN / 25 mm | n=150 | disp≤5.0 mm | span=1.5 s
  denoised: low-pass filter fc=8.50 Hz (instrument peak ≈ 10.63 Hz)
  time=45.23 s | disp=127.8 mm | residual=2.145 cN / 25 mm (idx 892)

Replicate 1 _ 2
  samples=1248 | threshold=1.400 cN / 25 mm
  noise: std=0.041 cN / 25 mm | bias=0.008 cN / 25 mm | max_abs=0.198 cN / 25 mm | n=148 | disp≤5.0 mm | span=1.5 s
  denoised: low-pass filter fc=8.50 Hz (instrument peak ≈ 10.63 Hz)
  No spikes above threshold in the selected displacement window.

Summary for 20250317_C1E_rossella_internal
  replicates: count=10 | median std=0.043 cN / 25 mm | mean std=0.044 cN / 25 mm | max abs noise=0.245 cN / 25 mm
  bias: median=0.010 cN / 25 mm | range=(0.005, 0.015) cN / 25 mm
  total noise samples: count=1485 | max disp used=5.0 mm
  instrument peak≈10.63 Hz | applied cutoff≈8.50 Hz
  spikes found: 1
```

### Generated Files
- **Analysis plots**: `dataset_replicate.png` - Force trace, baseline, and detected spikes
- **Noise plots**: `dataset_replicate_noise.png` - Noise estimation diagnostics
- **Spectrum plots**: `dataset_replicate_spectrum.png` - Frequency analysis of residuals
- **Summary spectra**: Multi-panel overview of all replicates' frequency content

## Data Format

### Input: FTM 10 CSV Format
- **Header**: 3 rows (labels, names, units)
- **Columns**: Time (s), Force (N), Displacement (mm) for each replicate
- **Decimals**: European format with commas (automatically handled)
- **Layout**: Multiple replicates in wide format

Example CSV structure:
```csv
"1 _ 1",,,"1 _ 2",,,
"Czas","Siła","Przemieszczenie","Czas","Siła","Przemieszczenie"
"sec","N","mm","sec","N","mm"
"0","0,094","0,001","0","0,001","0,001"
"0,01","0,095","0,007","0,01","0,002","0,007"
...
```

## Performance & Tips

- **Memory efficient**: Streams CSV data, processes replicates independently
- **Parallel plotting**: Uses multiple CPU cores for plot generation (default 4 workers)
- **Vector output**: Use `MPLBACKEND=module://mplcairo.base` for fast PDF/SVG generation
- **Batch processing**: Shell loops work well for processing multiple files
- **Threshold tuning**: Start with default 1.4 cN/25mm, adjust based on your materials

## Installation

```bash
# Install core dependencies
pip install numpy scipy

# Install with plotting support
pip install numpy scipy matplotlib

# Optional: Fast vector graphics
pip install mplcairo
```

## Requirements

- Python 3.9+
- NumPy (required)
- SciPy (required)
- Matplotlib (optional, for plotting)
- mplcairo (optional, for fast vector output)
