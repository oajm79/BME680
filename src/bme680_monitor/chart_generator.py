"""
On-demand BME680 telemetry chart generator and SQLite downsampling fetcher.

Provides:
- Timeframe resolution with semantic presets ('last_night', 'today', 'last_24h', 'last_7d')
  and a hard 7-day (168h) guardrail clamp.
- SQLite bucketed downsampling locally or via SSH to the Pi Zero 2W sensor node
  (300s buckets <=24h, 900s buckets <=72h, 3600s buckets >72h) to protect the Pi Zero's
  512 MB RAM and minimize rows transferred.
- High-DPI dark-theme PNG rendering using Pillow (2x supersampling + LANCZOS downscale).
"""

import io
import logging
import math
import os
import sqlite3
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from PIL import Image, ImageDraw, ImageFont

logger = logging.getLogger(__name__)

# Timeframe guardrails
DEFAULT_HOURS = 12.0
MIN_HOURS = 1.0
MAX_HOURS = 168.0  # Hard 7-day cap

VALID_METRICS = ("all", "temperature", "humidity", "air_quality", "pressure")
VALID_PRESETS = ("last_night", "today", "last_24h", "last_7d")

DEFAULT_LOCAL_DB_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "sensor_data.db"
DEFAULT_REMOTE_HOST = os.getenv("BME680_REMOTE_HOST", "oajm@10.0.0.219")
DEFAULT_REMOTE_DB_PATH = os.getenv(
    "BME680_REMOTE_DB_PATH", "/home/oajm/projects/BME680/data/sensor_data.db"
)

# Dark Homelab palette
BG_COLOR = (26, 26, 46, 255)          # #1a1a2e
PANEL_BG_COLOR = (22, 33, 62, 255)    # #16213e
PANEL_BORDER_COLOR = (42, 42, 74, 255)  # #2a2a4a
GRID_COLOR = (42, 42, 74, 255)        # #2a2a4a
TEXT_PRIMARY = (224, 224, 224, 255)   # #e0e0e0
TEXT_MUTED = (148, 163, 184, 255)     # #94a3b8

METRIC_SPECS: Dict[str, Dict[str, Any]] = {
    "temperature": {
        "title": "Temperature",
        "unit": "°C",
        "line_color": (255, 107, 107, 255),      # #ff6b6b coral
        "band_color": (255, 107, 107, 50),
        "ref_color": (78, 205, 196, 180),        # #4ecdc4 cyan
        "avg_key": "temp_avg",
        "min_key": "temp_min",
        "max_key": "temp_max",
        "latest_key": "temperature_c",
        "thresholds": [
            (18.0, "18°C Min Comfort"),
            (24.0, "24°C Max Comfort"),
        ],
        "decimals": 1,
    },
    "humidity": {
        "title": "Relative Humidity",
        "unit": "%RH",
        "line_color": (56, 189, 248, 255),       # #38bdf8 sky blue
        "band_color": (56, 189, 248, 50),
        "ref_color": (78, 205, 196, 180),
        "avg_key": "hum_avg",
        "min_key": "hum_min",
        "max_key": "hum_max",
        "latest_key": "humidity_rh",
        "thresholds": [
            (30.0, "30% Dry Limit"),
            (60.0, "60% Humid Limit"),
        ],
        "decimals": 1,
    },
    "air_quality": {
        "title": "Air Quality (VOC Gas Resistance)",
        "unit": "kΩ",
        "line_color": (16, 185, 129, 255),       # #10b981 emerald
        "band_color": (16, 185, 129, 50),
        "ref_color": (245, 158, 11, 180),        # #f59e0b amber
        "avg_key": "gas_kohm_avg",
        "min_key": "gas_kohm_min",
        "max_key": "gas_kohm_max",
        "latest_key": "gas_kohm",
        "thresholds": [
            (50.0, "50 kΩ Moderate"),
            (100.0, "100 kΩ Good"),
        ],
        "decimals": 1,
    },
    "pressure": {
        "title": "Atmospheric Pressure",
        "unit": "hPa",
        "line_color": (245, 158, 11, 255),       # #f59e0b amber
        "band_color": (245, 158, 11, 50),
        "ref_color": (148, 163, 184, 160),
        "avg_key": "press_avg",
        "min_key": "press_min",
        "max_key": "press_max",
        "latest_key": "pressure_hpa",
        "thresholds": [
            (1013.25, "1013.25 hPa Sea Level"),
        ],
        "decimals": 1,
    },
}


def select_bucket_seconds(hours: float) -> int:
    """
    Select SQLite aggregation bucket size in seconds based on window duration.

    - <= 24h: 300s (5-minute buckets, max 288 points)
    - 24h < hours <= 72h: 900s (15-minute buckets, max 288 points)
    - > 72h: 3600s (60-minute buckets, max 168 points)
    """
    if hours <= 24.0:
        return 300
    if hours <= 72.0:
        return 900
    return 3600


