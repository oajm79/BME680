# Project Structure Documentation

This document explains the professional directory structure of the BME680 Monitor project.

## 📁 Directory Layout

```
BME680/                          # Project root
│
├── 📄 Configuration Files       # Build and project config
│   ├── setup.py                 # Setuptools configuration
│   ├── pyproject.toml           # Modern Python project config (PEP 518)
│   ├── requirements.txt         # Runtime dependencies
│   ├── Makefile                 # Development automation
│   └── .gitignore              # Git ignore rules
│
├── 📚 Documentation             # Project documentation
│   ├── README.md                # Main project README (in root)
│   ├── LICENSE                  # MIT License
│   ├── CONTRIBUTING.md          # Contribution guidelines
│   ├── STRUCTURE.md             # This file
│   └── docs/                    # Additional documentation
│       ├── README.md            # Detailed user guide
│       ├── MIGRATION.md         # v1 to v2 migration guide
│       └── CHANGELOG.md         # Version history
│
├── 💻 Source Code               # Application code
│   ├── sensor.py                # Main entry point (root level)
│   └── src/                     # Source directory
│       └── bme680_monitor/      # Main package
│           ├── __init__.py      # Package initialization & exports
│           ├── config.py        # Configuration management
│           ├── sensor_manager.py # BME680 hardware interface
│           ├── air_quality.py   # Air quality calculations
│           ├── display.py       # OLED display management
│           └── data_logger.py   # CSV data logging
│
├── 🧪 Testing                   # Test suite
│   └── tests/
│       ├── __init__.py
│       ├── test_config.py       # Configuration tests
│       ├── test_air_quality.py  # Air quality calculation tests
│       └── test_data_logger.py  # Data logging tests
│
├── ⚙️  Configuration            # Runtime configuration
│   └── config/
│       └── config.yaml          # Main configuration file
│
└── 🛠️  Scripts                  # Utility scripts
    └── scripts/
        ├── sensor_control.sh    # Service management script
        └── bme680-sensor.service # Systemd service definition
```

## 📂 Directory Purposes

### Root Directory (`/`)

**Purpose**: Project metadata, configuration, and entry point

**Files**:
- `sensor.py` - Main executable script (kept in root for easy access)
- `setup.py` - Package installation configuration
- `pyproject.toml` - Modern Python build system config
- `Makefile` - Convenience commands for development
- `requirements.txt` - Production dependencies
- `README.md` - Primary documentation
- `LICENSE` - MIT license text
- `CONTRIBUTING.md` - Contribution guidelines

**Why**: Makes it easy for users to run the project and for developers to understand the setup at a glance.

### Source Directory (`src/`)

**Purpose**: All production source code

**Structure**: Uses the "src layout" - a Python best practice

**Benefits**:
- Prevents accidental imports from development directory
- Forces proper package installation for testing
- Clearer separation between source and other files
- Industry standard for Python packages

**Package**: `bme680_monitor/`
- `__init__.py` - Exports public API
- `config.py` - YAML configuration management
- `sensor_manager.py` - Hardware abstraction layer
- `air_quality.py` - Business logic for AQI
- `display.py` - Output handling (OLED)
- `data_logger.py` - Persistence layer (CSV)

### Tests Directory (`tests/`)

**Purpose**: Unit and integration tests

**Structure**: Mirror the source structure

**Naming Convention**:
- `test_*.py` - Test files (discovered by pytest)
- `Test*` - Test classes
- `test_*` - Test functions

**Benefits**:
- Separate from source code
- Easy to exclude from distribution
- Clear testing scope

### Documentation Directory (`docs/`)

**Purpose**: Detailed documentation beyond README

**Files**:
- `README.md` - Complete user guide (350+ lines)
- `MIGRATION.md` - Upgrade instructions
- `CHANGELOG.md` - Version history and changes

**Why Separate**:
- Keeps root directory clean
- Organized documentation
- Easy to navigate for users
- Can be published to GitHub Pages or Read the Docs

### Configuration Directory (`config/`)

**Purpose**: Runtime configuration files

**Files**:
- `config.yaml` - Main application settings

**Benefits**:
- Separate configuration from code
- Easy to find and modify settings
- Can have environment-specific configs (dev/prod)
- Clean separation of concerns

### Scripts Directory (`scripts/`)

**Purpose**: Utility and deployment scripts

**Files**:
- `sensor_control.sh` - Service management (start/stop/status)
- `bme680-sensor.service` - Systemd service file

