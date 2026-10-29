#!/home/oajm/projects/BME680/.venv/bin/python
"""
bme680-tools-mcp.py — Stdio JSON-RPC MCP server for on-demand BME680 environmental telemetry charts.

Exposes `get_bme680_telemetry_chart` to OpenClaw so users can request indoor
temperature, humidity, air quality, and atmospheric pressure charts via WhatsApp
with server-side SQLite downsampling and a 7-day (168h) guardrail cap.
"""

import json
import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional

PROJECT_ROOT = Path(__file__).resolve().parent
SRC_DIR = PROJECT_ROOT / "src"
SHARED_SERVICES_DIR = PROJECT_ROOT.parent / "shared-services-lib"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))
if SHARED_SERVICES_DIR.exists() and str(SHARED_SERVICES_DIR) not in sys.path:
    sys.path.insert(0, str(SHARED_SERVICES_DIR))

from bme680_monitor.chart_generator import (
    VALID_METRICS,
    VALID_PRESETS,
    fetch_bme680_history,
    generate_bme680_chart,
)
from shared_services.mcp_throttle import IdempotencyGuard, RateLimiter
from shared_services.openclaw import OpenClawClient, load_env_file

logging.basicConfig(
    filename=PROJECT_ROOT / "mcp_server.log",
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger("bme680-mcp")

# Anti-loop rate limiter and idempotency guard for OpenClaw MCP stdio calls
_limiter = RateLimiter(min_interval_seconds=2.0)
_idempotency = IdempotencyGuard(ttl_seconds=120.0)

TOOLS = [
    {
        "name": "get_bme680_telemetry_chart",
        "description": (
            "Generate and send via WhatsApp a high-resolution dark-theme PNG telemetry chart / graph / plot "
            "for the indoor BME680 environmental sensor (temperature, humidity, air quality / VOC / IAQ, and atmospheric pressure) "
            "and return the statistical summary (min, max, average, current reading, and comfort level). "
            "Genera y envía por WhatsApp un gráfico PNG de temperatura, humedad, calidad del aire y presión del sensor ambiental BME680 "
            "en el hogar (1 a 168 horas, máximo 7 días, o presets 'last_night' para anoche 22:00–08:00, 'today', 'last_24h', 'last_7d')."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "metric": {
                    "type": "string",
                    "enum": list(VALID_METRICS),
                    "description": (
                        "Metric to plot / Métrica a graficar: 'all' (triple synchronized panel of temperature, humidity, and air quality), "
                        "'temperature' (temperatura), 'humidity' (humedad), 'air_quality' (calidad del aire / VOC), or 'pressure' (presión). Default: 'all'."
                    ),
                    "default": "all",
                },
                "hours": {
                    "type": "number",
                    "description": (
                        "Historical time window in hours / Ventana histórica en horas (default: 12, strict max: 168 hours / 7 days). "
                        "Any value > 168 is automatically clamped to 168 hours."
                    ),
                    "default": 12,
                },
                "preset": {
                    "type": "string",
                    "enum": list(VALID_PRESETS),
                    "description": (
                        "Optional time preset / Preset temporal: 'last_night' (anoche / yesterday 22:00 to today 08:00), "
                        "'today' (hoy since 00:00), 'last_24h' (last 24h), or 'last_7d' (last 7 days)."
                    ),
                },
                "send_to_whatsapp": {
                    "type": "boolean",
                    "description": "If True (default), sends the PNG chart image directly to the user's WhatsApp via OpenClaw.",
                    "default": True,
                },
                "recipient": {
                    "type": "string",
                    "description": "Target WhatsApp E.164 phone number (optional; defaults to configured recipient).",
                },
            },
            "additionalProperties": False,
        },
    }
]