def resolve_time_window(
    hours: Optional[Union[int, float]] = None,
    preset: Optional[str] = None,
    now: Optional[datetime] = None,
) -> Dict[str, Any]:
    """
    Resolve time window and apply the 168-hour (7-day) guardrail cap.

    Args:
        hours: Requested window in hours (default 12). Clamped to [1, 168].
        preset: Optional semantic preset ('last_night', 'today', 'last_24h', 'last_7d').
        now: Optional reference datetime (defaults to local system time).

    Returns:
        Dictionary containing start_utc, end_utc, start_local, end_local,
        hours, requested_hours, clamped, bucket_seconds, and window_label.
    """
    if now is None:
        now_local = datetime.now().astimezone()
    elif now.tzinfo is None:
        now_local = now.astimezone()
    else:
        now_local = now

    clamped = False
    preset_norm = preset.strip().lower() if preset else None

    if preset_norm:
        if preset_norm not in VALID_PRESETS:
            raise ValueError(
                f"Invalid preset '{preset}'. Must be one of {VALID_PRESETS}."
            )
        if preset_norm == "last_night":
            yesterday = (now_local - timedelta(days=1)).date()
            today = now_local.date()
            tz = now_local.tzinfo
            start_local = datetime(yesterday.year, yesterday.month, yesterday.day, 22, 0, 0, tzinfo=tz)
            end_local = datetime(today.year, today.month, today.day, 8, 0, 0, tzinfo=tz)
            effective_hours = 10.0
            requested_hours = 10.0
            window_label = "Last Night (22:00 – 08:00)"
        elif preset_norm == "today":
            today = now_local.date()
            tz = now_local.tzinfo
            start_local = datetime(today.year, today.month, today.day, 0, 0, 0, tzinfo=tz)
            end_local = now_local
            elapsed_hours = max(0.25, (end_local - start_local).total_seconds() / 3600.0)
            effective_hours = elapsed_hours
            requested_hours = round(elapsed_hours, 2)
            window_label = f"Today (00:00 – {end_local.strftime('%H:%M')})"
        elif preset_norm == "last_24h":
            effective_hours = 24.0
            requested_hours = 24.0
            end_local = now_local
            start_local = end_local - timedelta(hours=24.0)
            window_label = "Last 24 Hours"
        else:  # last_7d
            effective_hours = MAX_HOURS
            requested_hours = MAX_HOURS
            end_local = now_local
            start_local = end_local - timedelta(hours=MAX_HOURS)
            window_label = "Last 7 Days (168h)"
    else:
        raw_hours = float(hours) if hours is not None else DEFAULT_HOURS
        requested_hours = raw_hours
        if raw_hours > MAX_HOURS:
            effective_hours = MAX_HOURS
            clamped = True
        elif raw_hours < MIN_HOURS:
            effective_hours = MIN_HOURS
        else:
            effective_hours = raw_hours

        end_local = now_local
        start_local = end_local - timedelta(hours=effective_hours)
        if effective_hours == int(effective_hours):
            window_label = f"Last {int(effective_hours)}h"
        else:
            window_label = f"Last {effective_hours:.1f}h"
        if clamped:
            window_label += " (Clamped to 7d Max)"

    start_utc = start_local.astimezone(timezone.utc)
    end_utc = end_local.astimezone(timezone.utc)
    bucket_seconds = select_bucket_seconds(effective_hours)

    return {
        "preset": preset_norm,
        "requested_hours": requested_hours,
        "hours": effective_hours,
        "clamped": clamped,
        "bucket_seconds": bucket_seconds,
        "start_local": start_local,
        "end_local": end_local,
        "start_utc": start_utc,
        "end_utc": end_utc,
        "start_utc_str": start_utc.strftime("%Y-%m-%d %H:%M:%S"),
        "end_utc_str": end_utc.strftime("%Y-%m-%d %H:%M:%S"),
        "window_label": window_label,
    }


