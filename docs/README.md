# BME680 Environmental Sensor Monitor

Professional air quality monitoring system using BME680 sensor with OLED display, automated calibration, and persistent data logging.

![BME680 Sensor](https://img.shields.io/badge/Sensor-BME680-blue)
![Python](https://img.shields.io/badge/Python-3.7+-green)
![License](https://img.shields.io/badge/License-MIT-yellow)

## 📋 Features

- **Real-time monitoring** of temperature, humidity, pressure, and air quality
- **Intelligent calibration** with automatic burn-in and baseline establishment
- **Persistent baseline** storage with 24-hour validity
- **OLED display** support (128x64 SSD1306)
- **CSV data logging** for analysis and dashboards
- **Automatic recalibration** every 4 hours
- **Service management** script for easy start/stop/status control
- **Log rotation** to prevent disk space issues

## 🔧 Hardware Requirements

### Components
- Raspberry Pi (any model with I2C support)
- BME680 Environmental Sensor
- 0.96" OLED Display (SSD1306, 128x64, I2C)
- Jumper wires

### Wiring Diagram

```
BME680 Sensor → Raspberry Pi
────────────────────────────
VCC  → 3.3V (Pin 1)
GND  → GND  (Pin 6)
SDA  → SDA  (Pin 3, GPIO 2)
SCL  → SCL  (Pin 5, GPIO 3)

OLED Display → Raspberry Pi
────────────────────────────
VCC  → 3.3V (Pin 17)
GND  → GND  (Pin 20)
SDA  → SDA  (Pin 3, GPIO 2) [shared with BME680]
SCL  → SCL  (Pin 5, GPIO 3) [shared with BME680]
```

**Note**: Both devices share the same I2C bus (SDA/SCL).

### I2C Addresses
- BME680: `0x77` (or `0x76` on some models)
- OLED: `0x3C`

Verify with: `sudo i2cdetect -y 1`

## 🚀 Installation

### 1. Enable I2C on Raspberry Pi

```bash
sudo raspi-config
# Navigate to: Interface Options → I2C → Enable
sudo reboot
```

### 2. Install System Dependencies

```bash
sudo apt-get update
sudo apt-get install -y python3-pip python3-venv i2c-tools git
```

### 3. Clone Repository

```bash
git clone <your-repo-url>
cd BME680
```

### 4. Create Virtual Environment

```bash
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

### 5. Verify I2C Devices

```bash
sudo i2cdetect -y 1
```

Expected output:
```
     0  1  2  3  4  5  6  7  8  9  a  b  c  d  e  f
00:          -- -- -- -- -- -- -- -- -- -- -- -- --
10: -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- --
20: -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- --
30: -- -- -- -- -- -- -- -- -- -- -- -- 3c -- -- --
40: -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- --
50: -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- --
60: -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- --
70: -- -- -- -- -- -- -- 77
```

## 🎯 Usage

### Using the Control Script (Recommended)

```bash
# Start monitoring
./sensor_control.sh start

# Check status
./sensor_control.sh status

# View live logs
./sensor_control.sh logs

# Stop monitoring
./sensor_control.sh stop

# Restart monitoring
./sensor_control.sh restart
```

### Manual Execution

```bash
source venv/bin/activate
python3 sensor.py
```

Press `Ctrl+C` to stop.

## 📊 Data Output

### CSV File Format

Data is saved to `measures.csv`:

| Column | Description | Unit |
|--------|-------------|------|
| `timestamp` | Date and time | YYYY-MM-DD HH:MM:SS |
| `temperature_c` | Temperature | °C |
| `humidity_rh` | Relative humidity | % |
| `pressure_hpa` | Atmospheric pressure | hPa |
| `gas_resistance_ohms` | Gas sensor resistance | Ω |
| `air_quality_index` | Numeric AQI (0-3) | 0=Cal, 1=Poor, 2=Mod, 3=Good |
| `air_quality_label` | Human-readable quality | Text |

### Air Quality Index (AQI)

The system uses a **ratio-based algorithm**:

```
AQI = current_gas_resistance / baseline_gas_resistance

Good     : ratio > 1.35  (Better than baseline)
Moderate : 0.70 ≤ ratio ≤ 1.35
Poor     : ratio < 0.70  (Worse than baseline)
```

**Typical Clean Air Baseline**: 50kΩ - 200kΩ

## 🔬 Calibration Process

### Automatic Calibration Phases

1. **Burn-in Phase** (5 minutes)
   - Allows gas sensor to stabilize
   - No readings taken

2. **Baseline Sampling** (5 minutes)
   - Collects gas resistance readings in **clean air**
   - Calculates average as baseline
   - **Critical**: Ensure sensor is in clean environment!

3. **Normal Operation**
   - Compares current readings to baseline
   - Calculates air quality score

### Recalibration

- **Automatic**: Every 4 hours (configurable)
- **Manual**: Delete `gas_baseline.json` and restart

### Calibration Best Practices

✅ **DO**:
- Calibrate outdoors or in well-ventilated area
- Open windows during calibration
- Wait for stable weather conditions
- Calibrate away from traffic/pollution sources

❌ **DON'T**:
- Calibrate near cooking areas
- Calibrate during cleaning (chemicals)
- Calibrate in closed rooms
- Rush the calibration process

## 📁 File Structure

```
BME680/
├── sensor.py              # Main monitoring script
├── sensor_control.sh      # Service management script
├── requirements.txt       # Python dependencies
├── README.md              # This file
├── .gitignore            # Git ignore rules
├── measures.csv          # Data output (auto-generated)
├── gas_baseline.json     # Calibration data (auto-generated)
└── logs/                 # Log files (auto-generated)
    ├── sensor.log        # Main application log
    ├── sensor_control.log # Control script log
    ├── sensor_history.log # Start/stop history
    └── sensor.pid        # Process ID file
```

## ⚙️ Configuration

### Sensor Configuration

Edit `sensor.py` to change settings:

```python
# Air Quality Configuration (lines 45-51)
BURN_IN_DURATION_S = 300              # Burn-in time (5 min)
BASELINE_SAMPLING_DURATION_S = 300     # Baseline sampling (5 min)
GOOD_AIR_THRESHOLD_RATIO = 1.35        # Good air threshold
POOR_AIR_THRESHOLD_RATIO = 0.70        # Poor air threshold
RECALIBRATION_INTERVAL_S = 4 * 3600    # Recalibrate every 4 hours

# Sensor I2C Address (line 18)
sensor = bme680.BME680(0x77)  # Change to 0x76 if needed
```

### Control Script Configuration

Edit `sensor_control.sh` (lines 7-15):

```bash
VENV_DIR="venv"                # Virtual environment directory
PYTHON_SCRIPT="sensor.py"      # Main script name
LOG_DIR="logs"                 # Log directory
MAX_LOG_SIZE_MB=50            # Max log size before rotation
```

## 🔍 Troubleshooting

### Sensor Not Detected

```bash
# Check I2C is enabled
sudo raspi-config

# Check devices on bus
sudo i2cdetect -y 1

# Check sensor permissions
sudo chmod 666 /dev/i2c-1

# If sensor is at 0x76 instead of 0x77, edit sensor.py line 18
```

### OLED Not Working

```bash
# Verify OLED address (should be 0x3C)
sudo i2cdetect -y 1

# Check display connection
# Script will continue without OLED if it fails
```

### Low Baseline Warning

If you see: `⚠️ WARNING: Baseline is LOW`

**Cause**: Calibration was done in contaminated air

**Solution**:
1. Move sensor to clean, outdoor environment
2. Delete `gas_baseline.json`
3. Restart: `./sensor_control.sh restart`
4. Wait for recalibration (10 minutes)

### Process Won't Start

```bash
# Check logs
./sensor_control.sh logs

# Or manually:
cat logs/sensor.log

# Verify virtual environment
source venv/bin/activate
python3 -c "import bme680, luma.oled"
```

## 📈 Data Visualization Ideas

### Grafana Dashboard
- Import CSV into InfluxDB or Prometheus
- Create time-series graphs
- Set up alerts for poor air quality

### Python Analysis
```python
import pandas as pd
import matplotlib.pyplot as plt

df = pd.read_csv('measures.csv')
df['timestamp'] = pd.to_datetime(df['timestamp'])
df.set_index('timestamp', inplace=True)

# Plot temperature over time
df['temperature_c'].plot(title='Temperature Over Time')
plt.show()
```

### Jupyter Notebook
- Load `measures.csv`
- Analyze correlations between temperature, humidity, and AQI
- Identify pollution patterns

## 🛠️ Advanced Setup

### Run as Systemd Service

Create `/etc/systemd/system/bme680-sensor.service`:

```ini
[Unit]
Description=BME680 Air Quality Monitor
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/BME680
ExecStart=/home/pi/BME680/venv/bin/python3 /home/pi/BME680/sensor.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl daemon-reload
sudo systemctl enable bme680-sensor
sudo systemctl start bme680-sensor
sudo systemctl status bme680-sensor
```

## 🤝 Contributing

Contributions welcome! Please:
1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Open a Pull Request

## 📄 License

MIT License - feel free to use in your projects!

## 🙏 Acknowledgments

- [Pimoroni BME680 Library](https://github.com/pimoroni/bme680-python)
- [Luma.OLED](https://github.com/rm-hull/luma.oled)
- BME680 community for calibration insights

## 📧 Support

Issues? Open a GitHub issue or check the troubleshooting section.

---

**Made with ❤️ for clean air monitoring**
