"""
BME680 Environmental Sensor Monitor Package

A professional air quality monitoring system with:
- Automatic calibration and baseline management
- OLED display support
- CSV data logging
- Configurable thresholds
"""

__version__ = "2.0.0"
__author__ = "BME680 Monitor Project"

from .config import Config
from .sensor_manager import SensorManager
from .air_quality import AirQualityCalculator
from .display import OLEDDisplay
from .data_logger import DataLogger

__all__ = [
    "Config",
    "SensorManager",
    "AirQualityCalculator",
    "OLEDDisplay",
    "DataLogger",
]
