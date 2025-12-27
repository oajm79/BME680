"""Tests for configuration module."""

import pytest
import tempfile
import yaml
from pathlib import Path
import sys

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from bme680_monitor.config import Config


class TestConfig:
    """Test suite for Config."""

    @pytest.fixture
    def temp_config_file(self):
        """Create a temporary config file."""
        config_data = {
            'sensor': {
                'i2c_address': 0x77,
                'gas_heater_temperature': 320,
                'sampling_interval': 1
            },
            'calibration': {
                'burn_in_duration': 300,
                'recalibration_interval': 14400
            },
            'air_quality': {
                'good_threshold': 1.35,
                'poor_threshold': 0.70
            },
            'oled': {
                'enabled': True,
                'i2c_address': 0x3C
            },
            'logging': {
                'level': 'INFO'
            }
        }

        fd, path = tempfile.mkstemp(suffix='.yaml')
        with open(path, 'w') as f:
            yaml.dump(config_data, f)

        yield path

        # Cleanup
        import os
        os.close(fd)
        os.remove(path)

    def test_load_config(self, temp_config_file):
        """Test loading configuration from file."""
        config = Config(temp_config_file)

        assert config.sensor_i2c_address == 0x77
        assert config.gas_heater_temperature == 320
        assert config.sampling_interval == 1

    def test_get_with_dot_notation(self, temp_config_file):
        """Test getting values with dot notation."""
        config = Config(temp_config_file)

        assert config.get('sensor.i2c_address') == 0x77
        assert config.get('calibration.burn_in_duration') == 300
        assert config.get('air_quality.good_threshold') == 1.35

    def test_get_with_default(self, temp_config_file):
        """Test getting non-existent value returns default."""
        config = Config(temp_config_file)

        assert config.get('nonexistent.key', 'default') == 'default'

    def test_properties(self, temp_config_file):
        """Test configuration properties."""
        config = Config(temp_config_file)

        # Sensor properties
        assert config.sensor_i2c_address == 0x77
        assert config.gas_heater_temperature == 320

        # Calibration properties
        assert config.burn_in_duration == 300
        assert config.recalibration_interval == 14400

        # Air quality properties
        assert config.good_air_threshold == 1.35
        assert config.poor_air_threshold == 0.70

        # OLED properties
        assert config.oled_enabled is True
        assert config.oled_i2c_address == 0x3C

        # Logging properties
        assert config.log_level == 'INFO'

    def test_missing_config_file(self):
        """Test error when config file doesn't exist."""
        with pytest.raises(FileNotFoundError):
            Config('nonexistent.yaml')
