# Contributing to BME680 Monitor

Thank you for your interest in contributing to the BME680 Monitor project! This document provides guidelines and instructions for contributing.

## 🤝 Ways to Contribute

- **Bug Reports** - Report issues you encounter
- **Feature Requests** - Suggest new features
- **Code Contributions** - Submit bug fixes or new features
- **Documentation** - Improve or translate documentation
- **Testing** - Test on different hardware configurations

## 🐛 Reporting Bugs

Before creating a bug report:

1. **Check existing issues** - Your bug may already be reported
2. **Update to latest version** - The bug may already be fixed
3. **Verify hardware** - Run `make check-hardware`

When reporting, include:

- **Description** - Clear description of the issue
- **Steps to Reproduce** - Detailed steps
- **Expected Behavior** - What should happen
- **Actual Behavior** - What actually happens
- **Environment** - OS, Python version, hardware
- **Logs** - Relevant log output

## 💡 Suggesting Features

Feature requests are welcome! Please:

1. **Check existing requests** - May already exist
2. **Describe the use case** - Why is this needed?
3. **Provide examples** - How would it work?
4. **Consider alternatives** - Are there other solutions?

## 🔧 Development Setup

### 1. Fork and Clone

```bash
# Fork the repository on GitHub, then:
git clone https://github.com/YOUR_USERNAME/BME680.git
cd BME680
```

### 2. Set Up Environment

```bash
# Create virtual environment
make setup-venv
source venv/bin/activate

# Install with dev dependencies
make install-dev
```

### 3. Verify Setup

```bash
# Run tests
make test

# Check code style
make lint

# Verify imports
make verify-install
```

## 📝 Coding Standards

### Style Guide

- **PEP 8** - Follow Python style guide
- **Line Length** - Max 100 characters
- **Formatting** - Use `black` for formatting
- **Imports** - Organize with `isort`

```bash
# Format code
make format

# Check formatting
make format-check
```

### Code Quality

- **Type Hints** - Add type annotations where possible
- **Docstrings** - Document all public functions/classes
- **Comments** - Explain *why*, not *what*
- **Tests** - Write tests for new features

Example:

```python
def calculate_air_quality(gas_resistance: float, baseline: float) -> tuple[int, str]:
    """
    Calculate air quality index from gas resistance.

    Args:
        gas_resistance: Current gas resistance in Ohms
        baseline: Baseline gas resistance in Ohms

    Returns:
        Tuple of (quality_index, quality_label)
        quality_index: 0-3 (0=Calibrating, 1=Poor, 2=Moderate, 3=Good)
        quality_label: Human-readable label

    Example:
        >>> calculate_air_quality(135000, 100000)
        (3, 'Good')
    """
    ratio = gas_resistance / baseline
    # Implementation...
```

## 🧪 Testing

### Running Tests

```bash
# Run all tests
make test

# Run with coverage
make test-cov

# Run specific test file
pytest tests/test_air_quality.py -v
```

### Writing Tests

- Place tests in `tests/` directory
- Name test files `test_*.py`
- Use descriptive test names
- Cover edge cases
- Mock hardware dependencies

Example:

```python
def test_air_quality_calculation_good():
    """Test that good air quality is detected correctly."""
    calculator = AirQualityCalculator(...)
    calculator.gas_baseline = 100000.0

    index, label = calculator.update(gas_resistance=140000, heat_stable=True)

    assert index == AirQualityLevel.GOOD
    assert label == "Good"
```

## 📋 Pull Request Process

### 1. Create a Branch

```bash
# Create feature branch from main
git checkout -b feature/your-feature-name

# Or for bug fixes
git checkout -b fix/bug-description
```

### 2. Make Changes

- **Commit Often** - Small, logical commits
- **Write Good Messages** - Clear, descriptive
- **Test Continuously** - Run tests as you develop

Commit message format:

```
<type>: <short description>

<optional detailed description>

<optional footer>
```

Types: `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`

Examples:

```
feat: Add support for BME688 sensor

Implement BME688 detection and configuration in sensor_manager.py.
Maintains backward compatibility with BME680.

Closes #42
```

```
fix: Correct baseline persistence on startup

Baseline file was not being loaded correctly when age was exactly 24 hours.
Changed comparison from >= to >.
```

### 3. Run Quality Checks

Before submitting:

```bash
# Format code
make format

# Run all tests
make test

# Check linting
make lint

# Type check
make typecheck

# Run all checks
make all
```

### 4. Submit Pull Request

1. **Push** your branch to your fork
2. **Open PR** on GitHub against `main` branch
3. **Fill template** with description of changes
4. **Link issues** if resolving bugs

PR checklist:

- [ ] Tests pass locally
- [ ] Code is formatted (`make format`)
- [ ] Tests added for new features
- [ ] Documentation updated if needed
- [ ] Commit messages are clear
- [ ] No merge conflicts

### 5. Code Review

- **Respond promptly** to feedback
- **Make requested changes** in new commits
- **Ask questions** if unclear
- **Be patient** - reviews take time

## 📚 Documentation

### Updating Docs

When adding features:

- Update `docs/README.md` with usage examples
- Add docstrings to new functions/classes
- Update `config/config.yaml` comments if adding settings
- Update CHANGELOG.md

### Documentation Style

- **Clear Examples** - Show, don't just tell
- **Complete Information** - Include all parameters
- **Correct Format** - Use proper markdown
- **Test Examples** - Ensure code examples work

## 🏗️ Architecture Guidelines

### Module Organization

```
src/bme680_monitor/
├── config.py          # Configuration only
├── sensor_manager.py  # Hardware interface
├── air_quality.py     # Business logic
├── display.py         # Output handling
└── data_logger.py     # Data persistence
```

### Design Principles

- **Single Responsibility** - One module, one purpose
- **Dependency Injection** - Pass dependencies, don't hardcode
- **Error Handling** - Graceful degradation
- **Testability** - Easy to mock and test

### Adding New Features

1. **Identify Module** - Where does it belong?
2. **Design Interface** - What's the API?
3. **Write Tests First** - TDD approach
4. **Implement** - Keep it simple
5. **Document** - Add docstrings
6. **Integrate** - Update main script if needed

## 🔍 Code Review Criteria

PRs are reviewed for:

- **Functionality** - Does it work as intended?
- **Tests** - Are there adequate tests?
- **Code Quality** - Is it clean and maintainable?
- **Documentation** - Is it documented?
- **Compatibility** - Does it break existing code?
- **Performance** - Any performance impacts?

## 🎯 Good First Issues

Looking for a place to start?

- Issues labeled `good first issue`
- Documentation improvements
- Test coverage improvements
- Code formatting fixes

## 📞 Getting Help

- **Questions** - Open a GitHub Discussion
- **Bugs** - Open a GitHub Issue
- **Ideas** - Start a Discussion first

## 📜 License

By contributing, you agree that your contributions will be licensed under the MIT License.

## 🙏 Recognition

Contributors are recognized in:

- GitHub contributors list
- CHANGELOG.md for significant features
- Special thanks in release notes

Thank you for contributing! 🎉