def _resolve_whatsapp_recipient(explicit_recipient: Optional[str] = None) -> str:
    """Resolve the target WhatsApp E.164 number from arguments or environment files."""
    if explicit_recipient and explicit_recipient.strip():
        return explicit_recipient.strip()

    for key in ("FINANCE_WHATSAPP_TO", "FINANCE_WHATSAPP_OMAR", "WHATSAPP_TO"):
        val = os.getenv(key)
        if val and val.strip():
            return val.strip()

    env_candidates = [
        PROJECT_ROOT / ".env",
        PROJECT_ROOT.parent / "accounts" / ".env",
        PROJECT_ROOT.parent / "shared-services-lib" / ".env",
        PROJECT_ROOT.parent / "pi-backend" / "credentials" / "notify.env",
    ]
    for env_path in env_candidates:
        env_map = load_env_file(env_path)
        for key in ("FINANCE_WHATSAPP_TO", "FINANCE_WHATSAPP_OMAR", "WHATSAPP_TO"):
            val = env_map.get(key)
            if val and val.strip():
                return val.strip()

    return ""


def _build_whatsapp_caption(history: Dict[str, Any], metric: str) -> str:
    """Format a concise caption for the WhatsApp chart image."""
    window = history["window"]
    stats = history["stats"]
    latest = history.get("latest")
    bucket_min = window["bucket_seconds"] // 60

    lines = [
        f"🌿 *BME680 Indoor Telemetry — {window['window_label']}*",
        f"⏱️ Resolution: {bucket_min}m buckets ({stats['bucket_count']} pts / {stats['total_samples']} samples)",
    ]
    if window.get("clamped"):
        lines.append("⚠️ _Note: Requested window exceeded 7-day maximum and was clamped to 168h._")

    if stats["bucket_count"] > 0:
        t = stats["temperature"]
        h = stats["humidity"]
        aq = stats["air_quality"]
        p = stats["pressure"]
        lines.extend(
            [
                "",
                f"🌡️ *Temp:* Min {t['min']:.1f}°C | Avg {t['avg']:.1f}°C | Max {t['max']:.1f}°C (Now: {t['last']:.1f}°C)",
                f"💧 *Humidity:* Min {h['min']:.0f}% | Avg {h['avg']:.0f}% | Max {h['max']:.0f}% (Now: {h['last']:.0f}%)",
                f"🍃 *Air Quality:* Min {aq['min']:.0f}kΩ | Avg {aq['avg']:.0f}kΩ | Max {aq['max']:.0f}kΩ ({aq['label']})",
                f"🧭 *Pressure:* Min {p['min']:.1f} hPa | Avg {p['avg']:.1f} hPa | Max {p['max']:.1f} hPa",
            ]
        )
        if latest and latest.get("comfort_label"):
            lines.append(f"🛋️ *Comfort:* {latest['comfort_label']}")

    return "\n".join(lines)


