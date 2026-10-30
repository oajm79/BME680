"""Tests for sensor manager module."""

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from bme680_monitor.sensor_manager import SensorData, SensorManager


class TestSensorDataRepr:
    """Test suite for SensorData.__repr__."""

    def test_repr_with_gas_resistance(self):
        data = SensorData(
            temperature=22.5, humidity=45.0, pressure=1013.0,
            gas_resistance=120000.0, heat_stable=True
        )
        assert repr(data) == "SensorData(T=22.5°C, H=45.0%, P=1013.0hPa, Gas=120000Ω)"

    def test_repr_without_gas_resistance(self):
        data = SensorData(
            temperature=22.5, humidity=45.0, pressure=1013.0,
            gas_resistance=None, heat_stable=False
        )
        assert repr(data) == "SensorData(T=22.5°C, H=45.0%, P=1013.0hPa, Gas=N/A)"


class TestSensorManagerInitErrors:
    """Test suite for SensorManager initialization error handling."""

    def test_i2c_oserror_is_logged_like_runtime_error(self, caplog):
        """A missing/disabled I2C bus raises OSError on real hardware, not RuntimeError.

        The init code must log the same SDA/SCL/I2C troubleshooting guidance for
        OSError as it does for RuntimeError, instead of letting it fall through
        unlogged to an unhandled traceback.
        """
        with patch("bme680_monitor.sensor_manager.bme680.BME680", side_effect=OSError("Remote I/O error")):
            with pytest.raises(OSError):
                with caplog.at_level("ERROR"):
                    SensorManager()

        assert any("Error initializing sensor" in record.message for record in caplog.records), (
            "OSError during sensor init was not logged - it fell through the "
            "RuntimeError-only except clause"
        )

    def test_read_throttles_errors_and_attempts_reinit(self, caplog):
        from unittest.mock import MagicMock

        mock_dev = MagicMock()
        mock_dev.get_sensor_data.side_effect = OSError("[Errno 121] Remote I/O error")
        with patch("bme680_monitor.sensor_manager.bme680.BME680", return_value=mock_dev) as mock_cls:
            mgr = SensorManager()
            assert mock_cls.call_count == 1
            caplog.clear()
            with caplog.at_level("ERROR"):
                for _ in range(30):
                    assert mgr.read() is None
            # Only the 1st error should be logged within 30 attempts (throttled to every 300)
            error_records = [r for r in caplog.records if "Error reading sensor data" in r.message]
            assert len(error_records) == 1
            # Re-init should have been attempted on the 30th consecutive error
            assert mock_cls.call_count == 2