def _enrich_bucket_row(row_dict: Dict[str, Any]) -> Dict[str, Any]:
    """Convert raw bucket row values into float types and compute kOhm gas metrics."""
    bucket_epoch = int(row_dict["bucket_epoch"])
    bucket_dt_utc = datetime.fromtimestamp(bucket_epoch, tz=timezone.utc)
    bucket_dt_local = bucket_dt_utc.astimezone()

    gas_avg = float(row_dict["gas_avg"]) if row_dict.get("gas_avg") is not None else 0.0
    gas_min = float(row_dict["gas_min"]) if row_dict.get("gas_min") is not None else 0.0
    gas_max = float(row_dict["gas_max"]) if row_dict.get("gas_max") is not None else 0.0

    return {
        "bucket_epoch": bucket_epoch,
        "bucket_ts": row_dict.get("bucket_ts") or bucket_dt_utc.strftime("%Y-%m-%d %H:%M:%S"),
        "local_dt": bucket_dt_local,
        "temp_avg": float(row_dict["temp_avg"]),
        "temp_min": float(row_dict["temp_min"]),
        "temp_max": float(row_dict["temp_max"]),
        "hum_avg": float(row_dict["hum_avg"]),
        "hum_min": float(row_dict["hum_min"]),
        "hum_max": float(row_dict["hum_max"]),
        "press_avg": float(row_dict["press_avg"]),
        "press_min": float(row_dict["press_min"]),
        "press_max": float(row_dict["press_max"]),
        "gas_avg": gas_avg,
        "gas_min": gas_min,
        "gas_max": gas_max,
        "gas_kohm_avg": gas_avg / 1000.0,
        "gas_kohm_min": gas_min / 1000.0,
        "gas_kohm_max": gas_max / 1000.0,
        "aqi_avg": float(row_dict["aqi_avg"]) if row_dict.get("aqi_avg") is not None else 0.0,
        "sample_count": int(row_dict.get("sample_count") or 0),
    }


