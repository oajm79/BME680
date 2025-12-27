"""Configuration management for BME680 sensor monitor."""

import os
import yaml
from typing import Any, Dict
from pathlib import Path


class Config:
    """Configuration manager that loads settings from YAML file."""

    DEFAULT_CONFIG_FILE = "config.yaml"

    def __init__(self, config_file: str = None):
        """
        Initialize configuration.

        Args:
            config_file: Path to YAML configuration file. If None, uses default.
        """
        self.config_file = config_file or self.DEFAULT_CONFIG_FILE
        self._config: Dict[str, Any] = {}
        self.load()

    def load(self) -> None:
        """Load configuration from YAML file."""
        if not os.path.exists(self.config_file):
            raise FileNotFoundError(
                f"Configuration file not found: {self.config_file}\n"
                f"Please create it or use the default config.yaml"
            )

        with open(self.config_file, 'r') as f:
            self._config = yaml.safe_load(f)

    def get(self, key_path: str, default: Any = None) -> Any:
        """
        Get configuration value using dot notation.

        Args:
            key_path: Dot-separated path to config value (e.g., 'sensor.i2c_address')
            default: Default value if key not found

        Returns:
            Configuration value or default

        Example:
            >>> config = Config()
            >>> config.get('sensor.i2c_address')
            0x77
        """
        keys = key_path.split('.')
        value = self._config

        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return default

        return value

    # Sensor configuration
    @property
    def sensor_i2c_address(self) -> int:
        """Get sensor I2C address."""
        return self.get('sensor.i2c_address', 0x77)

    @property
    def gas_heater_temperature(self) -> int:
        """Get gas heater temperature in Celsius."""
        return self.get('sensor.gas_heater_temperature', 320)

    @property
    def gas_heater_duration(self) -> int:
        """Get gas heater duration in milliseconds."""
        return self.get('sensor.gas_heater_duration', 150)

    @property
    def sampling_interval(self) -> int:
        """Get sampling interval in seconds."""
        return self.get('sensor.sampling_interval', 1)

    # Calibration configuration
    @property
    def burn_in_duration(self) -> int:
        """Get burn-in duration in seconds."""
        return self.get('calibration.burn_in_duration', 300)

    @property
    def baseline_sampling_duration(self) -> int:
        """Get baseline sampling duration in seconds."""
        return self.get('calibration.baseline_sampling_duration', 300)

    @property
    def recalibration_interval(self) -> int:
        """Get recalibration interval in seconds (0 = disabled)."""
        return self.get('calibration.recalibration_interval', 14400)

    @property
    def baseline_file(self) -> str:
        """Get baseline persistence file path."""
        return self.get('calibration.baseline_file', 'gas_baseline.json')

    @property
    def baseline_max_age(self) -> int:
        """Get baseline maximum age in hours."""
        return self.get('calibration.baseline_max_age', 24)

    # Air quality configuration
    @property
    def good_air_threshold(self) -> float:
        """Get good air quality threshold ratio (relative)."""
        return self.get('air_quality.good_threshold', 1.35)

    @property
    def poor_air_threshold(self) -> float:
        """Get poor air quality threshold ratio (relative)."""
        return self.get('air_quality.poor_threshold', 0.70)

    @property
    def excellent_threshold_abs(self) -> int:
        """Get excellent air quality threshold in Ohms (absolute)."""
        return self.get('air_quality.excellent_threshold', 150000)

    @property
    def good_threshold_abs(self) -> int:
        """Get good air quality threshold in Ohms (absolute)."""
        return self.get('air_quality.good_threshold_abs', 100000)

    @property
    def moderate_threshold_abs(self) -> int:
        """Get moderate air quality threshold in Ohms (absolute)."""
        return self.get('air_quality.moderate_threshold', 50000)

    @property
    def clean_air_min(self) -> int:
        """Get minimum clean air resistance in Ohms."""
        return self.get('air_quality.clean_air_min', 50000)

    @property
    def clean_air_max(self) -> int:
        """Get maximum clean air resistance in Ohms."""
        return self.get('air_quality.clean_air_max', 200000)

    # OLED configuration
    @property
    def oled_enabled(self) -> bool:
        """Check if OLED display is enabled."""
        return self.get('oled.enabled', True)

    @property
    def oled_i2c_address(self) -> int:
        """Get OLED I2C address."""
        return self.get('oled.i2c_address', 0x3C)

    @property
    def oled_width(self) -> int:
        """Get OLED display width."""
        return self.get('oled.width', 128)

    @property
    def oled_height(self) -> int:
        """Get OLED display height."""
        return self.get('oled.height', 64)

    @property
    def oled_yellow_section_height(self) -> int:
        """Get OLED yellow section height."""
        return self.get('oled.yellow_section_height', 16)

    @property
    def oled_font_name(self) -> str:
        """Get OLED font name."""
        return self.get('oled.font_name', 'DejaVuSans.ttf')

    @property
    def oled_font_size(self) -> int:
        """Get OLED font size."""
        return self.get('oled.font_size', 10)

    @property
    def oled_line_height(self) -> int:
        """Get OLED line height."""
        return self.get('oled.line_height', 12)

    @property
    def oled_title(self) -> str:
        """Get OLED display title."""
        return self.get('oled.title', 'BME680 Readings')

    # Data logging configuration
    @property
    def csv_filename(self) -> str:
        """Get CSV output filename."""
        return self.get('data_logging.csv_filename', 'measures.csv')

    @property
    def flush_immediately(self) -> bool:
        """Check if CSV should flush immediately after each write."""
        return self.get('data_logging.flush_immediately', True)

    # Logging configuration
    @property
    def log_level(self) -> str:
        """Get logging level."""
        return self.get('logging.level', 'INFO')

    @property
    def log_format(self) -> str:
        """Get logging format."""
        return self.get('logging.format', '%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    @property
    def log_date_format(self) -> str:
        """Get logging date format."""
        return self.get('logging.date_format', '%Y-%m-%d %H:%M:%S')

    @property
    def log_file_enabled(self) -> bool:
        """Check if file logging is enabled."""
        return self.get('logging.file.enabled', True)

    @property
    def log_filename(self) -> str:
        """Get log file path."""
        return self.get('logging.file.filename', 'logs/sensor.log')

    @property
    def log_max_bytes(self) -> int:
        """Get maximum log file size in bytes."""
        return self.get('logging.file.max_bytes', 10485760)

    @property
    def log_backup_count(self) -> int:
        """Get number of log file backups to keep."""
        return self.get('logging.file.backup_count', 5)

    @property
    def log_console_enabled(self) -> bool:
        """Check if console logging is enabled."""
        return self.get('logging.console.enabled', True)

    def __repr__(self) -> str:
        """String representation of config."""
        return f"Config(file='{self.config_file}')"
