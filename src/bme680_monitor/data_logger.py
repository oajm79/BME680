"""CSV data logging for BME680 sensor readings."""

import csv
import os
import logging
from datetime import datetime
from typing import Optional, List, Any
from contextlib import contextmanager


logger = logging.getLogger(__name__)


class DataLogger:
    """Manages CSV data logging for sensor readings."""

    DEFAULT_COLUMNS = [
        'timestamp',
        'temperature_c',
        'humidity_rh',
        'pressure_hpa',
        'gas_resistance_ohms',
        'air_quality_index',
        'air_quality_label'
    ]

    def __init__(
        self,
        filename: str = "measures.csv",
        flush_immediately: bool = True,
        columns: Optional[List[str]] = None
    ):
        """
        Initialize data logger.

        Args:
            filename: CSV output filename
            flush_immediately: Whether to flush after each write
            columns: List of column names (uses default if None)
        """
        self.filename = filename
        self.flush_immediately = flush_immediately
        self.columns = columns or self.DEFAULT_COLUMNS

        # Initialize CSV file with header if needed
        self._initialize_file()

    def _initialize_file(self) -> None:
        """Initialize CSV file with header if it doesn't exist or is empty."""
        write_header = not os.path.exists(self.filename) or os.path.getsize(self.filename) == 0

        if write_header:
            try:
                with open(self.filename, 'w', newline='') as f:
                    writer = csv.writer(f)
                    writer.writerow(self.columns)
                logger.info(f"Created new CSV file: {self.filename} with headers")
            except IOError as e:
                logger.error(f"Error creating CSV file: {e}")
                raise

    def log_reading(
        self,
        temperature: float,
        humidity: float,
        pressure: float,
        gas_resistance: Optional[float],
        air_quality_index: Optional[int],
        air_quality_label: str
    ) -> None:
        """
        Log a sensor reading to CSV file.

        Args:
            temperature: Temperature in Celsius
            humidity: Relative humidity in %
            pressure: Atmospheric pressure in hPa
            gas_resistance: Gas resistance in Ohms (can be None)
            air_quality_index: Air quality index 0-3 (can be None)
            air_quality_label: Air quality label (e.g., "Good", "Poor")
        """
        timestamp_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        row = [
            timestamp_str,
            round(temperature, 2),
            round(humidity, 2),
            round(pressure, 2),
            round(gas_resistance, 2) if gas_resistance is not None else None,
            air_quality_index,
            air_quality_label
        ]

        try:
            with open(self.filename, 'a', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(row)

                if self.flush_immediately:
                    f.flush()

        except IOError as e:
            logger.error(f"Error writing to CSV file: {e}")

    def log_batch(self, readings: List[dict]) -> None:
        """
        Log multiple readings at once.

        Args:
            readings: List of dictionaries containing sensor readings
        """
        try:
            with open(self.filename, 'a', newline='') as f:
                writer = csv.writer(f)

                for reading in readings:
                    timestamp_str = reading.get(
                        'timestamp',
                        datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    )

                    row = [
                        timestamp_str,
                        round(reading['temperature'], 2),
                        round(reading['humidity'], 2),
                        round(reading['pressure'], 2),
                        round(reading['gas_resistance'], 2) if reading.get('gas_resistance') else None,
                        reading.get('air_quality_index'),
                        reading.get('air_quality_label', 'Unknown')
                    ]
                    writer.writerow(row)

                if self.flush_immediately:
                    f.flush()

            logger.info(f"Logged {len(readings)} readings to {self.filename}")

        except (IOError, KeyError) as e:
            logger.error(f"Error writing batch to CSV file: {e}")

    def get_file_size(self) -> int:
        """
        Get current CSV file size in bytes.

        Returns:
            File size in bytes, or 0 if file doesn't exist
        """
        if os.path.exists(self.filename):
            return os.path.getsize(self.filename)
        return 0

    def get_file_size_mb(self) -> float:
        """
        Get current CSV file size in megabytes.

        Returns:
            File size in MB, or 0.0 if file doesn't exist
        """
        return self.get_file_size() / (1024 * 1024)

    def rotate_if_needed(self, max_size_mb: float = 100.0) -> bool:
        """
        Rotate log file if it exceeds maximum size.

        Args:
            max_size_mb: Maximum file size in MB before rotation

        Returns:
            True if file was rotated, False otherwise
        """
        if self.get_file_size_mb() > max_size_mb:
            try:
                # Create backup filename with timestamp
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                backup_filename = f"{self.filename}.{timestamp}.backup"

                os.rename(self.filename, backup_filename)
                logger.info(f"Rotated log file to {backup_filename}")

                # Reinitialize with new file
                self._initialize_file()
                return True

            except OSError as e:
                logger.error(f"Error rotating log file: {e}")
                return False

        return False

    @contextmanager
    def batch_mode(self):
        """
        Context manager for batch writing mode.

        Usage:
            with logger.batch_mode() as batch:
                for reading in readings:
                    batch.append(reading)
        """
        batch = []

        try:
            yield batch
        finally:
            if batch:
                self.log_batch(batch)

    def __repr__(self) -> str:
        """String representation of data logger."""
        return f"DataLogger(file='{self.filename}', size={self.get_file_size_mb():.2f}MB)"
