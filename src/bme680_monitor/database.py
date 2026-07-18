"""SQLite database management for BME680 sensor readings."""

import logging
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any

logger = logging.getLogger(__name__)


class DatabaseManager:
    """
    Manages SQLite database for storing sensor readings.

    Replaces CSV logging with a proper database for better querying,
    data integrity, and storage efficiency.
    """

    def __init__(
        self,
        db_path: str = "data/sensor_data.db",
        table_name: str = "measurements"
    ):
        """
        Initialize database manager.

        Args:
            db_path: Path to SQLite database file
            table_name: Name of the measurements table
        """
        self.db_path = Path(db_path)
        self.table_name = table_name
        self.connection: Optional[sqlite3.Connection] = None

        # Ensure directory exists
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        # Initialize database
        self._initialize_database()

    def _initialize_database(self) -> None:
        """Create database and tables if they don't exist."""
        try:
            self.connection = sqlite3.connect(str(self.db_path))
            self.connection.row_factory = sqlite3.Row

            cursor = self.connection.cursor()

            # Create measurements table
            cursor.execute(f"""
                CREATE TABLE IF NOT EXISTS {self.table_name} (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    temperature_c REAL NOT NULL,
                    humidity_rh REAL NOT NULL,
                    pressure_hpa REAL NOT NULL,
                    gas_resistance_ohms REAL,
                    air_quality_index INTEGER,
                    air_quality_label TEXT,
                    comfort_level INTEGER,
                    comfort_label TEXT
                )
            """)

            # Create index on timestamp for faster queries
            cursor.execute(f"""
                CREATE INDEX IF NOT EXISTS idx_{self.table_name}_timestamp
                ON {self.table_name}(timestamp)
            """)

            self.connection.commit()
            logger.info(f"Database initialized: {self.db_path}")

        except sqlite3.Error as e:
            logger.error(f"Error initializing database: {e}")
            raise

    def log_reading(
        self,
        temperature: float,
        humidity: float,
        pressure: float,
        gas_resistance: Optional[float] = None,
        air_quality_index: Optional[int] = None,
        air_quality_label: Optional[str] = None,
        comfort_level: Optional[int] = None,
        comfort_label: Optional[str] = None
    ) -> int:
        """
        Log a sensor reading to the database.

        Args:
            temperature: Temperature in Celsius
            humidity: Relative humidity in %
            pressure: Atmospheric pressure in hPa
            gas_resistance: Gas resistance in Ohms
            air_quality_index: Air quality index (0-3)
            air_quality_label: Air quality label
            comfort_level: Comfort level (0-4)
            comfort_label: Comfort label

        Returns:
            The ID of the inserted row
        """
        if not self.connection:
            logger.error("Database not connected")
            return -1

        try:
            cursor = self.connection.cursor()
            cursor.execute(f"""
                INSERT INTO {self.table_name} (
                    timestamp, temperature_c, humidity_rh, pressure_hpa,
                    gas_resistance_ohms, air_quality_index, air_quality_label,
                    comfort_level, comfort_label
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                datetime.now().isoformat(),
                temperature,
                humidity,
                pressure,
                gas_resistance,
                air_quality_index,
                air_quality_label,
                comfort_level,
                comfort_label
            ))

            self.connection.commit()
            return cursor.lastrowid

        except sqlite3.Error as e:
            logger.error(f"Error logging reading to database: {e}")
            return -1

    def get_recent_readings(
        self,
        limit: int = 100,
        hours: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Get recent sensor readings.

        Args:
            limit: Maximum number of readings to return
            hours: If provided, only return readings from last N hours

        Returns:
            List of readings as dictionaries
        """
        if not self.connection:
            return []

        try:
            cursor = self.connection.cursor()

            if hours:
                cursor.execute(f"""
                    SELECT * FROM {self.table_name}
                    WHERE timestamp >= datetime('now', '-{hours} hours')
                    ORDER BY timestamp DESC
                    LIMIT ?
                """, (limit,))
            else:
                cursor.execute(f"""
                    SELECT * FROM {self.table_name}
                    ORDER BY timestamp DESC
                    LIMIT ?
                """, (limit,))

            return [dict(row) for row in cursor.fetchall()]

        except sqlite3.Error as e:
            logger.error(f"Error getting recent readings: {e}")
            return []

    def get_statistics(self, hours: int = 24) -> Dict[str, Any]:
        """
        Get statistics for the last N hours.

        Args:
            hours: Number of hours to analyze

        Returns:
            Dictionary with min, max, avg for each measurement
        """
        if not self.connection:
            return {}

        try:
            cursor = self.connection.cursor()
            cursor.execute(f"""
                SELECT
                    MIN(temperature_c) as temp_min,
                    MAX(temperature_c) as temp_max,
                    AVG(temperature_c) as temp_avg,
                    MIN(humidity_rh) as humidity_min,
                    MAX(humidity_rh) as humidity_max,
                    AVG(humidity_rh) as humidity_avg,
                    MIN(pressure_hpa) as pressure_min,
                    MAX(pressure_hpa) as pressure_max,
                    AVG(pressure_hpa) as pressure_avg,
                    MIN(gas_resistance_ohms) as gas_min,
                    MAX(gas_resistance_ohms) as gas_max,
                    AVG(gas_resistance_ohms) as gas_avg,
                    COUNT(*) as reading_count
                FROM {self.table_name}
                WHERE timestamp >= datetime('now', '-{hours} hours')
            """)

            row = cursor.fetchone()
            if row:
                return dict(row)
            return {}

        except sqlite3.Error as e:
            logger.error(f"Error getting statistics: {e}")
            return {}

    def cleanup_old_data(self, days: int = 30) -> int:
        """
        Delete readings older than N days.

        Args:
            days: Number of days to keep

        Returns:
            Number of deleted rows
        """
        if not self.connection:
            return 0

        try:
            cursor = self.connection.cursor()
            cursor.execute(f"""
                DELETE FROM {self.table_name}
                WHERE timestamp < datetime('now', '-{days} days')
            """)

            deleted = cursor.rowcount
            self.connection.commit()

            if deleted > 0:
                logger.info(f"Cleaned up {deleted} old readings")
                # Vacuum to reclaim space
                cursor.execute("VACUUM")

            return deleted

        except sqlite3.Error as e:
            logger.error(f"Error cleaning up old data: {e}")
            return 0

    def export_to_csv(self, output_path: str, hours: Optional[int] = None) -> bool:
        """
        Export database data to CSV for compatibility.

        Args:
            output_path: Path to output CSV file
            hours: If provided, only export last N hours

        Returns:
            True if export was successful
        """
        import csv

        if not self.connection:
            return False

        try:
            readings = self.get_recent_readings(limit=100000, hours=hours)

            if not readings:
                logger.warning("No data to export")
                return False

            with open(output_path, 'w', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=readings[0].keys())
                writer.writeheader()
                writer.writerows(readings)

            logger.info(f"Exported {len(readings)} readings to {output_path}")
            return True

        except Exception as e:
            logger.error(f"Error exporting to CSV: {e}")
            return False

    def close(self) -> None:
        """Close database connection."""
        if self.connection:
            self.connection.close()
            self.connection = None
            logger.debug("Database connection closed")

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()

    def __del__(self):
        """Destructor to ensure connection is closed."""
        self.close()
