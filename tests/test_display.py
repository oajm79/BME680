"""Tests for OLED display module and compatibility shims."""

import sys
import warnings
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from PIL import Image

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from bme680_monitor import display as disp


class TestPillowCompatibilityShim:
    """Test suite for Pillow deprecation shim and display initialization."""

    def test_shim_applies_and_avoids_deprecation_warning(self):
        """Image.Image.getdata should delegate to get_flattened_data without warning."""
        disp._apply_pillow_compatibility_shim()

        img = Image.new("1", (4, 4), 1)
        with warnings.catch_warnings(record=True) as recorded:
            warnings.simplefilter("always")
            data = list(img.getdata())

        assert len(data) == 16
        # Assert no DeprecationWarning was emitted for getdata
        getdata_warnings = [
            w for w in recorded
            if issubclass(w.category, DeprecationWarning) and "getdata" in str(w.message)
        ]
        assert not getdata_warnings

    def test_display_disabled_initialization(self):
        """OLEDDisplay initialized with enabled=False should not touch I2C."""
        display = disp.OLEDDisplay(enabled=False)
        assert not display.is_available()
        # Updating or clearing should be a no-op and not raise
        display.update(
            temperature=20.0,
            humidity=50.0,
            pressure=1013.0,
            air_quality_label="Good",
        )
        display.clear()

    def test_temp_short_label(self):
        """Verify temperature ranges are labeled correctly."""
        display = disp.OLEDDisplay(enabled=False)
        report = {}
        assert "Very Cold" in display._get_temp_short_label(5.0, report)
        assert "Cold" in display._get_temp_short_label(15.0, report)
        assert "Perfect" in display._get_temp_short_label(22.0, report)
        assert "Warm" in display._get_temp_short_label(26.0, report)
        assert "Very Hot" in display._get_temp_short_label(32.0, report)

    def test_humid_short_label(self):
        """Verify humidity ranges are labeled correctly."""
        display = disp.OLEDDisplay(enabled=False)
        report = {}
        assert "Very Dry" in display._get_humid_short_label(20.0, report)
        assert "Dry" in display._get_humid_short_label(35.0, report)
        assert "Ideal" in display._get_humid_short_label(50.0, report)
        assert "Humid" in display._get_humid_short_label(65.0, report)
        assert "Very Humid" in display._get_humid_short_label(80.0, report)

    def test_pressure_short_label(self):
        """Verify atmospheric pressure ranges are labeled correctly."""
        display = disp.OLEDDisplay(enabled=False)
        report = {}
        assert "Storm" in display._get_pressure_short_label(970.0, report)
        assert "Rainy" in display._get_pressure_short_label(995.0, report)
        assert "Normal" in display._get_pressure_short_label(1013.0, report)
        assert "Clear" in display._get_pressure_short_label(1030.0, report)
        assert "Very Dry" in display._get_pressure_short_label(1045.0, report)

    def test_comfort_display_mapping(self):
        """Verify comfort level emoji and text mappings."""
        display = disp.OLEDDisplay(enabled=False)
        c4 = display._get_comfort_display(4, "Very Comfortable")
        assert c4["text"] == "Excellent"
        assert c4["emoji"] == "😊"

        c0 = display._get_comfort_display(0, "Poor")
        assert c0["text"] == "Poor"
        assert c0["emoji"] == "😫"