def handle_get_bme680_telemetry_chart(
    args: Dict[str, Any],
    db_path: Optional[Path] = None,
) -> str:
    """Fetch downsampled BME680 history, render the PNG chart, and optionally dispatch to WhatsApp."""
    metric = (args.get("metric") or "all").strip().lower()
    hours = args.get("hours")
    preset = args.get("preset")
    send_to_whatsapp = bool(args.get("send_to_whatsapp", True))
    recipient = _resolve_whatsapp_recipient(args.get("recipient"))

    history = fetch_bme680_history(
        hours=hours,
        preset=preset,
        db_path=db_path,
    )
    png_bytes = generate_bme680_chart(history=history, metric=metric)

    window = history["window"]
    stats = history["stats"]
    latest = history.get("latest")
    bucket_min = window["bucket_seconds"] // 60

    wa_status = "Skipped (send_to_whatsapp=False)"
    if send_to_whatsapp:
        if not recipient:
            wa_status = "Not sent (no WhatsApp recipient configured in environment)"
        else:
            caption = _build_whatsapp_caption(history, metric=metric)
            client = OpenClawClient(channel="whatsapp", target=recipient)
            sent = client.send_photo(photo=png_bytes, caption=caption)
            wa_status = f"Sent to {recipient}" if sent else f"Failed to send to {recipient}"

    summary_lines = [
        f"📊 *BME680 Telemetry Report ({window['window_label']})*",
        f"• Metric Mode: `{metric}`",
        f"• Time Window: {window['start_local'].strftime('%Y-%m-%d %H:%M')} to {window['end_local'].strftime('%Y-%m-%d %H:%M')}",
        f"• Downsampling Resolution: {bucket_min}-minute buckets ({window['bucket_seconds']}s) | {stats['bucket_count']} buckets from {stats['total_samples']} raw readings",
        f"• 7-Day Guardrail Clamped: {'Yes (clamped to 168h max)' if window['clamped'] else 'No'}",
        f"• Data Source: `{history['source']}`",
        f"• WhatsApp Chart Delivery: {wa_status} ({len(png_bytes):,} bytes PNG)",
    ]

    if stats["bucket_count"] > 0:
        t = stats["temperature"]
        h = stats["humidity"]
        aq = stats["air_quality"]
        p = stats["pressure"]
        summary_lines.extend(
            [
                "",
                "📈 *Statistical Summary:*",
                f"• Temperature: Min {t['min']:.2f}°C | Max {t['max']:.2f}°C | Avg {t['avg']:.2f}°C | Current {t['last']:.2f}°C",
                f"• Humidity: Min {h['min']:.1f}%RH | Max {h['max']:.1f}%RH | Avg {h['avg']:.1f}%RH | Current {h['last']:.1f}%RH",
                f"• Air Quality (Gas): Min {aq['min']:.1f} kΩ | Max {aq['max']:.1f} kΩ | Avg {aq['avg']:.1f} kΩ | Current {aq['last']:.1f} kΩ ({aq['label']})",
                f"• Pressure: Min {p['min']:.1f} hPa | Max {p['max']:.1f} hPa | Avg {p['avg']:.1f} hPa | Current {p['last']:.1f} hPa",
                f"• Comfort State: {stats.get('comfort_label', 'Unknown')}"
                + (f" (as of {latest['timestamp']} UTC)" if latest and latest.get("timestamp") else ""),
            ]
        )
    else:
        summary_lines.append("\n⚠️ No sensor readings were found in the requested time window.")

    return "\n".join(summary_lines)


def execute_tool(name: str, arguments: Dict[str, Any]) -> str:
    """Dispatch an MCP tool call by name."""
    if name == "get_bme680_telemetry_chart":
        return handle_get_bme680_telemetry_chart(arguments)
    raise ValueError(f"Unknown tool: {name}")


def main() -> None:
    """Run the stdio JSON-RPC 2.0 MCP loop."""
    log.info("bme680-tools-mcp server starting via stdio...")
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except json.JSONDecodeError:
            continue

        method = req.get("method")
        req_id = req.get("id")
        params = req.get("params", {})

        if method == "initialize":
            resp = {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {}},
                    "serverInfo": {"name": "bme680-tools", "version": "1.0.0"},
                },
            }
            sys.stdout.write(json.dumps(resp) + "\n")
            sys.stdout.flush()

        elif method == "notifications/initialized":
            log.info("Client initialized notification received")

        elif method == "tools/list":
            resp = {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {"tools": TOOLS},
            }
            sys.stdout.write(json.dumps(resp) + "\n")
            sys.stdout.flush()

        elif method == "tools/call":
            t_name = params.get("name")
            t_args = params.get("arguments", {})
            try:
                _limiter.throttle()
                is_cached, cached_output = _idempotency.check(t_name, t_args)
                if is_cached:
                    text_res = str(cached_output)
                else:
                    text_res = execute_tool(t_name, t_args)
                    _idempotency.record(t_name, t_args, text_res)
                resp = {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "content": [{"type": "text", "text": text_res}],
                        "isError": False,
                    },
                }
            except Exception as exc:
                log.exception("Tool execution failed: %s", exc)
                resp = {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "content": [
                            {"type": "text", "text": f"Error executing {t_name}: {str(exc)}"}
                        ],
                        "isError": True,
                    },
                }
            sys.stdout.write(json.dumps(resp) + "\n")
            sys.stdout.flush()

        elif method == "ping":
            resp = {"jsonrpc": "2.0", "id": req_id, "result": {}}
            sys.stdout.write(json.dumps(resp) + "\n")
            sys.stdout.flush()

        else:
            if req_id is not None:
                resp = {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "error": {"code": -32601, "message": f"Method not found: {method}"},
                }
                sys.stdout.write(json.dumps(resp) + "\n")
                sys.stdout.flush()


if __name__ == "__main__":
    main()
