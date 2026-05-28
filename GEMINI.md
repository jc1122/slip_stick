# Gemini Code-along AI Guidelines

This document provides a high-level overview of the `slip-stick` project for AI coding assistants. For more detailed context, refer to the files in the `memory-bank/` directory.

## 1. Project Overview

The `slip-stick` Python package analyzes tensile tester CSV data to detect slip-stick spikes. It processes force-displacement traces using Savitzky-Golay baseline fitting and instrumental noise-aware filtering. The primary goal is to offer a quick and lightweight way to identify potential slip-stick events in FTM 10 tensile CSV files.

## 2. Architecture

The project follows a clean, modular architecture with a clear separation of concerns:

-   **`slipstick/core.py`**: Contains the core signal processing and analysis logic, including noise estimation, filtering, and spike detection.
-   **`slipstick/io.py`**: Handles CSV parsing and data loading.
-   **`slipstick/models.py`**: Defines the dataclasses used throughout the project.
-   **`slipstick/cli.py`**: Implements the command-line interface using `argparse`.
-   **`slipstick/output.py`**: Manages console output formatting.
-   **`slipstick/plotting.py`**: Provides functions for generating `matplotlib`-based visualizations.
-   **`slipstick/utils.py`**: Includes helper functions for force scaling, validation, and other common tasks.

## 3. Data Flow

The data processing pipeline is as follows:

1.  **Load Data**: Replicates are loaded from a CSV file using `load_replicates()` in `slipstick/io.py`.
2.  **Estimate Noise**: Instrumental noise is estimated using `estimate_instrumental_noise()` in `slipstick/core.py`.
3.  **Filter Data**: A Butterworth filter is applied to the data in `process_replicates()` in `slipstick/core.py`.
4.  **Analyze Data**: Each replicate is analyzed for spikes in `_analyse_replicate()` in `slipstick/core.py`.
5.  **Generate Output**: Results are formatted and printed to the console by functions in `slipstick/output.py`.
6.  **Generate Plots**: If requested, plots are generated in parallel by `_render_plot_jobs()` in `slipstick/plotting.py`.

## 4. Key Patterns

-   **Force Scaling**: Always use `scale_force_value()` or `scale_force_array()` from `slipstick/utils.py` when reporting force values.
-   **Configuration**: All analysis parameters are managed through the `CliConfig` dataclass.
-   **Immutability**: The `slipstick/models.py` file contains all the dataclasses for the project.

## 5. Development Workflow

-   **Running the Tool**:
    ```bash
    # Single dataset
    python -m slipstick.cli --input datasets/20250318_C1E_rossella_internal.csv

    # With plots
    python -m slipstick.cli --input datasets/file.csv --plot-dir plots/ --plot-workers 4
    ```
-   **Testing**: Run the test suite with `python test_refactoring.py`.
-   **Code Quality**: The project uses `black` for formatting and `ruff` for linting, enforced by pre-commit hooks.

## 6. File Organization

-   `datasets/`: Input CSV files.
-   `plots/`: Generated analysis plots.
-   `summaries/`: Text output logs.
-   `memory-bank/`: Detailed project documentation for AI agents.
-   `slipstick/`: Main package source code.
-   `test_refactoring.py`: Unit tests.
