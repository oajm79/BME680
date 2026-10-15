"""Tests for weather service module."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from bme680_monitor import weather_service as ws


class TestWeatherServiceFailureCaching:
    """Test suite for negative caching after failed API fetches."""

    @pytest.fixture
    def service(self):
        return ws.WeatherService(latitude=45.0, longitude=-75.0, location_name="Test", enabled=True)

    def test_does_not_retry_immediately_after_failed_fetch(self, service, monkeypatch):
        """A failed fetch must not be retried on every call within the backoff window."""
        call_count = 0

        def fake_get_json(url, timeout=10):
            nonlocal call_count
            call_count += 1
            raise OSError("Temporary failure in name resolution")

        monkeypatch.setattr(ws.time, "sleep", lambda x: None)
        monkeypatch.setattr(ws, "get_json", fake_get_json)

        service.get_current_conditions()
        first_call_count = call_count
        assert first_call_count == service.MAX_RETRIES * 2  # weather + air quality both retried MAX_RETRIES times

        service.get_current_conditions()

        assert call_count == first_call_count, (
            "get_current_conditions() re-attempted the API call immediately "
            "after a failure instead of using a short negative cache"
        )

    def test_retry_succeeds_on_second_attempt(self, service, monkeypatch):
        """A transient failure on attempt 1 should succeed on attempt 2 without failing overall."""
        attempts = {}

        def fake_get_json(url, timeout=15):
            attempts[url] = attempts.get(url, 0) + 1
            if "forecast" in url:
                if attempts[url] == 1:
                    raise OSError("HTTP Error 503: Service Unavailable")
                return {
                    "current": {
                        "temperature_2m": 22.0,
                        "relative_humidity_2m": 48,
                        "surface_pressure": 1012.0,
                        "weather_code": 0,
                    }
                }
            if "air-quality" in url:
                return {
                    "current": {
                        "us_aqi": 35,
                        "pm2_5": 7.5,
                        "pm10": 12.0,
                    }
                }
            return {}

        monkeypatch.setattr(ws.time, "sleep", lambda x: None)
        monkeypatch.setattr(ws, "get_json", fake_get_json)

        res = service.get_current_conditions()
        assert res is not None
        assert res["temperature"] == 22.0
        assert res["humidity"] == 48
        assert res["aqi"] == 35
        assert res["aqi_label"] == "Good"
        assert res["weather_description"] == "Clear sky"

    def test_non_dict_response_handled_gracefully(self, service, monkeypatch):
        """If an API returns HTML string or non-dict, it should retry and log warning."""
        attempts = 0

        def fake_get_json(url, timeout=15):
            nonlocal attempts
            attempts += 1
            return "<html>Error 503</html>"  # non-dict response

        monkeypatch.setattr(ws.time, "sleep", lambda x: None)
        monkeypatch.setattr(ws, "get_json", fake_get_json)

        res = service.get_current_conditions()
        assert res is None
        assert attempts == service.MAX_RETRIES * 2
