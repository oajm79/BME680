"""Tests for the SQLite database manager."""

import sys
import tempfile
import os
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from bme680_monitor.database import DatabaseManager


class TestDatabaseManagerRoundTrip:
    """Test suite for DatabaseManager read/write round-trips."""

    @pytest.fixture
    def db(self):
        fd, path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        os.remove(path)  # DatabaseManager creates it
        manager = DatabaseManager(db_path=path)
        yield manager
        manager.close()
        if os.path.exists(path):
            os.remove(path)

    def test_log_reading_then_get_recent_readings_round_trip(self, db):
        row_id = db.log_reading(
            temperature=21.5, humidity=40.0, pressure=1012.0,
            gas_resistance=95000.0, air_quality_index=2, air_quality_label="Moderate",
            comfort_level=1, comfort_label="Comfortable"
        )
        assert row_id > 0

        readings = db.get_recent_readings(limit=10)
        assert len(readings) == 1
        assert readings[0]["temperature_c"] == 21.5
        assert readings[0]["air_quality_label"] == "Moderate"

    def test_get_statistics_reflects_logged_readings(self, db):
        db.log_reading(temperature=20.0, humidity=40.0, pressure=1010.0)
        db.log_reading(temperature=24.0, humidity=50.0, pressure=1014.0)

        stats = db.get_statistics(hours=24)

        assert stats["reading_count"] == 2
        assert stats["temp_min"] == 20.0
        assert stats["temp_max"] == 24.0
        assert stats["temp_avg"] == 22.0

    def test_cleanup_old_data_on_fresh_readings_deletes_nothing(self, db):
        db.log_reading(temperature=20.0, humidity=40.0, pressure=1010.0)

        deleted = db.cleanup_old_data(days=30)

        assert deleted == 0
        assert len(db.get_recent_readings(limit=10)) == 1

    def test_utc_timestamp_and_recent_hour_filtering(self, db):
        """Verify fix for BME680#7: readings are stored in UTC and 1-hour filter works accurately."""
        row_id = db.log_reading(temperature=22.0, humidity=42.0, pressure=1013.25)
        assert row_id > 0

        readings = db.get_recent_readings(limit=10)
        assert len(readings) == 1
        ts = readings[0]["timestamp"]
        # Format must be SQLite standard 'YYYY-MM-DD HH:MM:SS' without 'T'
        assert "T" not in ts
        assert len(ts) == 19

        # Filter for last 1 hour must include this fresh reading
        recent_1h = db.get_recent_readings(hours=1)
        assert len(recent_1h) == 1
        assert recent_1h[0]["temperature_c"] == 22.0

        # Stats for last 1 hour must reflect the reading
        stats_1h = db.get_statistics(hours=1)
        assert stats_1h["reading_count"] == 1
        assert stats_1h["temp_avg"] == 22.0

    def test_legacy_iso_timestamp_normalization(self, db):
        """Verify that legacy ISO timestamps with 'T' are normalized upon initialization."""
        cursor = db.connection.cursor()
        cursor.execute(f"""
            INSERT INTO {db.table_name} (
                timestamp, temperature_c, humidity_rh, pressure_hpa
            ) VALUES ('2026-01-01T12:00:00', 19.5, 45.0, 1015.0)
        """)
        db.connection.commit()

        # Re-initialize database to trigger migration
        db._initialize_database()

        cursor.execute(f"SELECT timestamp FROM {db.table_name} WHERE temperature_c = 19.5")
        migrated_ts = cursor.fetchone()[0]
        assert migrated_ts == "2026-01-01 12:00:00"
        assert "T" not in migrated_ts

