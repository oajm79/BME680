"""Unit tests for BME680 chart generator, SQLite downsampling, and MCP server."""

import importlib.util
import io
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from PIL import Image

from bme680_monitor.chart_generator import (
    MAX_HOURS,
    fetch_bme680_history,
    generate_bme680_chart,
    resolve_time_window,
    select_bucket_seconds,
)
from bme680_monitor.database import DatabaseManager

PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


def _load_mcp_module():
    """Dynamically load bme680-tools-mcp.py for unit testing."""
    mcp_path = Path(__file__).resolve().parent.parent / "bme680-tools-mcp.py"
    spec = importlib.util.spec_from_file_location("bme680_tools_mcp", mcp_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class TestBucketAndWindowGuardrails:
    """Tests for bucket resolution and 7-day (168h) guardrail clamping."""

    def test_select_bucket_seconds_tiers(self):
        assert select_bucket_seconds(1) == 300
        assert select_bucket_seconds(12) == 300
        assert select_bucket_seconds(24) == 300
        assert select_bucket_seconds(24.5) == 900
        assert select_bucket_seconds(48) == 900
        assert select_bucket_seconds(72) == 900
        assert select_bucket_seconds(72.1) == 3600
        assert select_bucket_seconds(168) == 3600

    def test_default_and_clamped_hours(self):
        ref_now = datetime(2026, 10, 29, 12, 0, 0, tzinfo=timezone.utc)
        win_default = resolve_time_window(now=ref_now)
        assert win_default["hours"] == 12.0
        assert win_default["clamped"] is False
        assert win_default["bucket_seconds"] == 300

        win_clamped = resolve_time_window(hours=500, now=ref_now)
        assert win_clamped["requested_hours"] == 500.0
        assert win_clamped["hours"] == MAX_HOURS == 168.0
        assert win_clamped["clamped"] is True
        assert win_clamped["bucket_seconds"] == 3600
        assert "Clamped to 7d Max" in win_clamped["window_label"]

    def test_preset_last_night_and_today(self):
        local_tz = timezone(timedelta(hours=-4))
        ref_now = datetime(2026, 10, 29, 9, 30, 0, tzinfo=local_tz)

        win_night = resolve_time_window(preset="last_night", now=ref_now)
        assert win_night["preset"] == "last_night"
        assert win_night["hours"] == 10.0
        assert win_night["start_local"] == datetime(2026, 10, 28, 22, 0, 0, tzinfo=local_tz)
        assert win_night["end_local"] == datetime(2026, 10, 29, 8, 0, 0, tzinfo=local_tz)
        assert win_night["bucket_seconds"] == 300
        assert win_night["clamped"] is False

        win_today = resolve_time_window(preset="today", now=ref_now)
        assert win_today["preset"] == "today"
        assert win_today["start_local"] == datetime(2026, 10, 29, 0, 0, 0, tzinfo=local_tz)
        assert win_today["end_local"] == ref_now
        assert pytest.approx(win_today["hours"], rel=1e-3) == 9.5
        assert win_today["bucket_seconds"] == 300

        win_7d = resolve_time_window(preset="last_7d", now=ref_now)
        assert win_7d["hours"] == 168.0
        assert win_7d["bucket_seconds"] == 3600

    def test_invalid_preset_raises(self):
        with pytest.raises(ValueError, match="Invalid preset"):
            resolve_time_window(preset="last_year")


class TestSQLiteDownsamplingAndRendering:
    """Tests for local SQLite downsampling, SSH fallback, and Pillow PNG rendering."""

    @pytest.fixture
    def synthetic_db(self, tmp_path: Path):
        db_file = tmp_path / "sensor_data.db"
        ref_now = datetime(2026, 10, 29, 12, 0, 0, tzinfo=timezone.utc)
        with DatabaseManager(db_path=str(db_file)) as db:
            # Insert 72 readings at 10-minute intervals over the last 12 hours
            for i in range(72):
                ts = ref_now - timedelta(minutes=(71 - i) * 10)
                temp = 20.5 + 2.5 * ((i % 12) / 12.0)
                hum = 42.0 + 8.0 * ((i % 8) / 8.0)
                press = 1012.0 + (i * 0.05)
                gas = 85000.0 + (i * 1200.0)
                db.log_reading(
                    temperature=temp,
                    humidity=hum,
                    pressure=press,
                    gas_resistance=gas,
                    air_quality_index=3 if gas > 100000 else 2,
                    air_quality_label="Good" if gas > 100000 else "Moderate",
                    comfort_level=4,
                    comfort_label="Comfortable",
                    timestamp=ts,
                )
        return db_file, ref_now

    def test_local_sqlite_downsampling(self, synthetic_db):
        db_file, ref_now = synthetic_db
        history = fetch_bme680_history(hours=12, db_path=db_file, now=ref_now)

        assert history["source"].startswith("local:")
        assert history["window"]["bucket_seconds"] == 300
        assert history["stats"]["total_samples"] == 72
        assert history["stats"]["bucket_count"] == 72
        assert history["latest"] is not None
        assert history["latest"]["air_quality_label"] == "Good"
        assert history["latest"]["comfort_label"] == "Comfortable"

        t_stats = history["stats"]["temperature"]
        assert 20.0 <= t_stats["min"] <= t_stats["avg"] <= t_stats["max"] <= 24.0

    def test_remote_ssh_downsampling_fallback(self, tmp_path: Path):
        missing_db = tmp_path / "nonexistent.db"
        ref_now = datetime(2026, 10, 29, 12, 0, 0, tzinfo=timezone.utc)
        mock_stdout = (
            "B|1793270400|2026-10-29 10:40:00|21.4|21.1|21.8|45.2|44.0|46.5|1013.2|1013.0|1013.5|120000|115000|125000|3.0|15\n"
            "B|1793270700|2026-10-29 10:45:00|21.7|21.5|22.0|45.8|45.0|46.9|1013.4|1013.1|1013.6|124000|120000|128000|3.0|15\n"
            "L|2026-10-29 11:59:50|21.9|45.5|1013.5|126000|3|Good|4|Comfortable\n"
        )
        with patch("bme680_monitor.chart_generator.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout=mock_stdout, stderr="")
            history = fetch_bme680_history(hours=6, db_path=missing_db, now=ref_now)

        assert history["source"].startswith("ssh:")
        assert history["stats"]["bucket_count"] == 2
        assert history["stats"]["total_samples"] == 30
        assert history["latest"]["temperature_c"] == 21.9
        assert history["latest"]["gas_kohm"] == 126.0

    @pytest.mark.parametrize(
        "metric,expected_size",
        [
            ("all", (1200, 900)),
            ("temperature", (1200, 750)),
            ("humidity", (1200, 750)),
            ("air_quality", (1200, 750)),
            ("pressure", (1200, 750)),
        ],
    )
    def test_generate_bme680_chart_metrics(self, synthetic_db, tmp_path: Path, metric, expected_size):
        db_file, ref_now = synthetic_db
        history = fetch_bme680_history(hours=12, db_path=db_file, now=ref_now)
        out_file = tmp_path / f"chart_{metric}.png"

        png_bytes = generate_bme680_chart(history, metric=metric, output_path=out_file)
        assert png_bytes[:8] == PNG_MAGIC
        assert out_file.exists()

        img = Image.open(io.BytesIO(png_bytes))
        assert img.format == "PNG"
        assert img.size == expected_size


class TestMCPToolAndIdempotency:
    """Tests for bme680-tools-mcp.py execution, WhatsApp photo dispatch, and IdempotencyGuard."""

    def test_mcp_tool_dispatch_and_idempotency(self, tmp_path: Path):
        db_file = tmp_path / "sensor_data.db"
        ref_now = datetime.now(timezone.utc)
        with DatabaseManager(db_path=str(db_file)) as db:
            for i in range(10):
                db.log_reading(
                    temperature=22.0 + i * 0.1,
                    humidity=45.0,
                    pressure=1013.0,
                    gas_resistance=110000.0,
                    air_quality_index=3,
                    air_quality_label="Good",
                    comfort_level=4,
                    comfort_label="Comfortable",
                    timestamp=ref_now - timedelta(minutes=(9 - i) * 5),
                )

        mcp_mod = _load_mcp_module()
        mcp_mod._idempotency.cache.clear()

        with patch.object(mcp_mod, "OpenClawClient") as mock_oc_cls:
            mock_client = MagicMock()
            mock_client.send_photo.return_value = True
            mock_oc_cls.return_value = mock_client

            args = {
                "metric": "temperature",
                "hours": 240,  # Exceeds 168h -> must clamp
                "send_to_whatsapp": True,
                "recipient": "+15550001111",
            }
            output = mcp_mod.handle_get_bme680_telemetry_chart(args, db_path=db_file)

            assert "Yes (clamped to 168h max)" in output
            assert "Sent to +15550001111" in output
            assert "Temperature:" in output
            mock_oc_cls.assert_called_once_with(channel="whatsapp", target="+15550001111")
            mock_client.send_photo.assert_called_once()
            sent_kwargs = mock_client.send_photo.call_args.kwargs
            assert sent_kwargs["photo"][:8] == PNG_MAGIC
            assert "BME680 Indoor Telemetry" in sent_kwargs["caption"]

            # Verify IdempotencyGuard caches identical call
            mcp_mod._idempotency.record("get_bme680_telemetry_chart", args, output)
            is_cached, cached_val = mcp_mod._idempotency.check("get_bme680_telemetry_chart", args)
            assert is_cached is True
            assert output in cached_val
            assert "CONTROL DIRECTIVE" in cached_val
