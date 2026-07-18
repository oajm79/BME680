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

        monkeypatch.setattr(ws, "get_json", fake_get_json)

        service.get_current_conditions()
        first_call_count = call_count
        assert first_call_count == 2  # weather + air quality both attempted once

        service.get_current_conditions()

        assert call_count == first_call_count, (
            "get_current_conditions() re-attempted the API call immediately "
            "after a failure instead of using a short negative cache"
        )
