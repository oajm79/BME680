# Migration Guide: v1.0 → v2.0

This guide helps you migrate from the original monolithic `sensor.py` to the new modular version 2.0.

## 🎯 What Changed?

### Architecture
- **Before**: Single 337-line `sensor.py` file
- **After**: Modular package with 5 separate modules + main script

### Key Improvements
1. ✅ **Modular design** - Separated concerns into focused modules
2. ✅ **Configuration file** - YAML-based configuration instead of hardcoded values
3. ✅ **Professional logging** - Using Python's `logging` module with rotation
4. ✅ **Unit tests** - Basic test coverage for core functionality
5. ✅ **Better error handling** - Improved recovery and graceful degradation
6. ✅ **Type hints** - Better code documentation and IDE support

## 📦 New File Structure

```
BME680/
├── bme680_monitor/          # NEW: Main package
│   ├── __init__.py
│   ├── config.py            # Configuration management
│   ├── sensor_manager.py    # BME680 sensor interface
│   ├── air_quality.py       # Air quality calculations
│   ├── display.py           # OLED display management
│   └── data_logger.py       # CSV logging
├── tests/                   # NEW: Unit tests
│   ├── __init__.py
│   ├── test_config.py
│   ├── test_air_quality.py
│   └── test_data_logger.py
├── sensor.py                # Refactored main script
├── sensor.py.backup         # Your original file (backup)
├── config.yaml              # NEW: Configuration file
├── requirements.txt         # Updated dependencies
├── bme680-sensor.service    # NEW: Systemd service
├── sensor_control.sh        # Updated (bug fix)
├── README.md                # Enhanced documentation
└── MIGRATION.md             # This file
```

## 🚀 Migration Steps

### Step 1: Update Dependencies

The new version requires PyYAML for configuration:

```bash
source venv/bin/activate
pip install -r requirements.txt
```

### Step 2: Review Configuration

Your old settings are now in `config.yaml`. Review and customize:

```bash
# Edit configuration
nano config.yaml

# Key settings to review:
# - sensor.i2c_address (was hardcoded at line 18)
# - calibration.burn_in_duration (was BURN_IN_DURATION_S)
# - calibration.recalibration_interval (was RECALIBRATION_INTERVAL_S)
# - oled.enabled (set to false if you don't have OLED)
```

### Step 3: Test the New Version

Run the new version directly:

```bash
python3 sensor.py
```

Expected output:
```
2024-XX-XX XX:XX:XX - __main__ - INFO - ============================================
2024-XX-XX XX:XX:XX - __main__ - INFO - BME680 Environmental Sensor Monitor v2.0.0
2024-XX-XX XX:XX:XX - __main__ - INFO - ============================================
2024-XX-XX XX:XX:XX - bme680_monitor.sensor_manager - INFO - BME680 sensor detected at address 0x77
...
```

### Step 4: Verify Data Compatibility

The new version produces identical CSV output:

```bash
# Check CSV headers match
head -1 measures.csv

# Should show:
# timestamp,temperature_c,humidity_rh,pressure_hpa,gas_resistance_ohms,air_quality_index,air_quality_label
```

Your existing `measures.csv` will continue to work. New data appends seamlessly.

### Step 5: Update Control Script (if needed)

The `sensor_control.sh` script works with the new version without changes. The bug fix for `stat` command improves Linux compatibility.

Test it:
```bash
./sensor_control.sh status
./sensor_control.sh start
./sensor_control.sh logs
```

## 🔄 Configuration Mapping

Here's how old hardcoded values map to new config:

| Old Code (sensor.py) | New Config (config.yaml) |
|---------------------|-------------------------|
| Line 18: `bme680.BME680(0x77)` | `sensor.i2c_address: 0x77` |
| Line 34: `set_gas_heater_temperature(320)` | `sensor.gas_heater_temperature: 320` |
| Line 35: `set_gas_heater_duration(150)` | `sensor.gas_heater_duration: 150` |
| Line 46: `BURN_IN_DURATION_S = 300` | `calibration.burn_in_duration: 300` |
| Line 47: `BASELINE_SAMPLING_DURATION_S = 300` | `calibration.baseline_sampling_duration: 300` |
| Line 48: `GOOD_AIR_THRESHOLD_RATIO = 1.35` | `air_quality.good_threshold: 1.35` |
| Line 49: `POOR_AIR_THRESHOLD_RATIO = 0.70` | `air_quality.poor_threshold: 0.70` |
| Line 51: `RECALIBRATION_INTERVAL_S = 14400` | `calibration.recalibration_interval: 14400` |
| Line 54-55: Clean air range | `air_quality.clean_air_min/max` |
| Line 125: `address=0x3C` | `oled.i2c_address: 0x3C` |
| Line 140: `CSV_FILENAME = "measures.csv"` | `data_logging.csv_filename: "measures.csv"` |

