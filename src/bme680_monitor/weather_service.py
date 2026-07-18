"""Weather service integration with Open-Meteo API."""

import logging
import time
from typing import Optional, Dict, Any

from shared_services.http import get_json

logger = logging.getLogger(__name__)


# Weather codes from Open-Meteo (WMO Weather interpretation codes)
WEATHER_CODES = {
    0: "Clear sky",
    1: "Mainly clear",
    2: "Partly cloudy",
    3: "Overcast",
    45: "Foggy",
    48: "Depositing rime fog",
    51: "Light drizzle",
    53: "Moderate drizzle",
    55: "Dense drizzle",
    61: "Slight rain",
    63: "Moderate rain",
    65: "Heavy rain",
    71: "Slight snow",
    73: "Moderate snow",
    75: "Heavy snow",
    77: "Snow grains",
    80: "Slight rain showers",
    81: "Moderate rain showers",
    82: "Violent rain showers",
    85: "Slight snow showers",
    86: "Heavy snow showers",
    95: "Thunderstorm",
    96: "Thunderstorm with slight hail",
    99: "Thunderstorm with heavy hail",
}

# US EPA Air Quality Index labels
AQI_LABELS = {
    (0, 50): "Good",
    (51, 100): "Moderate",
    (101, 150): "Unhealthy for Sensitive Groups",
    (151, 200): "Unhealthy",
    (201, 300): "Very Unhealthy",
    (301, 500): "Hazardous",
}


class WeatherService:
    """
    Fetches weather and air quality data from Open-Meteo API.

    Features:
    - Current weather conditions (temperature, humidity, pressure)
    - Air quality data (AQI, PM2.5, PM10)
    - Built-in caching to avoid API spam
    - No API key required
    """

    API_BASE = "https://api.open-meteo.com/v1"
    AQI_API_BASE = "https://air-quality-api.open-meteo.com/v1"
    CACHE_DURATION = 600  # 10 minutes
    FAILURE_BACKOFF = 60  # seconds to wait before retrying after a failed fetch

    def __init__(
        self,
        latitude: Optional[float] = None,
        longitude: Optional[float] = None,
        location_name: str = "Unknown",
        enabled: bool = True,
    ):
        """
        Initialize weather service.

        Args:
            latitude: Location latitude
            longitude: Location longitude
            location_name: Human-readable location name for display
            enabled: Whether the service is enabled
        """
        self.latitude = latitude
        self.longitude = longitude
        self.location_name = location_name
        self.enabled = enabled and latitude is not None and longitude is not None

        # Cache for API responses
        self._cache: Optional[Dict[str, Any]] = None
        self._cache_time: float = 0
        self._last_failure_time: Optional[float] = None

        if self.enabled:
            logger.info(f"Weather service enabled for {location_name} ({latitude}, {longitude})")
        else:
            logger.info("Weather service disabled (no coordinates configured)")

    def _get_aqi_label(self, aqi: int) -> str:
        """Get human-readable AQI label."""
        for (low, high), label in AQI_LABELS.items():
            if low <= aqi <= high:
                return label
        return "Unknown"

    def _get_weather_description(self, code: int) -> str:
        """Get weather description from WMO code."""
        return WEATHER_CODES.get(code, "Unknown")

    def _fetch_weather(self) -> Optional[Dict[str, Any]]:
        """Fetch current weather from Open-Meteo."""
        url = (
            f"{self.API_BASE}/forecast?"
            f"latitude={self.latitude}&longitude={self.longitude}"
            f"&current=temperature_2m,relative_humidity_2m,surface_pressure,weather_code"
            f"&timezone=auto"
        )
        try:
            return get_json(url, timeout=10)
        except Exception as e:
            logger.error(f"Weather API error: {e}")
            return None

    def _fetch_air_quality(self) -> Optional[Dict[str, Any]]:
        """Fetch air quality data from Open-Meteo."""
        url = (
            f"{self.AQI_API_BASE}/air-quality?"
            f"latitude={self.latitude}&longitude={self.longitude}"
            f"&current=us_aqi,pm2_5,pm10"
            f"&timezone=auto"
        )
        try:
            return get_json(url, timeout=10)
        except Exception as e:
            logger.error(f"Air quality API error: {e}")
            return None

    def get_current_conditions(self) -> Optional[Dict[str, Any]]:
        """
        Get current weather and air quality conditions.

        Uses caching to avoid excessive API calls.

        Returns:
            Dictionary with weather and air quality data, or None on error.
            {
                'temperature': float,      # Celsius
                'humidity': int,           # Percentage
                'pressure': float,         # hPa
                'weather_code': int,       # WMO code
                'weather_description': str,
                'aqi': int,                # US EPA AQI
                'aqi_label': str,          # Human readable
                'pm2_5': float,            # µg/m³
                'pm10': float,             # µg/m³
                'location_name': str,
            }
        """
        if not self.enabled:
            return None

        # Check cache
        current_time = time.time()
        if self._cache and (current_time - self._cache_time) < self.CACHE_DURATION:
            logger.debug("Using cached weather data")
            return self._cache

        # Back off after a recent failure instead of retrying every call
        if (
            self._last_failure_time is not None
            and (current_time - self._last_failure_time) < self.FAILURE_BACKOFF
        ):
            logger.debug("Skipping weather fetch, recent failure still in backoff window")
            return self._cache

        # Fetch fresh data
        weather_data = self._fetch_weather()
        air_quality_data = self._fetch_air_quality()

        if not weather_data:
            logger.warning("Failed to fetch weather data")
            self._last_failure_time = current_time
            return self._cache  # Return stale cache if available

        self._last_failure_time = None

        result = {
            "location_name": self.location_name,
            "temperature": None,
            "humidity": None,
            "pressure": None,
            "weather_code": None,
            "weather_description": None,
            "aqi": None,
            "aqi_label": None,
            "pm2_5": None,
            "pm10": None,
        }

        # Parse weather data
        if "current" in weather_data:
            current = weather_data["current"]
            result["temperature"] = current.get("temperature_2m")
            result["humidity"] = current.get("relative_humidity_2m")
            result["pressure"] = current.get("surface_pressure")
            weather_code = current.get("weather_code")
            if weather_code is not None:
                result["weather_code"] = weather_code
                result["weather_description"] = self._get_weather_description(weather_code)

        # Parse air quality data
        if air_quality_data and "current" in air_quality_data:
            current_aq = air_quality_data["current"]
            aqi = current_aq.get("us_aqi")
            if aqi is not None:
                result["aqi"] = int(aqi)
                result["aqi_label"] = self._get_aqi_label(int(aqi))
            result["pm2_5"] = current_aq.get("pm2_5")
            result["pm10"] = current_aq.get("pm10")

        # Update cache
        self._cache = result
        self._cache_time = current_time
        logger.debug(f"Weather data updated: {result['temperature']}°C, AQI: {result['aqi']}")

        return result

    def is_enabled(self) -> bool:
        """Check if weather service is enabled."""
        return self.enabled

    def is_configured(self) -> bool:
        """Check if weather service has valid coordinates."""
        return self.latitude is not None and self.longitude is not None
