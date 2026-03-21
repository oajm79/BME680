"""
BME680 Environmental Sensor Monitor Package

A professional air quality monitoring system with:
- Automatic calibration and baseline management
- OLED display support
- SQLite data logging
- Telegram notifications
- Configurable thresholds
- Environmental comfort assessment
"""

__version__ = "2.2.0"
__author__ = "BME680 Monitor Project"

from .config import Config
from .sensor_manager import SensorManager
from .air_quality import AirQualityCalculator
from .display import OLEDDisplay
from .data_logger import DataLogger
from .database import DatabaseManager
from .telegram_notifier import TelegramNotifier, AlertType
from .comfort_index import ComfortIndexCalculator
from .weather_service import WeatherService

__all__ = [
    "Config",
    "SensorManager",
    "AirQualityCalculator",
    "OLEDDisplay",
    "DataLogger",
    "DatabaseManager",
    "TelegramNotifier",
    "AlertType",
    "ComfortIndexCalculator",
    "WeatherService",
]