**Benefits**:
- Separate operational scripts from application code
- Easy to find deployment-related files
- Clean root directory

## 🔄 Import Structure

### From Application Code

```python
# sensor.py (in root)
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

# Now can import package
from bme680_monitor import Config, SensorManager
```

### From Tests

```python
# tests/test_config.py
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

# Now can import package
from bme680_monitor.config import Config
```

### After Installation

```python
# Once installed via pip, just import directly
from bme680_monitor import Config, SensorManager
```

## 📦 Package Installation

### Development Installation

```bash
# Editable install - changes reflect immediately
pip install -e .

# Or with development dependencies
pip install -e ".[dev]"
```

### User Installation

```bash
# From source
pip install .

# From PyPI (when published)
pip install bme680-monitor
```

## 🚀 Running the Application

### Direct Execution

```bash
# From project root
python sensor.py
```

### Via Make

```bash
make run    # Development
make start  # As service
```

### As Installed Package

```bash
# After pip install
bme680-monitor
```

## 🧪 Running Tests

```bash
# Direct pytest
pytest tests/ -v

# Via Make
make test
make test-cov

# With coverage report
make coverage
```

## 📊 File Organization Principles

### 1. **Separation of Concerns**

- Source code → `src/`
- Tests → `tests/`
- Documentation → `docs/`
- Configuration → `config/`
- Scripts → `scripts/`

### 2. **Standard Conventions**

- Follows Python Packaging User Guide
- Uses PEP 518 (pyproject.toml)
- Standard test layout
- Conventional documentation structure

### 3. **Scalability**

Structure supports growth:
- Easy to add new modules in `src/bme680_monitor/`
- Test structure mirrors source
- Documentation can expand in `docs/`
- Additional scripts go in `scripts/`

### 4. **Tool Compatibility**

Works well with:
- **setuptools** - Package building
- **pytest** - Test discovery
- **black/flake8** - Finds source code correctly
- **mypy** - Type checking
- **coverage** - Code coverage
- **VS Code/PyCharm** - IDE recognition

## 🎯 Design Decisions

### Why `src/` Layout?

**Alternative**: Flat layout (package in root)

**Chosen**: `src/` layout because:
- Prevents import confusion
- Forces proper installation
- Industry best practice
- Better for testing

### Why Separate `config/`?

**Alternative**: Config in root or in package

**Chosen**: Separate directory because:
- Clear separation
- Easy to find/modify
- Can version control separately
- Supports multiple environments

### Why `sensor.py` in Root?

**Alternative**: Move to `src/` or `scripts/`

**Chosen**: Root level because:
- User convenience (easy to find/run)
- Clear entry point
- Matches user expectations
- Still installs as console script

## 🔍 Finding Things

| What | Where | Why |
|------|-------|-----|
| Run the app | `sensor.py` | Main entry point |
| Source code | `src/bme680_monitor/` | All production code |
| Tests | `tests/` | All test files |
| User guide | `docs/README.md` | Detailed docs |
| Settings | `config/config.yaml` | Configuration |
| Start/stop | `scripts/sensor_control.sh` | Service control |
| Development | `Makefile` | Common tasks |

## 📝 Maintenance

### Adding a New Module

1. Create file in `src/bme680_monitor/new_module.py`
2. Add tests in `tests/test_new_module.py`
3. Export in `src/bme680_monitor/__init__.py`
4. Document in `docs/README.md`

### Adding a New Feature

1. Update config schema in `config/config.yaml`
2. Add configuration properties in `src/bme680_monitor/config.py`
3. Implement feature in appropriate module
4. Write tests
5. Update documentation

### Releasing a New Version

1. Update version in `setup.py` and `pyproject.toml`
2. Update `docs/CHANGELOG.md`
3. Run tests: `make test`
4. Build: `make build`
5. Tag release: `git tag v2.x.x`

## 🎓 Best Practices

1. **Keep root clean** - Only essential files
2. **Document structure** - Keep this file updated
3. **Test organization** - Mirror source structure
4. **Clear naming** - Self-explanatory names
5. **Separation** - Each directory has single purpose

## 📚 References

- [Python Packaging User Guide](https://packaging.python.org/)
- [PEP 518](https://www.python.org/dev/peps/pep-0518/) - pyproject.toml
- [pytest documentation](https://docs.pytest.org/)
- [Setuptools documentation](https://setuptools.pypa.io/)

---

**Last Updated**: 2024-12-27 | **Version**: 2.0.0
