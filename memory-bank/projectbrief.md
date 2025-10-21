# Project brief

## Overview
This repository contains a publication-ready Python package for automated detection
and analysis of slip-stick phenomena in tensile test data from FTM 10 testing machines.
The software implements a validated signal processing pipeline combining instrumental
noise characterization, zero-phase filtering, and Savitzky-Golay baseline correction
to identify force residual spikes that indicate slip-stick events.

## Scientific context
Slip-stick friction manifests as periodic force oscillations in adhesive peel tests,
representing discontinuous debonding events at material interfaces. This automated
detection tool enables systematic quantification of slip-stick behavior across large
experimental datasets, supporting materials science research and quality control
applications.

## Requirements
- **Data format**: FTM 10 tensile tester CSV exports (three header rows, comma decimals,
  time/force/displacement column triples per replicate)
- **Analysis window**: Configurable displacement range (default 50–200 mm)
- **Noise characterization**: Pre-test baseline analysis (default 1–5 mm)
- **Filtering**: Optional zero-phase Butterworth denoising based on instrument frequency
- **Baseline removal**: Long-window Savitzky-Golay filter for trend elimination
- **Spike detection**: Configurable threshold-based detection (default 1.4 cN/25 mm)
- **Visualization**: Publication-quality plots (PNG/PDF/SVG) with comprehensive annotations
- **Batch processing**: Multi-core parallel processing for high-throughput analysis

## Goals
- **Scientific rigor**: Validated methodology with documented parameters and assumptions
- **Reproducibility**: Deterministic algorithms, version-controlled dependencies, archived outputs
- **Usability**: Clear CLI interface, sensible defaults, comprehensive documentation
- **Performance**: Parallel processing for batch analysis (2-4× speedup)
- **Publication quality**: Professional plots, proper citations, comprehensive testing

## Scope
The `slipstick` package provides:
- Core signal processing algorithms (`core.py`)
- Data I/O for FTM 10 format (`io.py`)
- Type-safe data structures (`models.py`)
- Command-line interface (`cli.py`)
- Output formatting (`output.py`)
- Visualization tools (`plotting.py`)
- Utility functions (`utils.py`)

Supporting materials:
- Comprehensive documentation (README, CONTRIBUTING, CITATION.cff)
- Memory bank for AI-assisted development context
- Batch processing scripts (`scripts/run_all.py`, `scripts/plot_spike_summary.py`)
- Unit tests (`test_refactoring.py`)
- 47 validated datasets covering multiple material/film combinations

## Publication readiness
- ✅ MIT License for open distribution
- ✅ Citation metadata (CFF format)
- ✅ Comprehensive README with methodology section
- ✅ Contributing guidelines for scientific reproducibility
- ✅ Validated on 47 real-world datasets (>400 replicates)
- ✅ ~45% test coverage with A-grade architecture
- ✅ Clean code passing all linting and formatting checks