def _enrich_latest_row(row_dict: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Normalize the latest raw sensor reading dictionary."""
    if not row_dict:
        return None
    gas_ohms = float(row_dict.get("gas_resistance_ohms") or 0.0)
    return {
        "timestamp": str(row_dict.get("timestamp") or ""),
        "temperature_c": float(row_dict["temperature_c"]),
        "humidity_rh": float(row_dict["humidity_rh"]),
        "pressure_hpa": float(row_dict["pressure_hpa"]),
        "gas_resistance_ohms": gas_ohms,
        "gas_kohm": gas_ohms / 1000.0,
        "air_quality_index": (
            int(row_dict["air_quality_index"])
            if row_dict.get("air_quality_index") is not None and str(row_dict["air_quality_index"]) != ""
            else None
        ),
        "air_quality_label": str(row_dict.get("air_quality_label") or "Unknown"),
        "comfort_level": (
            int(row_dict["comfort_level"])
            if row_dict.get("comfort_level") is not None and str(row_dict["comfort_level"]) != ""
            else None
        ),
        "comfort_label": str(row_dict.get("comfort_label") or "Unknown"),
    }


def _query_local_sqlite(
    db_path: Path,
    start_utc_str: str,
    end_utc_str: str,
    bucket_sec: int,
    table_name: str = "measurements",
) -> Tuple[List[Dict[str, Any]], Optional[Dict[str, Any]]]:
    """Execute the downsampling query and latest-row query against a local SQLite database."""
    bucket_sql = f"""
        SELECT
            CAST(strftime('%s', timestamp) / ? AS INTEGER) * ? AS bucket_epoch,
            datetime(CAST(strftime('%s', timestamp) / ? AS INTEGER) * ?, 'unixepoch') AS bucket_ts,
            AVG(temperature_c) AS temp_avg,
            MIN(temperature_c) AS temp_min,
            MAX(temperature_c) AS temp_max,
            AVG(humidity_rh) AS hum_avg,
            MIN(humidity_rh) AS hum_min,
            MAX(humidity_rh) AS hum_max,
            AVG(pressure_hpa) AS press_avg,
            MIN(pressure_hpa) AS press_min,
            MAX(pressure_hpa) AS press_max,
            AVG(gas_resistance_ohms) AS gas_avg,
            MIN(gas_resistance_ohms) AS gas_min,
            MAX(gas_resistance_ohms) AS gas_max,
            AVG(air_quality_index) AS aqi_avg,
            COUNT(*) AS sample_count
        FROM {table_name}
        WHERE timestamp >= ? AND timestamp <= ?
        GROUP BY bucket_epoch
        ORDER BY bucket_epoch ASC
    """
    latest_sql = f"""
        SELECT
            timestamp, temperature_c, humidity_rh, pressure_hpa,
            gas_resistance_ohms, air_quality_index, air_quality_label,
            comfort_level, comfort_label
        FROM {table_name}
        ORDER BY id DESC
        LIMIT 1
    """
    with sqlite3.connect(str(db_path), timeout=5.0) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute(
            bucket_sql,
            (bucket_sec, bucket_sec, bucket_sec, bucket_sec, start_utc_str, end_utc_str),
        )
        buckets = [_enrich_bucket_row(dict(r)) for r in cur.fetchall()]

        cur.execute(latest_sql)
        latest_row = cur.fetchone()
        latest = _enrich_latest_row(dict(latest_row)) if latest_row else None

    return buckets, latest


def _query_remote_sqlite(
    remote_host: str,
    remote_db_path: str,
    start_utc_str: str,
    end_utc_str: str,
    bucket_sec: int,
    table_name: str = "measurements",
) -> Tuple[List[Dict[str, Any]], Optional[Dict[str, Any]]]:
    """
    Execute a single aggregated SQLite query on the remote Pi Zero 2W via SSH.

    Performs server-side downsampling so the Pi Zero's 512 MB RAM is protected
    and <250 compact lines are transmitted over the network.
    """
    safe_start = start_utc_str.replace("'", "")
    safe_end = end_utc_str.replace("'", "")
    safe_table = "".join(ch for ch in table_name if ch.isalnum() or ch == "_")
    b_sec = int(bucket_sec)

    sql_script = (
        f"SELECT 'B', "
        f"CAST(strftime('%s', timestamp) / {b_sec} AS INTEGER) * {b_sec} AS bucket_epoch, "
        f"datetime(CAST(strftime('%s', timestamp) / {b_sec} AS INTEGER) * {b_sec}, 'unixepoch') AS bucket_ts, "
        f"AVG(temperature_c), MIN(temperature_c), MAX(temperature_c), "
        f"AVG(humidity_rh), MIN(humidity_rh), MAX(humidity_rh), "
        f"AVG(pressure_hpa), MIN(pressure_hpa), MAX(pressure_hpa), "
        f"IFNULL(AVG(gas_resistance_ohms), 0), IFNULL(MIN(gas_resistance_ohms), 0), IFNULL(MAX(gas_resistance_ohms), 0), "
        f"IFNULL(AVG(air_quality_index), 0), COUNT(*) "
        f"FROM {safe_table} "
        f"WHERE timestamp >= '{safe_start}' AND timestamp <= '{safe_end}' "
        f"GROUP BY bucket_epoch ORDER BY bucket_epoch ASC; "
        f"SELECT 'L', timestamp, temperature_c, humidity_rh, pressure_hpa, "
        f"IFNULL(gas_resistance_ohms, 0), IFNULL(air_quality_index, ''), "
        f"IFNULL(air_quality_label, ''), IFNULL(comfort_level, ''), IFNULL(comfort_label, '') "
        f"FROM {safe_table} ORDER BY id DESC LIMIT 1;"
    )

    remote_cmd = f"sqlite3 -cmd '.timeout 5000' {remote_db_path} \"{sql_script}\""
    cmd = [
        "ssh",
        "-o", "BatchMode=yes",
        "-o", "ConnectTimeout=5",
        remote_host,
        remote_cmd,
    ]

    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
    if proc.returncode != 0:
        raise RuntimeError(
            f"Remote SQLite SSH query failed (exit {proc.returncode}): {proc.stderr.strip()}"
        )

    buckets: List[Dict[str, Any]] = []
    latest: Optional[Dict[str, Any]] = None

    for raw_line in proc.stdout.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        parts = line.split("|")
        tag = parts[0]
        if tag == "B" and len(parts) >= 17:
            row_dict = {
                "bucket_epoch": int(parts[1]),
                "bucket_ts": parts[2],
                "temp_avg": float(parts[3]),
                "temp_min": float(parts[4]),
                "temp_max": float(parts[5]),
                "hum_avg": float(parts[6]),
                "hum_min": float(parts[7]),
                "hum_max": float(parts[8]),
                "press_avg": float(parts[9]),
                "press_min": float(parts[10]),
                "press_max": float(parts[11]),
                "gas_avg": float(parts[12]),
                "gas_min": float(parts[13]),
                "gas_max": float(parts[14]),
                "aqi_avg": float(parts[15]),
                "sample_count": int(parts[16]),
            }
            buckets.append(_enrich_bucket_row(row_dict))
        elif tag == "L" and len(parts) >= 10:
            latest_dict = {
                "timestamp": parts[1],
                "temperature_c": float(parts[2]),
                "humidity_rh": float(parts[3]),
                "pressure_hpa": float(parts[4]),
                "gas_resistance_ohms": float(parts[5]),
                "air_quality_index": int(parts[6]) if parts[6] != "" else None,
                "air_quality_label": parts[7] or "Unknown",
                "comfort_level": int(parts[8]) if parts[8] != "" else None,
                "comfort_label": parts[9] or "Unknown",
            }
            latest = _enrich_latest_row(latest_dict)

    return buckets, latest


def _compute_summary_stats(
    buckets: List[Dict[str, Any]],
    latest: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    """Compute overall min, max, weighted average, and total raw sample count across buckets."""
    if not buckets:
        return {
            "total_samples": 0,
            "bucket_count": 0,
            "latest": latest,
        }

    total_samples = sum(b["sample_count"] for b in buckets)
    weight_denom = total_samples if total_samples > 0 else len(buckets)

    def _wavg(key: str) -> float:
        if total_samples > 0:
            return sum(b[key] * b["sample_count"] for b in buckets) / weight_denom
        return sum(b[key] for b in buckets) / len(buckets)

    return {
        "total_samples": total_samples,
        "bucket_count": len(buckets),
        "temperature": {
            "min": min(b["temp_min"] for b in buckets),
            "max": max(b["temp_max"] for b in buckets),
            "avg": _wavg("temp_avg"),
            "last": latest["temperature_c"] if latest else buckets[-1]["temp_avg"],
        },
        "humidity": {
            "min": min(b["hum_min"] for b in buckets),
            "max": max(b["hum_max"] for b in buckets),
            "avg": _wavg("hum_avg"),
            "last": latest["humidity_rh"] if latest else buckets[-1]["hum_avg"],
        },
        "pressure": {
            "min": min(b["press_min"] for b in buckets),
            "max": max(b["press_max"] for b in buckets),
            "avg": _wavg("press_avg"),
            "last": latest["pressure_hpa"] if latest else buckets[-1]["press_avg"],
        },
        "air_quality": {
            "min": min(b["gas_kohm_min"] for b in buckets),
            "max": max(b["gas_kohm_max"] for b in buckets),
            "avg": _wavg("gas_kohm_avg"),
            "last": latest["gas_kohm"] if latest else buckets[-1]["gas_kohm_avg"],
            "aqi_avg": _wavg("aqi_avg"),
            "label": latest["air_quality_label"] if latest else "Unknown",
        },
        "comfort_label": latest["comfort_label"] if latest else "Unknown",
        "latest": latest,
    }


def fetch_bme680_history(
    hours: Optional[Union[int, float]] = None,
    preset: Optional[str] = None,
    db_path: Optional[Union[str, Path]] = None,
    remote_host: str = DEFAULT_REMOTE_HOST,
    remote_db_path: str = DEFAULT_REMOTE_DB_PATH,
    now: Optional[datetime] = None,
    table_name: str = "measurements",
) -> Dict[str, Any]:
    """
    Fetch downsampled BME680 telemetry history from local SQLite or remote Pi Zero 2W.

    Args:
        hours: Requested window in hours (1 to 168, default 12).
        preset: Optional semantic preset ('last_night', 'today', 'last_24h', 'last_7d').
        db_path: Optional local SQLite path. If it exists, queries locally; otherwise uses SSH.
        remote_host: SSH target for the Pi Zero 2W node.
        remote_db_path: Remote SQLite file path on the Pi Zero 2W node.
        now: Optional reference timestamp for deterministic testing.
        table_name: SQLite table name (default 'measurements').

    Returns:
        Dictionary with window metadata, downsampled buckets, latest reading, and summary stats.
    """
    window = resolve_time_window(hours=hours, preset=preset, now=now)
    local_candidate = Path(db_path) if db_path is not None else DEFAULT_LOCAL_DB_PATH

    if local_candidate.exists() and local_candidate.is_file() and local_candidate.stat().st_size > 0:
        source = f"local:{local_candidate}"
        buckets, latest = _query_local_sqlite(
            db_path=local_candidate,
            start_utc_str=window["start_utc_str"],
            end_utc_str=window["end_utc_str"],
            bucket_sec=window["bucket_seconds"],
            table_name=table_name,
        )
    else:
        source = f"ssh:{remote_host}:{remote_db_path}"
        buckets, latest = _query_remote_sqlite(
            remote_host=remote_host,
            remote_db_path=remote_db_path,
            start_utc_str=window["start_utc_str"],
            end_utc_str=window["end_utc_str"],
            bucket_sec=window["bucket_seconds"],
            table_name=table_name,
        )

    stats = _compute_summary_stats(buckets, latest)
    return {
        "source": source,
        "window": window,
        "buckets": buckets,
        "latest": latest,
        "stats": stats,
    }


def _load_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    """Load DejaVuSans or DejaVuSans-Bold at the requested pixel size with safe fallback."""
    font_name = "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"
    candidates = [
        f"/usr/share/fonts/truetype/dejavu/{font_name}",
        font_name,
    ]
    for path in candidates:
        try:
            return ImageFont.truetype(path, size=size)
        except OSError:
            continue
    return ImageFont.load_default()


def _draw_dashed_hline(
    draw: ImageDraw.ImageDraw,
    x0: int,
    x1: int,
    y: int,
    color: Tuple[int, int, int, int],
    dash_len: int = 12,
    gap_len: int = 8,
    width: int = 2,
) -> None:
    """Draw a horizontal dashed line across a chart panel."""
    cur_x = x0
    while cur_x < x1:
        end_x = min(x1, cur_x + dash_len)
        draw.line([(cur_x, y), (end_x, y)], fill=color, width=width)
        cur_x += dash_len + gap_len


def _render_metric_panel(
    canvas: Image.Image,
    draw: ImageDraw.ImageDraw,
    box: Tuple[int, int, int, int],
    buckets: List[Dict[str, Any]],
    spec: Dict[str, Any],
    window: Dict[str, Any],
    show_x_labels: bool = True,
    detailed: bool = True,
) -> None:
    """Render a single metric time-series panel onto the supersampled RGBA canvas."""
    x0, y0, x1, y1 = box
    font_title = _load_font(30 if detailed else 26, bold=True)
    font_stat = _load_font(24 if detailed else 22, bold=False)
    font_axis = _load_font(22, bold=False)
    font_badge = _load_font(22, bold=True)

    # Panel background & border
    draw.rounded_rectangle(
        [x0, y0, x1, y1],
        radius=18,
        fill=PANEL_BG_COLOR,
        outline=PANEL_BORDER_COLOR,
        width=3,
    )

    # Panel header
    title_text = f"{spec['title']} ({spec['unit']})"
    draw.text((x0 + 28, y0 + 18), title_text, fill=spec["line_color"], font=font_title)

    avg_key = spec["avg_key"]
    min_key = spec["min_key"]
    max_key = spec["max_key"]
    unit = spec["unit"]
    decimals = spec["decimals"]

    if not buckets:
        empty_font = _load_font(32, bold=True)
        draw.text(
            ((x0 + x1) // 2 - 220, (y0 + y1) // 2 - 20),
            "No telemetry readings in selected window",
            fill=TEXT_MUTED,
            font=empty_font,
        )
        return

    vals_avg = [b[avg_key] for b in buckets]
    vals_min = [b[min_key] for b in buckets]
    vals_max = [b[max_key] for b in buckets]

    overall_min = min(vals_min)
    overall_max = max(vals_max)
    overall_avg = sum(vals_avg) / len(vals_avg)
    last_val = vals_avg[-1]

    stats_summary = (
        f"MIN: {overall_min:.{decimals}f}{unit}   "
        f"AVG: {overall_avg:.{decimals}f}{unit}   "
        f"MAX: {overall_max:.{decimals}f}{unit}   "
        f"LAST: {last_val:.{decimals}f}{unit}"
    )
    stat_bbox = draw.textbbox((0, 0), stats_summary, font=font_stat)
    stat_w = stat_bbox[2] - stat_bbox[0]
    draw.text((x1 - stat_w - 28, y0 + 22), stats_summary, fill=TEXT_PRIMARY, font=font_stat)

    # Inner plot area
    plot_x0 = x0 + 115
    plot_x1 = x1 - 45
    plot_y0 = y0 + (78 if detailed else 68)
    plot_y1 = y1 - (64 if show_x_labels else 28)
    plot_w = max(10, plot_x1 - plot_x0)
    plot_h = max(10, plot_y1 - plot_y0)

    # Compute Y-axis bounds with padding
    y_min = overall_min
    y_max = overall_max
    if detailed:
        for t_val, _ in spec.get("thresholds", []):
            if abs(t_val - overall_avg) <= max(15.0, (overall_max - overall_min) * 2.5):
                y_min = min(y_min, t_val)
                y_max = max(y_max, t_val)

    span = y_max - y_min
    if span < 1e-6:
        span = max(1.0, abs(y_max) * 0.05)
        y_min -= span / 2.0
        y_max += span / 2.0
    else:
        pad = span * 0.15
        y_min -= pad
        y_max += pad

    def _val_to_y(val: float) -> int:
        norm = (val - y_min) / (y_max - y_min)
        norm = max(0.0, min(1.0, norm))
        return int(round(plot_y1 - norm * plot_h))

    t_start = buckets[0]["bucket_epoch"]
    t_end = buckets[-1]["bucket_epoch"]
    t_span = max(1, t_end - t_start)

    def _epoch_to_x(epoch: int, idx: int) -> int:
        if len(buckets) == 1:
            return plot_x0 + plot_w // 2
        if t_end == t_start:
            return int(round(plot_x0 + (idx / max(1, len(buckets) - 1)) * plot_w))
        norm = (epoch - t_start) / t_span
        norm = max(0.0, min(1.0, norm))
        return int(round(plot_x0 + norm * plot_w))

    # Horizontal gridlines & Y-axis labels
    num_y_ticks = 5 if detailed else 4
    for i in range(num_y_ticks + 1):
        frac = i / num_y_ticks
        val = y_min + frac * (y_max - y_min)
        py = int(round(plot_y1 - frac * plot_h))
        draw.line([(plot_x0, py), (plot_x1, py)], fill=GRID_COLOR, width=2)
        label = f"{val:.{decimals}f}"
        lb = draw.textbbox((0, 0), label, font=font_axis)
        lw = lb[2] - lb[0]
        lh = lb[3] - lb[1]
        draw.text((plot_x0 - lw - 14, py - lh // 2 - 2), label, fill=TEXT_MUTED, font=font_axis)

    # Vertical gridlines & X-axis time ticks
    num_x_ticks = min(6, max(2, len(buckets)))
    for i in range(num_x_ticks):
        frac = i / max(1, num_x_ticks - 1)
        px = int(round(plot_x0 + frac * plot_w))
        draw.line([(px, plot_y0), (px, plot_y1)], fill=GRID_COLOR, width=2)
        if show_x_labels:
            tick_epoch = int(round(t_start + frac * (t_end - t_start)))
            tick_dt = datetime.fromtimestamp(tick_epoch, tz=timezone.utc).astimezone(
                window["end_local"].tzinfo
            )
            if window["hours"] > 36:
                t_label = tick_dt.strftime("%m-%d %H:%M")
            else:
                t_label = tick_dt.strftime("%H:%M")
            tb = draw.textbbox((0, 0), t_label, font=font_axis)
            tw = tb[2] - tb[0]
            draw.text((px - tw // 2, plot_y1 + 14), t_label, fill=TEXT_MUTED, font=font_axis)

    # Comfort / reference threshold lines
    for t_val, t_label in spec.get("thresholds", []):
        if y_min <= t_val <= y_max:
            ty = _val_to_y(t_val)
            _draw_dashed_hline(draw, plot_x0, plot_x1, ty, spec["ref_color"], width=2)
            if detailed:
                draw.text((plot_x0 + 12, ty - 26), t_label, fill=spec["ref_color"], font=font_axis)

    # Compute pixel coordinates
    pts_avg = [(_epoch_to_x(b["bucket_epoch"], i), _val_to_y(b[avg_key])) for i, b in enumerate(buckets)]
    pts_min = [(_epoch_to_x(b["bucket_epoch"], i), _val_to_y(b[min_key])) for i, b in enumerate(buckets)]
    pts_max = [(_epoch_to_x(b["bucket_epoch"], i), _val_to_y(b[max_key])) for i, b in enumerate(buckets)]

    # Shaded min-max band via alpha overlay
    if len(buckets) >= 2:
        overlay = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
        ov_draw = ImageDraw.Draw(overlay)
        polygon_pts = pts_max + list(reversed(pts_min))
        ov_draw.polygon(polygon_pts, fill=spec["band_color"])
        canvas.alpha_composite(overlay)

    # Re-bind draw after alpha_composite
    draw = ImageDraw.Draw(canvas)

    # Draw average line
    if len(pts_avg) >= 2:
        draw.line(pts_avg, fill=spec["line_color"], width=6 if detailed else 5, joint="curve")

    # Draw point markers if bucket count is modest
    if len(pts_avg) <= 60:
        r = 6 if detailed else 5
        for px, py in pts_avg:
            draw.ellipse([px - r, py - r, px + r, py + r], fill=spec["line_color"])

    # Callout badges for MIN, MAX, and LAST on single-metric detailed charts
    if detailed and buckets:
        min_idx = min(range(len(buckets)), key=lambda i: buckets[i][min_key])
        max_idx = max(range(len(buckets)), key=lambda i: buckets[i][max_key])
        last_idx = len(buckets) - 1

        callouts = [
            ("MIN", pts_min[min_idx], buckets[min_idx][min_key], (56, 189, 248, 255)),
            ("MAX", pts_max[max_idx], buckets[max_idx][max_key], (255, 107, 107, 255)),
            ("LAST", pts_avg[last_idx], buckets[last_idx][avg_key], spec["line_color"]),
        ]
        for label_prefix, (cx, cy), val, color in callouts:
            draw.ellipse([cx - 9, cy - 9, cx + 9, cy + 9], fill=color, outline=BG_COLOR, width=3)
            badge_text = f"{label_prefix}: {val:.{decimals}f}{unit}"
            bb = draw.textbbox((0, 0), badge_text, font=font_badge)
            bw = bb[2] - bb[0] + 20
            bh = bb[3] - bb[1] + 12
            bx = min(max(plot_x0 + 6, cx - bw // 2), plot_x1 - bw - 6)
            by = cy - bh - 14 if cy - bh - 14 > plot_y0 else cy + 14
            draw.rounded_rectangle(
                [bx, by, bx + bw, by + bh],
                radius=8,
                fill=(26, 26, 46, 235),
                outline=color,
                width=2,
            )
            draw.text((bx + 10, by + 4), badge_text, fill=TEXT_PRIMARY, font=font_badge)


def generate_bme680_chart(
    history: Dict[str, Any],
    metric: str = "all",
    output_path: Optional[Union[str, Path]] = None,
) -> bytes:
    """
    Render a high-resolution dark-theme PNG chart from downsampled BME680 history.

    Uses 2x supersampling and LANCZOS downscaling for crisp typography and smooth curves.

    Args:
        history: Output dictionary from `fetch_bme680_history`.
        metric: One of ('all', 'temperature', 'humidity', 'air_quality', 'pressure').
        output_path: Optional file path where the PNG will also be written.

    Returns:
        PNG image bytes.
    """
    metric_norm = (metric or "all").strip().lower()
    if metric_norm not in VALID_METRICS:
        raise ValueError(f"Unsupported metric '{metric}'. Must be one of {VALID_METRICS}.")

    target_w = 1200
    target_h = 900 if metric_norm == "all" else 750
    scale = 2
    width = target_w * scale
    height = target_h * scale

    canvas = Image.new("RGBA", (width, height), BG_COLOR)
    draw = ImageDraw.Draw(canvas)

    font_header = _load_font(42, bold=True)
    font_sub = _load_font(24, bold=False)
    font_pill = _load_font(24, bold=True)

    window = history["window"]
    buckets = history["buckets"]
    stats = history["stats"]
    latest = history.get("latest")

    # Header section
    header_title = (
        "BME680 Indoor Telemetry Overview"
        if metric_norm == "all"
        else f"BME680 Telemetry — {METRIC_SPECS[metric_norm]['title']}"
    )
    draw.text((48, 36), header_title, fill=TEXT_PRIMARY, font=font_header)

    bucket_min = window["bucket_seconds"] // 60
    start_str = window["start_local"].strftime("%Y-%m-%d %H:%M")
    end_str = window["end_local"].strftime("%Y-%m-%d %H:%M")
    subtitle = (
        f"Window: {window['window_label']} ({start_str} to {end_str})  •  "
        f"Resolution: {bucket_min}m buckets ({stats['bucket_count']} pts / {stats['total_samples']} raw samples)"
    )
    draw.text((48, 94), subtitle, fill=TEXT_MUTED, font=font_sub)

    # Current reading status badge in top-right
    if latest:
        status_text = (
            f"NOW: {latest['temperature_c']:.1f}°C | {latest['humidity_rh']:.0f}%RH | "
            f"{latest['gas_kohm']:.0f}kΩ ({latest['air_quality_label']}) | {latest['comfort_label']}"
        )
        sb = draw.textbbox((0, 0), status_text, font=font_pill)
        sw = sb[2] - sb[0] + 36
        sh = sb[3] - sb[1] + 22
        sx = width - sw - 48
        sy = 42
        draw.rounded_rectangle(
            [sx, sy, sx + sw, sy + sh],
            radius=14,
            fill=PANEL_BG_COLOR,
            outline=(16, 185, 129, 255),
            width=3,
        )
        draw.text((sx + 18, sy + 9), status_text, fill=TEXT_PRIMARY, font=font_pill)

    # Render panel(s)
    top_margin = 148
    bottom_margin = 36
    left_margin = 48
    right_margin = width - 48

    if metric_norm == "all":
        panel_metrics = ["temperature", "humidity", "air_quality"]
        gap = 28
        avail_h = height - top_margin - bottom_margin - gap * (len(panel_metrics) - 1)
        panel_h = avail_h // len(panel_metrics)

        for idx, m_key in enumerate(panel_metrics):
            py0 = top_margin + idx * (panel_h + gap)
            py1 = py0 + panel_h
            is_last = idx == len(panel_metrics) - 1
            _render_metric_panel(
                canvas=canvas,
                draw=ImageDraw.Draw(canvas),
                box=(left_margin, py0, right_margin, py1),
                buckets=buckets,
                spec=METRIC_SPECS[m_key],
                window=window,
                show_x_labels=is_last,
                detailed=False,
            )
    else:
        _render_metric_panel(
            canvas=canvas,
            draw=ImageDraw.Draw(canvas),
            box=(left_margin, top_margin, right_margin, height - bottom_margin),
            buckets=buckets,
            spec=METRIC_SPECS[metric_norm],
            window=window,
            show_x_labels=True,
            detailed=True,
        )

    # Downscale with LANCZOS anti-aliasing
    final_img = canvas.convert("RGB").resize((target_w, target_h), Image.Resampling.LANCZOS)

    buf = io.BytesIO()
    final_img.save(buf, format="PNG", optimize=True)
    png_bytes = buf.getvalue()

    if output_path is not None:
        out_p = Path(output_path)
        out_p.parent.mkdir(parents=True, exist_ok=True)
        out_p.write_bytes(png_bytes)

    return png_bytes
