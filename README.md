# BME680 Environmental Sensor Monitor

[![Python](https://img.shields.io/badge/Python-3.7+-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

Professional air quality monitoring system for Raspberry Pi using the BME680 environmental sensor with OLED display, automated calibration, and persistent data logging.

## 🌟 Features

- **Real-time Environmental Monitoring** - Temperature, humidity, pressure, and air quality
- **Intelligent Calibration** - Automatic burn-in and baseline establishment with persistence
- **Hybrid Air Quality Algorithm** - Combines absolute and relative thresholds for accurate readings
- **Comfort Interpretations** - Human-readable assessments with actionable recommendations
- **OLED Display Support** - Alternating views with sensor data and comfort emoji
- **CSV Data Logging** - Structured data export for analysis and dashboards
- **Optimized Logging** - Reduced log frequency (15 min) while maintaining full CSV data
- **Configuration Management** - YAML-based configuration without code changes
- **Professional Logging** - Structured logs with automatic rotation
- **Service Management** - Systemd integration for auto-start
- **Unit Tests** - Comprehensive test coverage
- **Modular Architecture** - Clean, maintainable codebase

## 📁 Project Structure

```
BME680/
├── src/                    # Source code
│   └── bme680_monitor/    # Main package
│       ├── config.py      # Configuration management
│       ├── sensor_manager.py  # BME680 interface
│       ├── air_quality.py     # Hybrid AQI algorithm
│       ├── comfort_index.py   # Comfort interpretations
│       ├── display.py         # OLED display with alternating views
│       └── data_logger.py     # CSV logging
├── tests/                 # Unit tests
├── docs/                  # Documentation
│   ├── AIR_QUALITY_ALGORITHM.md
│   ├── COMFORT_INTERPRETATIONS.md
│   └── CHANGELOG.md
├── scripts/               # Utility scripts
│   ├── sensor_control.sh  # Service control
│   └── bme680-sensor.service  # Systemd service
├── config/                # Configuration files
│   └── config.yaml       # Main configuration
├── sensor.py             # Main entry point
├── setup.py              # Package installation
├── pyproject.toml        # Build configuration
├── Makefile              # Development tasks
└── requirements.txt      # Dependencies
```

## 🚀 Quick Start

### Prerequisites

- Raspberry Pi (any model with I2C)
- BME680 sensor module
- Optional: 0.96" OLED display (SSD1306)

### Installation

```bash
# Clone the repository
git clone <your-repo-url>
cd BME680

# Create virtual environment
make setup-venv
source venv/bin/activate

# Install dependencies
make install

# Or install with development tools
make install-dev
```

### Configuration

Edit `config/config.yaml` to match your hardware:

```yaml
sensor:
  i2c_address: 0x77  # Change to 0x76 if needed

oled:
  enabled: true      # Set to false if no display
  i2c_address: 0x3C
```

### Running

```bash
# Direct execution
make run

# Or using control script
make start   # Start as background service
make status  # Check status
make logs    # View live logs
make stop    # Stop service
```

## 📖 Documentation

Comprehensive documentation is available in the [docs/](docs/) directory:

- **[Full Documentation](docs/README.md)** - Complete usage guide
- **[Migration Guide](docs/MIGRATION.md)** - Upgrading from v1.0
- **[Changelog](docs/CHANGELOG.md)** - Version history
- **[Air Quality Algorithm](docs/AIR_QUALITY_ALGORITHM.md)** - Hybrid algorithm explanation
- **[Comfort Interpretations](docs/COMFORT_INTERPRETATIONS.md)** - Assessment guide

## ⚙️ Configuration

### Logging Frequency

By default, the sensor logs to `sensor.log` every 15 minutes, while `measures.csv` captures every reading. To adjust the log frequency, edit `sensor.py`:

```python
# Line 23 in sensor.py
LOG_INTERVAL_MINUTES = 15  # Change to your preferred interval
```

### OLED Display Timing

The OLED display alternates between two views. To adjust timing, edit `src/bme680_monitor/display.py`:

```python
# Lines 61-62
self._normal_view_duration = 5.0   # Normal view duration (seconds)
self._comfort_view_duration = 3.0  # Comfort view duration (seconds)
```

## 🔧 Development

### Running Tests

```bash
# Run all tests
make test

# Run with coverage
make test-cov

# Lint code
make lint

# Format code
make format

# Type checking
make typecheck
```

### Project Commands

```bash
make help          # Show all available commands
make install       # Install package
make test          # Run tests
make clean         # Clean build artifacts
make build         # Build distribution
```

## 📊 Data Output

Sensor data is logged to `measures.csv` in this format:

| Column | Description |
|--------|-------------|
| timestamp | Reading time |
| temperature_c | Temperature (°C) |
| humidity_rh | Humidity (%) |
| pressure_hpa | Pressure (hPa) |
| gas_resistance_ohms | Gas sensor (Ω) |
| air_quality_index | 0=Cal, 1=Poor, 2=Mod, 3=Good |
| air_quality_label | Human-readable quality |

### Air Quality Algorithm

The system uses a **hybrid algorithm** combining:

1. **Relative Assessment** (baseline comparison):
   ```
   ratio = current_gas_resistance / baseline
   Good:     ratio > 1.35
   Moderate: 0.70 ≤ ratio ≤ 1.35
   Poor:     ratio < 0.70
   ```

2. **Absolute Assessment** (scientific thresholds):
   ```
   Excellent: > 150 kΩ
   Good:      > 100 kΩ
   Moderate:  > 50 kΩ
   Poor:      < 50 kΩ
   ```

The final quality is the **minimum** of both assessments for safety. See [AIR_QUALITY_ALGORITHM.md](docs/AIR_QUALITY_ALGORITHM.md) for details.

## 🛠️ Hardware Setup

### Wiring

```
BME680 → Raspberry Pi
VCC  → 3.3V (Pin 1)
GND  → GND  (Pin 6)
SDA  → SDA  (Pin 3)
SCL  → SCL  (Pin 5)

OLED → Raspberry Pi (shared I2C)
VCC  → 3.3V
GND  → GND
SDA  → SDA
SCL  → SCL
```

### Enable I2C

```bash
sudo raspi-config
# Navigate to: Interface Options → I2C → Enable

# Or use make command
make enable-i2c
```

### Verify Hardware

```bash
# Check I2C devices
make check-hardware

# Should show:
#   0x3C (OLED)
#   0x77 (BME680)
```

## 🔄 Systemd Service

Install as a system service for auto-start:

```bash
# Install service
make install-service

# Enable and start
sudo systemctl enable bme680-sensor
sudo systemctl start bme680-sensor

# Check status
sudo systemctl status bme680-sensor

# View logs
sudo journalctl -u bme680-sensor -f
```

## 🧪 Calibration

For accurate air quality readings:

1. **Position** sensor in clean, outdoor air during calibration
2. **Wait** 5 minutes for burn-in
3. **Sample** baseline for 5 minutes
4. **Avoid** smoke, cooking, or chemical fumes

The baseline is automatically saved and reloaded on restart.

## 📈 Data Visualization

Use the CSV output with:

- **Grafana** - Time-series dashboards
- **Jupyter** - Data analysis notebooks
- **Excel/LibreOffice** - Charts and graphs
- **Python/pandas** - Custom analysis

Example:

```python
import pandas as pd
df = pd.read_csv('measures.csv')
df['timestamp'] = pd.to_datetime(df['timestamp'])
df.set_index('timestamp').plot()
```

## 🤝 Contributing

Contributions welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Write tests for new features
4. Ensure all tests pass: `make test`
5. Format code: `make format`
6. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- [Pimoroni BME680 Library](https://github.com/pimoroni/bme680-python)
- [Luma.OLED](https://github.com/rm-hull/luma.oled)
- BME680 community for calibration insights

## 📞 Support

- **Issues**: [GitHub Issues](https://github.com/yourusername/BME680/issues)
- **Documentation**: [docs/README.md](docs/README.md)
- **Hardware Issues**: Check `make check-hardware`

## 🗺️ Roadmap

- [ ] Web dashboard
- [ ] REST API
- [ ] InfluxDB integration
- [ ] Multi-sensor support
- [ ] Mobile app
- [ ] Email/SMS alerts

---

**Version**: 2.0.0 | **Python**: 3.7+ | **Platform**: Linux (Raspberry Pi)
