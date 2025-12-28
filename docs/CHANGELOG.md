# Changelog

All notable changes to the BME680 Environmental Sensor Monitor project.

## [2.1.0] - 2024-12-28

### ✨ Added

#### Display Enhancements
- **OLED Display View Alternation** - Screen now alternates between two views:
  - Normal view (5 seconds): Detailed sensor readings with T:/H:/P: prefixes
  - Comfort view (3 seconds): Large emoji with comfort status
  - Configurable durations via `_normal_view_duration` and `_comfort_view_duration`
  - All labels in English for consistency

#### Comfort Assessment System
- **`comfort_index.py`** - New comprehensive comfort interpretation module:
  - Temperature comfort levels with recommendations
  - Humidity health ranges and guidance
  - Atmospheric pressure with weather forecasting
  - Heat index calculation for high temperatures
  - Overall comfort assessment combining all factors
- **Hybrid Air Quality Algorithm** - Enhanced air quality detection:
  - Combines absolute scientific thresholds with relative baseline comparison
  - Prevents false "Good" readings when calibrated in contaminated air
  - Uses minimum of both assessments for safety
  - Documented in `docs/AIR_QUALITY_ALGORITHM.md`

### 🔧 Changed

#### Logging Optimization
- **Reduced sensor.log frequency** - Now logs every 15 minutes instead of every reading
  - Configurable via `LOG_INTERVAL_MINUTES` constant (line 23 in sensor.py)
  - Reduces log file growth while maintaining CSV data completeness
  - `measures.csv` still logs every reading for detailed analysis
- **Improved log format** - Clearer structure with detailed conditions summary

#### Display Improvements
- All OLED labels now in English
- Added T:/H:/P: prefixes for clarity
- Changed "Aire:" to "AQ:" for air quality display
- Comfort view shows large centered emoji with status text

### 📚 Documentation
- Updated `docs/AIR_QUALITY_ALGORITHM.md` with hybrid algorithm explanation
- Added `docs/COMFORT_INTERPRETATIONS.md` with detailed interpretation guide
- Updated configuration examples

## [2.0.0] - 2024-12-27

### 🎉 Major Refactoring - Modular Architecture

This is a complete architectural overhaul of the project, transforming it from a monolithic script into a professional, modular package.

### ✨ Added

#### New Modules
- **`bme680_monitor/`** - Main package with modular components:
  - `config.py` - YAML-based configuration management with property accessors
  - `sensor_manager.py` - BME680 sensor interface and data acquisition
  - `air_quality.py` - Air quality calculation engine with baseline management
  - `display.py` - OLED display management with error handling
  - `data_logger.py` - CSV logging with rotation and batch mode support

#### Configuration
- **`config.yaml`** - Centralized YAML configuration file
  - Sensor settings (I2C address, heater config)
  - Calibration parameters (burn-in, thresholds)
  - Air quality thresholds
  - OLED display settings
  - Logging configuration
  - Easy to modify without touching code

#### Documentation
- **`README.md`** - Comprehensive documentation with:
  - Hardware requirements and wiring diagrams
  - Installation instructions
  - Usage examples
  - Troubleshooting guide
  - Data visualization ideas
  - Systemd service setup
- **`MIGRATION.md`** - Detailed migration guide from v1.0 to v2.0
- **`CHANGELOG.md`** - This file

#### Testing
- **`tests/`** - Unit test suite with pytest:
  - `test_config.py` - Configuration loading and property tests
  - `test_air_quality.py` - AQI calculation algorithm tests
  - `test_data_logger.py` - CSV logging and batch mode tests
  - Test coverage for core functionality

#### DevOps
- **`bme680-sensor.service`** - Systemd service file for auto-start
- **`requirements.txt`** - Explicit dependency management with versions
- **`.gitignore`** - Comprehensive ignore rules for Python projects

### 🔄 Changed

#### Code Organization
- **`sensor.py`** - Refactored from 337 lines to 243 lines
  - Now uses modular imports
  - Implements proper logging instead of print statements
  - Better error handling and graceful shutdown
  - Separation of concerns (each module has single responsibility)

