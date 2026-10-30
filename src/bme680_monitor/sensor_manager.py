"""BME680 sensor management and data acquisition."""

import logging
import bme680
from typing import Optional, Dict, Any


logger = logging.getLogger(__name__)


class SensorData:
    """Container for sensor reading data."""

    def __init__(
        self,
        temperature: float,
        humidity: float,
        pressure: float,
        gas_resistance: Optional[float],
        heat_stable: bool
    ):
        """
        Initialize sensor data.

        Args:
            temperature: Temperature in Celsius
            humidity: Relative humidity in %
            pressure: Atmospheric pressure in hPa
            gas_resistance: Gas resistance in Ohms (None if not stable)
            heat_stable: Whether gas sensor heater is stable
        """
        self.temperature = temperature
        self.humidity = humidity
        self.pressure = pressure
        self.gas_resistance = gas_resistance
        self.heat_stable = heat_stable

    def to_dict(self) -> Dict[str, Any]:
        """Convert sensor data to dictionary."""
        return {
            'temperature': self.temperature,
            'humidity': self.humidity,
            'pressure': self.pressure,
            'gas_resistance': self.gas_resistance,
            'heat_stable': self.heat_stable
        }

    def __repr__(self) -> str:
        """String representation of sensor data."""
        gas_str = f"{self.gas_resistance:.0f}Ω" if self.gas_resistance else "N/A"
        return (
            f"SensorData(T={self.temperature:.1f}°C, "
            f"H={self.humidity:.1f}%, "
            f"P={self.pressure:.1f}hPa, "
            f"Gas={gas_str})"
        )


class SensorManager:
    """Manages BME680 sensor initialization and data reading."""

    def __init__(
        self,
        i2c_address: int = 0x77,
        gas_heater_temperature: int = 320,
        gas_heater_duration: int = 150,
        allow_deferred_init: bool = False
    ):
        """
        Initialize sensor manager.

        Args:
            i2c_address: I2C address of BME680 sensor (0x77 or 0x76)
            gas_heater_temperature: Gas heater temperature in Celsius
            gas_heater_duration: Gas heater duration in milliseconds
            allow_deferred_init: If True, keep running with sensor=None when
                initial I2C detection fails and retry automatically in read()

        Raises:
            RuntimeError, OSError: If sensor initialization fails and allow_deferred_init is False
        """
        self.i2c_address = i2c_address
        self.gas_heater_temperature = gas_heater_temperature
        self.gas_heater_duration = gas_heater_duration

        self.sensor: Optional[bme680.BME680] = None
        self._consecutive_read_errors: int = 0
        self._reinit_interval: int = 30
        self._log_throttle_interval: int = 300
        try:
            self._initialize_sensor()
        except (RuntimeError, OSError):
            if not allow_deferred_init:
                raise
            logger.warning(
                f"Deferred initialization enabled: BME680 at 0x{self.i2c_address:02X} "
                f"not reachable yet; will retry every {self._reinit_interval} reads."
            )

    def _initialize_sensor(self, quiet: bool = False) -> None:
        """Initialize BME680 sensor and configure settings."""
        try:
            self.sensor = bme680.BME680(self.i2c_address)
            logger.info(f"BME680 sensor detected at address 0x{self.i2c_address:02X}")

        except (RuntimeError, OSError) as e:
            # OSError (e.g. "Remote I/O error") is what a missing/disabled I2C
            # bus actually raises on this hardware; RuntimeError alone missed it.
            if not quiet:
                logger.error(f"Error initializing sensor: {e}")
                logger.error("Ensure SDA and SCL connections are correct")
                logger.error("and that I2C is enabled (sudo raspi-config -> Interface Options -> I2C)")
            raise

        # Configure gas heater
        self.sensor.set_gas_heater_temperature(self.gas_heater_temperature)
        self.sensor.set_gas_heater_duration(self.gas_heater_duration)
        self.sensor.select_gas_heater_profile(0)

        logger.info(
            f"Gas heater configured: {self.gas_heater_temperature}°C, "
            f"{self.gas_heater_duration}ms"
        )

        # Optional: Configure oversampling (commented out - using defaults)
        # self.sensor.set_temperature_oversample(bme680.OS_2X)
        # self.sensor.set_humidity_oversample(bme680.OS_2X)
        # self.sensor.set_pressure_oversample(bme680.OS_2X)
        # self.sensor.set_filter(bme680.FILTER_SIZE_2)

    def read(self) -> Optional[SensorData]:
        """
        Read sensor data. Automatically attempts I2C re-initialization after
        repeated read errors and throttles repetitive error logs to protect SD storage.

        Returns:
            SensorData object if successful, None otherwise
        """
        if not self.sensor:
            self._consecutive_read_errors += 1
            if (
                self._consecutive_read_errors == 1
                or self._consecutive_read_errors % self._log_throttle_interval == 0
            ):
                logger.error(
                    f"Sensor not initialized (consecutive={self._consecutive_read_errors})"
                )
            if self._consecutive_read_errors % self._reinit_interval == 0:
                try:
                    self._initialize_sensor(quiet=True)
                except Exception:
                    pass
            if not self.sensor:
                return None

        try:
            if self.sensor.get_sensor_data():
                if self._consecutive_read_errors > 0:
                    logger.info(
                        f"BME680 I2C communication recovered after {self._consecutive_read_errors} failed attempt(s)"
                    )
                    self._consecutive_read_errors = 0

                temperature = self.sensor.data.temperature
                humidity = self.sensor.data.humidity
                pressure = self.sensor.data.pressure
                heat_stable = self.sensor.data.heat_stable

                # Only read gas resistance if heater is stable
                gas_resistance = None
                if heat_stable:
                    gas_resistance = self.sensor.data.gas_resistance

                return SensorData(
                    temperature=temperature,
                    humidity=humidity,
                    pressure=pressure,
                    gas_resistance=gas_resistance,
                    heat_stable=heat_stable
                )

        except Exception as e:
            self._consecutive_read_errors += 1
            if (
                self._consecutive_read_errors == 1
                or self._consecutive_read_errors % self._log_throttle_interval == 0
            ):
                logger.error(
                    f"Error reading sensor data (consecutive={self._consecutive_read_errors}): {e}"
                )
            if self._consecutive_read_errors % self._reinit_interval == 0:
                try:
                    self._initialize_sensor(quiet=True)
                except Exception:
                    pass

        return None

    def is_available(self) -> bool:
        """
        Check if sensor is available and working.

        Returns:
            True if sensor is available, False otherwise
        """
        return self.sensor is not None

    def get_sensor_info(self) -> Dict[str, Any]:
        """
        Get sensor configuration information.

        Returns:
            Dictionary with sensor configuration
        """
        return {
            'i2c_address': f"0x{self.i2c_address:02X}",
            'gas_heater_temperature': self.gas_heater_temperature,
            'gas_heater_duration': self.gas_heater_duration,
            'available': self.is_available()
        }

    def __repr__(self) -> str:
        """String representation of sensor manager."""
        return (
            f"SensorManager(address=0x{self.i2c_address:02X}, "
            f"heater={self.gas_heater_temperature}°C)"
        )
