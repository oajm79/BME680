"""Tests for air quality calculation module."""

import pytest
import os
import json
import tempfile
from pathlib import Path
import sys

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from bme680_monitor.air_quality import AirQualityCalculator, AirQualityLevel


class TestAirQualityCalculator:
    """Test suite for AirQualityCalculator."""

    @pytest.fixture
    def temp_baseline_file(self):
        """Create a temporary baseline file."""
        fd, path = tempfile.mkstemp(suffix='.json')
        os.close(fd)
        yield path
        # Cleanup
        if os.path.exists(path):
            os.remove(path)

    @pytest.fixture
    def calculator(self, temp_baseline_file):
        """Create a test air quality calculator."""
        return AirQualityCalculator(
            baseline_file=temp_baseline_file,
            burn_in_duration=10,  # Short for testing
            baseline_sampling_duration=10,
            recalibration_interval=0,  # Disabled
            good_threshold=1.35,
            poor_threshold=0.70,
            clean_air_min=50000,
            clean_air_max=200000,
            baseline_max_age_hours=24
        )

    def test_initialization(self, calculator):
        """Test calculator initialization."""
        assert calculator.gas_baseline is None
        assert calculator.baseline_gas_readings == []

    def test_baseline_save_and_load(self, calculator, temp_baseline_file):
        """Test baseline persistence."""
        # Set a baseline manually
        calculator.gas_baseline = 100000.0
        calculator.time_baseline_established = 1234567890.0

        # Save it
        calculator.save_baseline()

        # Create new calculator and load
        new_calc = AirQualityCalculator(
            baseline_file=temp_baseline_file,
            burn_in_duration=10,
            baseline_sampling_duration=10,
            recalibration_interval=0,
            good_threshold=1.35,
            poor_threshold=0.70,
            clean_air_min=50000,
            clean_air_max=200000,
            baseline_max_age_hours=999999  # Very long age for test
        )

        # Baseline should be loaded
        assert new_calc.gas_baseline == 100000.0

    def test_air_quality_good(self, calculator):
        """Test good air quality detection."""
        # Set baseline
        calculator.gas_baseline = 100000.0

        # Test good air (above threshold)
        index, label = calculator.update(gas_resistance=140000, heat_stable=True)

        # Should be good (140k / 100k = 1.4 > 1.35)
        assert index == AirQualityLevel.GOOD
        assert label == "Good"

    def test_air_quality_poor(self, calculator):
        """Test poor air quality detection."""
        # Set baseline
        calculator.gas_baseline = 100000.0

        # Test poor air (below threshold)
        index, label = calculator.update(gas_resistance=60000, heat_stable=True)

        # Should be poor (60k / 100k = 0.6 < 0.70)
        assert index == AirQualityLevel.POOR
        assert label == "Poor"

    def test_air_quality_moderate(self, calculator):
        """Test moderate air quality detection."""
        # Set baseline
        calculator.gas_baseline = 100000.0

        # Test moderate air (between thresholds)
        index, label = calculator.update(gas_resistance=100000, heat_stable=True)

        # Should be moderate (100k / 100k = 1.0, between 0.70 and 1.35)
        assert index == AirQualityLevel.MODERATE
        assert label == "Moderate"

    def test_calibrating_state(self, calculator):
        """Test calibrating state during burn-in."""
        # During burn-in, should return calibrating
        index, label = calculator.update(gas_resistance=100000, heat_stable=True)

        assert index == AirQualityLevel.CALIBRATING
        assert "Burn-in" in label or "Baseline" in label

    def test_get_baseline_info(self, calculator):
        """Test baseline info retrieval."""
        # No baseline yet
        assert calculator.get_baseline_info() is None

        # Set baseline
        calculator.gas_baseline = 100000.0
        calculator.time_baseline_established = 1234567890.0

        info = calculator.get_baseline_info()
        assert info is not None
        assert info['baseline_ohms'] == 100000.0
        assert info['baseline_kohms'] == 100.0