#### Logging System
- Migrated from `print()` statements to Python's `logging` module
  - Structured log format with timestamps and levels
  - File logging with automatic rotation (10MB max, 5 backups)
  - Console and file logging configurable independently
  - Log levels: DEBUG, INFO, WARNING, ERROR, CRITICAL

#### Configuration Management
- Moved from hardcoded constants to YAML configuration
  - All magic numbers now in `config.yaml`
  - Easy to adjust without code changes
  - Better for production deployments
  - Validation and defaults built-in

### 🐛 Fixed

#### Critical Bug Fix
- **`sensor_control.sh:53`** - Fixed `stat` command incompatibility
  - **Issue**: Used BSD-style `stat -f%z` which doesn't work on Linux
  - **Fix**: Now tries Linux `stat -c%s` first, falls back to BSD syntax
  - Improves cross-platform compatibility (Linux/macOS)

#### Improvements
- Better error recovery when sensor read fails
- Graceful degradation when OLED display unavailable
- Improved CSV resource management (proper file handling)
- Better I2C error messages with troubleshooting hints

### 🔧 Technical Improvements

#### Code Quality
- Added type hints throughout codebase
- Docstrings for all public classes and methods
- Better separation of concerns
- Reduced code duplication
- Improved error handling

#### Architecture
- **Before**: Monolithic 337-line script
- **After**: 5 focused modules + main script
  - `config.py`: 227 lines - Configuration
  - `sensor_manager.py`: 153 lines - Sensor interface
  - `air_quality.py`: 299 lines - AQI calculations
  - `display.py`: 173 lines - OLED display
  - `data_logger.py`: 216 lines - Data logging
  - `sensor.py`: 243 lines - Main orchestration

#### Dependencies
- Added `PyYAML==6.0.1` for configuration management
- Added `pytest==8.3.3` and `pytest-cov==5.0.0` for testing
- Updated Pillow to `10.4.0` (security update)
- Pinned all versions for reproducibility

### 📊 Project Statistics

#### Before (v1.0)
- 1 Python file (337 lines)
- 1 Bash script
- 0 tests
- 0 configuration files
- Hardcoded settings
- Print-based logging

#### After (v2.0)
- 6 Python modules (1,068 lines)
- 1 main script (243 lines)
- 3 test files with 15+ test cases
- 1 YAML config file
- Comprehensive documentation (3 markdown files)
- Professional logging system
- Systemd service support

### 🎯 Migration Path

Users can migrate from v1.0 to v2.0 with:
1. Install new dependencies: `pip install -r requirements.txt`
2. Review `config.yaml` and adjust settings
3. Test new version: `python3 sensor.py`
4. Old CSV data remains compatible
5. Rollback available via `sensor.py.backup`

See [MIGRATION.md](MIGRATION.md) for detailed instructions.

### 🔮 Future Enhancements (Not in this release)

These were identified as opportunities but not implemented yet:
- [ ] REST API for remote monitoring
- [ ] Web dashboard
- [ ] InfluxDB integration
- [ ] Grafana dashboard templates
- [ ] Email/Telegram alerts
- [ ] Multiple sensor support
- [ ] Historical data analysis tools

### 📝 Notes

- **Backward Compatible**: CSV format unchanged, existing data works
- **Baseline Persistence**: `gas_baseline.json` format unchanged
- **Control Script**: `sensor_control.sh` works with new version
- **Original Backup**: `sensor.py.backup` preserves original implementation

### 🙏 Acknowledgments

This refactoring maintains all original functionality while improving:
- Maintainability
- Testability
- Configurability
- Documentation
- Code quality
- Production readiness

---

## [1.0.0] - 2024-12-06 (Original Version)

### Initial Implementation
- BME680 sensor reading
- OLED display support
- CSV data logging
- Gas baseline calibration
- Air quality scoring
- Bash control script
- Basic error handling

---

**Version Naming**: This project uses [Semantic Versioning](https://semver.org/)
