"""Tests for data logger module."""

import pytest
import os
import csv
import tempfile
from pathlib import Path
import sys

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from bme680_monitor.data_logger import DataLogger


class TestDataLogger:
    """Test suite for DataLogger."""

    @pytest.fixture
    def temp_csv_file(self):
        """Create a temporary CSV file."""
        fd, path = tempfile.mkstemp(suffix='.csv')
        os.close(fd)
        os.remove(path)  # Remove so logger can create it
        yield path
        # Cleanup
        if os.path.exists(path):
            os.remove(path)

    @pytest.fixture
    def logger(self, temp_csv_file):
        """Create a test data logger."""
        return DataLogger(filename=temp_csv_file, flush_immediately=True)

    def test_initialization(self, logger, temp_csv_file):
        """Test logger initialization creates file with headers."""
        assert os.path.exists(temp_csv_file)

        # Check headers
        with open(temp_csv_file, 'r') as f:
            reader = csv.reader(f)
            headers = next(reader)
            assert 'timestamp' in headers
            assert 'temperature_c' in headers
            assert 'air_quality_index' in headers

    def test_log_reading(self, logger, temp_csv_file):
        """Test logging a single reading."""
        logger.log_reading(
            temperature=25.5,
            humidity=60.0,
            pressure=1013.25,
            gas_resistance=100000.0,
            air_quality_index=3,
            air_quality_label="Good"
        )

        # Read back and verify
        with open(temp_csv_file, 'r') as f:
            reader = csv.reader(f)
            next(reader)  # Skip header
            row = next(reader)

            assert float(row[1]) == 25.5  # temperature
            assert float(row[2]) == 60.0  # humidity
            assert float(row[3]) == 1013.25  # pressure
            assert float(row[4]) == 100000.0  # gas_resistance
            assert int(row[5]) == 3  # air_quality_index
            assert row[6] == "Good"  # air_quality_label

    def test_log_reading_with_none_values(self, logger, temp_csv_file):
        """Test logging with None gas resistance."""
        logger.log_reading(
            temperature=25.5,
            humidity=60.0,
            pressure=1013.25,
            gas_resistance=None,
            air_quality_index=None,
            air_quality_label="Calibrating"
        )

        # Should not crash
        assert os.path.exists(temp_csv_file)

    def test_get_file_size(self, logger, temp_csv_file):
        """Test file size retrieval."""
        size = logger.get_file_size()
        assert size > 0  # Should have at least header

        size_mb = logger.get_file_size_mb()
        assert size_mb >= 0.0

    def test_batch_mode(self, logger, temp_csv_file):
        """Test batch writing mode."""
        readings = [
            {
                'temperature': 25.0,
                'humidity': 60.0,
                'pressure': 1013.0,
                'gas_resistance': 100000.0,
                'air_quality_index': 3,
                'air_quality_label': 'Good'
            },
            {
                'temperature': 26.0,
                'humidity': 55.0,
                'pressure': 1012.0,
                'gas_resistance': 95000.0,
                'air_quality_index': 2,
                'air_quality_label': 'Moderate'
            }
        ]

        with logger.batch_mode() as batch:
            batch.extend(readings)

        # Verify both readings were written
        with open(temp_csv_file, 'r') as f:
            lines = f.readlines()
            assert len(lines) == 3  # Header + 2 readings
