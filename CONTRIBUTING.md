# Contributing to Slip-Stick Spike Detection

Thank you for your interest in contributing to this project! This guide will help you get started with contributing code, documentation, or scientific insights.

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Workflow](#development-workflow)
- [Code Standards](#code-standards)
- [Testing](#testing)
- [Documentation](#documentation)
- [Submitting Changes](#submitting-changes)
- [Scientific Reproducibility](#scientific-reproducibility)

## Code of Conduct

This project adheres to professional and respectful collaboration standards. Please:
- Be respectful and constructive in all interactions
- Welcome diverse perspectives and approaches
- Focus on what is best for the scientific community
- Acknowledge contributions from others

## Getting Started

### Prerequisites

- Python 3.11 or higher
- Git for version control
- Familiarity with signal processing concepts
- Understanding of tensile testing methods (helpful but not required)

### Setting Up Development Environment

1. **Fork and clone the repository**
   ```bash
   git clone https://github.com/[your-username]/slip_stick.git
   cd slip_stick
   ```

2. **Create a virtual environment**
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   pip install ruff black pre-commit pytest matplotlib pandas
   ```

4. **Install pre-commit hooks**
   ```bash
   pre-commit install
   ```

5. **Run tests to verify setup**
   ```bash
   python test_refactoring.py
   ```

## Development Workflow

### Branch Strategy

- `main`: Stable, publication-ready code
- `develop`: Integration branch for new features
- `feature/[name]`: Individual feature development
- `bugfix/[name]`: Bug fixes
- `docs/[name]`: Documentation improvements

### Making Changes

1. Create a new branch from `develop`:
   ```bash
   git checkout develop
   git pull origin develop
   git checkout -b feature/your-feature-name
   ```

2. Make your changes following the code standards below

3. Test your changes thoroughly

4. Commit with clear, descriptive messages:
   ```bash
   git commit -m "Add: Brief description of changes"
   ```

## Code Standards

### Python Style

- **Formatting**: Black with default settings (88 character line length)
- **Linting**: Ruff with project configuration
- **Type hints**: Encouraged for new code, especially public APIs
- **Docstrings**: Google-style for all public functions and classes

### Code Organization

Follow the existing modular structure:
- `slipstick/core.py`: Signal processing algorithms
- `slipstick/io.py`: Data loading and parsing
- `slipstick/models.py`: Data structures (dataclasses)
- `slipstick/cli.py`: Command-line interface
- `slipstick/output.py`: Console output formatting
- `slipstick/plotting.py`: Visualization functions
- `slipstick/utils.py`: Helper functions

### Design Principles

1. **Single Responsibility**: Each function/class has one clear purpose
2. **DRY (Don't Repeat Yourself)**: Extract common code into utilities
3. **Immutability**: Prefer immutable data structures where possible
4. **Clear Naming**: Use descriptive variable and function names
5. **Minimal Dependencies**: Justify any new dependencies

### Example Function

```python
def estimate_instrumental_noise(
    replicate: Replicate,
    noise_disp_min: float,
    noise_disp_max: float,
    noise_force_onset: float | None = None,
    window_seconds: float | None = None,
) -> NoiseEstimate:
    """Estimate instrumental noise from a quiet pre-test window.

    Args:
        replicate: The replicate data containing time, force, and displacement.
        noise_disp_min: Start of noise window in mm.
        noise_disp_max: End of noise window in mm.
        noise_force_onset: Optional force threshold to detect specimen engagement.
        window_seconds: Optional window length for baseline fitting.

    Returns:
        NoiseEstimate containing noise statistics and spectral information.

    Raises:
        ValueError: If noise window contains insufficient samples.
    """
    # Implementation here
    ...
```

## Testing

### Running Tests

```bash
# Run all tests
python test_refactoring.py

# Run with verbose output
python test_refactoring.py -v
```

### Writing Tests

- Place tests in `test_refactoring.py` or create new test files
- Test both expected behavior and edge cases
- Use descriptive test names: `test_scale_force_array_with_zero_values`
- Include docstrings explaining what is being tested

### Test Coverage Goals

- Aim for >80% coverage for new code
- All core algorithms must have tests
- Critical paths (noise estimation, spike detection) require comprehensive tests

## Documentation

### Code Documentation

- **Docstrings**: Required for all public functions, classes, and modules
- **Comments**: Use sparingly for complex logic, prefer self-documenting code
- **Type hints**: Helps with IDE support and catches errors early

### User Documentation

- **README.md**: High-level overview and quick start
- **Memory Bank**: Detailed context for AI assistants and developers
- **CLI help**: Keep `--help` text concise and accurate

### Scientific Documentation

When adding new algorithms or methods:
1. Document the scientific rationale
2. Cite relevant literature if applicable
3. Explain parameter choices and defaults
4. Provide validation results if available

## Submitting Changes

### Pull Request Process

1. **Ensure all tests pass**
   ```bash
   python test_refactoring.py
   ruff check .
   black --check .
   ```

2. **Update documentation** if needed:
   - README.md for user-facing changes
   - Docstrings for API changes
   - Memory bank for architectural changes
   - CHANGELOG.md (if it exists)

3. **Create a pull request** with:
   - Clear title describing the change
   - Description of what changed and why
   - Reference to related issues (e.g., "Fixes #42")
   - Screenshots for UI/plotting changes
   - Performance impacts (if relevant)

4. **Respond to review feedback** promptly and professionally

### Pull Request Template

```markdown
## Description
Brief description of changes

## Motivation and Context
Why is this change needed? What problem does it solve?

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Documentation update
- [ ] Performance improvement
- [ ] Code refactoring

## Testing
- [ ] All existing tests pass
- [ ] Added new tests for new functionality
- [ ] Manual testing performed

## Checklist
- [ ] Code follows project style guidelines
- [ ] Documentation has been updated
- [ ] Changes are backwards compatible (or breaking changes are documented)
```

## Scientific Reproducibility

### Ensuring Reproducibility

When contributing analysis methods:

1. **Deterministic algorithms**: Avoid randomness or document seed usage
2. **Parameter documentation**: Document all parameters and their physical meaning
3. **Validation**: Include test data or validation against known results
4. **Version control**: Ensure results can be reproduced with specific versions

### Data Handling

- **No proprietary data**: Keep test data anonymized and shareable
- **Minimal examples**: Provide small test datasets for validation
- **Clear provenance**: Document data sources and processing steps

### Algorithm Modifications

When modifying signal processing algorithms:

1. **Document rationale**: Explain why the change improves results
2. **Compare methods**: Show before/after comparisons
3. **Parameter sensitivity**: Test across parameter ranges
4. **Edge cases**: Ensure robustness to noisy or unusual data

## Questions or Need Help?

- **GitHub Issues**: Ask questions or discuss ideas
- **Documentation**: Check the README and memory bank files
- **Examples**: Look at existing code for patterns and conventions
- **Contact**: Reach out to maintainers if unsure about contribution approach

Thank you for contributing to making slip-stick analysis more accessible and reproducible!