## 🧪 Running Tests

New unit tests ensure core functionality works:

```bash
# Install test dependencies (if not already)
pip install pytest pytest-cov

# Run tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=bme680_monitor --cov-report=html
```

Expected output:
```
tests/test_air_quality.py::TestAirQualityCalculator::test_initialization PASSED
tests/test_air_quality.py::TestAirQualityCalculator::test_air_quality_good PASSED
tests/test_config.py::TestConfig::test_load_config PASSED
tests/test_data_logger.py::TestDataLogger::test_log_reading PASSED
...
```

## 🔧 Troubleshooting

### Issue: "No module named 'yaml'"

**Solution**: Install PyYAML
```bash
pip install PyYAML
```

### Issue: "Configuration file not found"

**Solution**: Ensure `config.yaml` exists in the project directory
```bash
ls -la config.yaml
# If missing, copy from backup or recreate
```

### Issue: "OLED display fails to initialize"

**Solution**: Disable OLED in config if you don't have the hardware
```yaml
oled:
  enabled: false
```

### Issue: Existing baseline file not recognized

**Solution**: The new version uses the same `gas_baseline.json` format. No changes needed.

### Issue: Different log format

**Solution**: The new version uses structured logging. Old logs remain unchanged. Configure format in `config.yaml`:
```yaml
logging:
  format: "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
```

## 🔙 Rollback Plan

If you need to revert to the old version:

```bash
# Restore original sensor.py
cp sensor.py.backup sensor.py

# Continue using old script
python3 sensor.py
```

Your data files (`measures.csv`, `gas_baseline.json`) work with both versions.

## ✨ New Features You Can Use

### 1. Easy Configuration Changes

No more editing Python code! Just update `config.yaml`:

```bash
nano config.yaml
# Change sampling_interval from 1 to 5 seconds
# Change recalibration_interval
# Toggle OLED on/off
```

### 2. Better Logging

View structured logs with levels:

```bash
# View logs with timestamps and levels
tail -f logs/sensor.log

# Change log level in config.yaml
logging:
  level: DEBUG  # For detailed debugging
```

### 3. Systemd Service (Auto-start)

Install as a system service:

```bash
# Copy service file
sudo cp bme680-sensor.service /etc/systemd/system/

# Edit paths if needed
sudo nano /etc/systemd/system/bme680-sensor.service

# Enable and start
sudo systemctl daemon-reload
sudo systemctl enable bme680-sensor
sudo systemctl start bme680-sensor

# Check status
sudo systemctl status bme680-sensor

# View logs
sudo journalctl -u bme680-sensor -f
```

### 4. CSV Log Rotation

Large CSV files are automatically rotated:

```python
# In your code or config, the logger now supports rotation
data_logger.rotate_if_needed(max_size_mb=100)
```

## 📚 Further Reading

- [README.md](README.md) - Full documentation
- [config.yaml](config.yaml) - All configuration options
- Module documentation:
  - [bme680_monitor/config.py](bme680_monitor/config.py) - Configuration
  - [bme680_monitor/air_quality.py](bme680_monitor/air_quality.py) - AQI calculations
  - [bme680_monitor/display.py](bme680_monitor/display.py) - OLED display
  - [bme680_monitor/data_logger.py](bme680_monitor/data_logger.py) - CSV logging

## ❓ Questions?

If you encounter issues during migration, check:

1. Python version: `python3 --version` (needs 3.7+)
2. Dependencies: `pip list | grep -E "bme680|luma|yaml"`
3. I2C enabled: `sudo i2cdetect -y 1`
4. File permissions: `ls -la sensor.py config.yaml`

---

**Migration completed successfully? Delete this file and `sensor.py.backup` to clean up!**

```bash
rm MIGRATION.md sensor.py.backup
```
