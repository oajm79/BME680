"""Telegram notification service for BME680 sensor alerts."""

import logging
import os
import time
from typing import Optional, Dict, Any
from enum import Enum

from shared_services.telegram import TelegramNotifier as _BaseTelegramNotifier

logger = logging.getLogger(__name__)


class AlertType(Enum):
    """Types of alerts that can be sent."""
    AIR_QUALITY_POOR = "air_quality_poor"
    AIR_QUALITY_GOOD = "air_quality_good"
    TEMPERATURE_HIGH = "temperature_high"
    TEMPERATURE_LOW = "temperature_low"
    HUMIDITY_HIGH = "humidity_high"
    HUMIDITY_LOW = "humidity_low"
    COMFORT_POOR = "comfort_poor"
    DAILY_SUMMARY = "daily_summary"
    SYSTEM_STATUS = "system_status"
    CUSTOM = "custom"


class TelegramNotifier(_BaseTelegramNotifier):
    """
    BME680-specific Telegram notifier.

    Extends shared_services.telegram.TelegramNotifier with:
    - Per-alert-type rate limiting
    - Quiet hours
    - State-based alerts with hysteresis (avoids alert flapping)
    - BME680 domain-specific alert methods
    """

    def __init__(
        self,
        bot_token: Optional[str] = None,
        chat_id: Optional[str] = None,
        enabled: bool = True,
        rate_limit_seconds: int = 300,
        quiet_hours_start: Optional[int] = None,
        quiet_hours_end: Optional[int] = None,
        confirmation_readings: int = 5,
    ):
        token = bot_token or os.environ.get('TELEGRAM_BOT_TOKEN', '')
        cid = chat_id or os.environ.get('TELEGRAM_CHAT_ID', '')

        super().__init__(token=token, chat_id=cid)

        self.enabled = enabled and bool(token) and bool(cid)
        self.rate_limit_seconds = rate_limit_seconds
        self.quiet_hours_start = quiet_hours_start
        self.quiet_hours_end = quiet_hours_end
        self.confirmation_readings = confirmation_readings

        self._last_alerts: Dict[str, float] = {}
        self._alert_states: Dict[str, bool] = {
            "air_quality_poor": False,
            "temperature_high": False,
            "temperature_low": False,
            "humidity_high": False,
            "humidity_low": False,
        }
        self._pending_state: Dict[str, Optional[bool]] = {}
        self._pending_count: Dict[str, int] = {}

        if self.enabled:
            logger.info("Telegram notifications enabled")
        else:
            if not token or not cid:
                logger.info("Telegram notifications disabled (no token/chat_id configured)")
            else:
                logger.info("Telegram notifications disabled by configuration")

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _is_quiet_hours(self) -> bool:
        """Check if current time is within quiet hours."""
        if self.quiet_hours_start is None or self.quiet_hours_end is None:
            return False
        current_hour = time.localtime().tm_hour
        if self.quiet_hours_start > self.quiet_hours_end:
            return current_hour >= self.quiet_hours_start or current_hour < self.quiet_hours_end
        return self.quiet_hours_start <= current_hour < self.quiet_hours_end

    def _is_rate_limited(self, alert_type: str) -> bool:
        """Check if alert type is rate limited."""
        last_time = self._last_alerts.get(alert_type, 0)
        return (time.time() - last_time) < self.rate_limit_seconds

    def _update_rate_limit(self, alert_type: str) -> None:
        """Update last alert time for rate limiting."""
        self._last_alerts[alert_type] = time.time()

    def _check_state_transition(self, state_key: str, is_bad: bool) -> Optional[str]:
        """
        Check if there's a confirmed state transition for alert purposes.

        Requires `confirmation_readings` consecutive readings in the new state
        before confirming the transition (hysteresis to avoid alert flapping).

        Returns:
            "entered" if transitioning to bad state,
            "exited" if transitioning to good state,
            None if no transition or not yet confirmed
        """
        previous_state = self._alert_states.get(state_key, False)

        if is_bad == previous_state:
            self._pending_state[state_key] = None
            self._pending_count[state_key] = 0
            return None

        pending = self._pending_state.get(state_key)
        if pending != is_bad:
            self._pending_state[state_key] = is_bad
            self._pending_count[state_key] = 1
        else:
            self._pending_count[state_key] = self._pending_count.get(state_key, 0) + 1

        if self._pending_count[state_key] >= self.confirmation_readings:
            self._alert_states[state_key] = is_bad
            self._pending_state[state_key] = None
            self._pending_count[state_key] = 0
            return "entered" if is_bad else "exited"

        return None

    def _format_outdoor_context(self, weather_data: Optional[Dict[str, Any]]) -> str:
        """Format outdoor weather data for inclusion in alerts."""
        if not weather_data:
            return ""

        location = weather_data.get('location_name', 'Outdoor')
        parts = [f"\n🌍 <b>Outdoor ({location}):</b>"]

        if weather_data.get('temperature') is not None:
            parts.append(f"🌡️ Temperature: {weather_data['temperature']:.1f}°C")
        if weather_data.get('humidity') is not None:
            parts.append(f"💧 Humidity: {weather_data['humidity']}%")
        if weather_data.get('weather_description'):
            parts.append(f"☁️ Conditions: {weather_data['weather_description']}")
        if weather_data.get('aqi') is not None:
            aqi_label = weather_data.get('aqi_label', '')
            parts.append(f"🌬️ Air Quality: {aqi_label} (AQI: {weather_data['aqi']})")

        return "\n".join(parts)

    # ── send_message override ─────────────────────────────────────────────────

    def send_message(
        self,
        message: str,
        alert_type: AlertType = AlertType.CUSTOM,
        parse_mode: str = "HTML",
        disable_notification: bool = False,
        force: bool = False,
    ) -> bool:
        """
        Send a Telegram message with per-type rate limiting and quiet hours.

        Args:
            message:              Message text (HTML supported).
            alert_type:           Used for per-type rate limiting.
            parse_mode:           'HTML' (default) or 'Markdown'.
            disable_notification: Send silently.
            force:                Bypass rate limiting and quiet hours.
        """
        if not self.enabled:
            logger.debug("Telegram notifications disabled, message not sent")
            return False

        if not force:
            if self._is_quiet_hours():
                logger.debug(f"Quiet hours active, skipping {alert_type.value} notification")
                return False
            if self._is_rate_limited(alert_type.value):
                logger.debug(f"Rate limited: {alert_type.value}")
                return False

        success = super().send_message(
            message, parse_mode=parse_mode, disable_notification=disable_notification
        )

        if success:
            self._update_rate_limit(alert_type.value)
            logger.info(f"Telegram notification sent: {alert_type.value}")
        else:
            logger.error(f"Failed to send Telegram notification: {alert_type.value}")

        return success

    # ── Alert methods ─────────────────────────────────────────────────────────

    def check_air_quality_transition(
        self,
        quality_label: str,
        gas_resistance: float,
        temperature: float,
        humidity: float,
        weather_data: Optional[Dict[str, Any]] = None,
    ) -> bool:
        is_poor = quality_label.lower() == "poor"
        transition = self._check_state_transition("air_quality_poor", is_poor)

        if transition is None:
            return False

        if transition == "entered":
            emoji = "🚨"
            status_text = "Air quality has <b>degraded</b>"
            alert_type = AlertType.AIR_QUALITY_POOR
        else:
            emoji = "✅"
            status_text = "Air quality has <b>improved</b>"
            alert_type = AlertType.AIR_QUALITY_GOOD

        outdoor_context = self._format_outdoor_context(weather_data)
        message = f"""
{emoji} <b>Air Quality Alert</b>

{status_text}

<b>Current Status:</b> {quality_label}
<b>Gas Resistance:</b> {gas_resistance/1000:.1f} kΩ

<b>🏠 Indoor Conditions:</b>
🌡️ Temperature: {temperature:.1f}°C
💧 Humidity: {humidity:.0f}%
{outdoor_context}
""".strip()

        return self.send_message(message, alert_type)

    def check_temperature_transition(
        self,
        temperature: float,
        high_threshold: Optional[float],
        low_threshold: Optional[float],
        weather_data: Optional[Dict[str, Any]] = None,
    ) -> bool:
        sent = False
        outdoor_context = self._format_outdoor_context(weather_data)

        if high_threshold is not None:
            is_high = temperature > high_threshold
            transition = self._check_state_transition("temperature_high", is_high)
            if transition == "entered":
                message = f"""
🔥 <b>Temperature Alert</b>

Temperature has <b>exceeded</b> the high threshold

<b>🏠 Indoor:</b> {temperature:.1f}°C
<b>Threshold:</b> {high_threshold:.1f}°C
{outdoor_context}
""".strip()
                sent = self.send_message(message, AlertType.TEMPERATURE_HIGH)
            elif transition == "exited":
                message = f"""
✅ <b>Temperature Alert</b>

Temperature has <b>returned to normal</b>

<b>🏠 Indoor:</b> {temperature:.1f}°C
<b>Threshold:</b> {high_threshold:.1f}°C
{outdoor_context}
""".strip()
                sent = self.send_message(message, AlertType.TEMPERATURE_HIGH)

        if low_threshold is not None:
            is_low = temperature < low_threshold
            transition = self._check_state_transition("temperature_low", is_low)
            if transition == "entered":
                message = f"""
🥶 <b>Temperature Alert</b>

Temperature has <b>dropped below</b> the low threshold

<b>🏠 Indoor:</b> {temperature:.1f}°C
<b>Threshold:</b> {low_threshold:.1f}°C
{outdoor_context}
""".strip()
                sent = self.send_message(message, AlertType.TEMPERATURE_LOW) or sent
            elif transition == "exited":
                message = f"""
✅ <b>Temperature Alert</b>

Temperature has <b>returned to normal</b>

<b>🏠 Indoor:</b> {temperature:.1f}°C
<b>Threshold:</b> {low_threshold:.1f}°C
{outdoor_context}
""".strip()
                sent = self.send_message(message, AlertType.TEMPERATURE_LOW) or sent

        return sent

    def check_humidity_transition(
        self,
        humidity: float,
        high_threshold: Optional[float],
        low_threshold: Optional[float],
        weather_data: Optional[Dict[str, Any]] = None,
    ) -> bool:
        sent = False
        outdoor_context = self._format_outdoor_context(weather_data)

        if high_threshold is not None:
            is_high = humidity > high_threshold
            transition = self._check_state_transition("humidity_high", is_high)
            if transition == "entered":
                message = f"""
💦 <b>Humidity Alert</b>

Humidity has <b>exceeded</b> the high threshold

<b>🏠 Indoor:</b> {humidity:.0f}%
<b>Threshold:</b> {high_threshold:.0f}%
{outdoor_context}
""".strip()
                sent = self.send_message(message, AlertType.HUMIDITY_HIGH)
            elif transition == "exited":
                message = f"""
✅ <b>Humidity Alert</b>

Humidity has <b>returned to normal</b>

<b>🏠 Indoor:</b> {humidity:.0f}%
<b>Threshold:</b> {high_threshold:.0f}%
{outdoor_context}
""".strip()
                sent = self.send_message(message, AlertType.HUMIDITY_HIGH)

        if low_threshold is not None:
            is_low = humidity < low_threshold
            transition = self._check_state_transition("humidity_low", is_low)
            if transition == "entered":
                message = f"""
🏜️ <b>Humidity Alert</b>

Humidity has <b>dropped below</b> the low threshold

<b>🏠 Indoor:</b> {humidity:.0f}%
<b>Threshold:</b> {low_threshold:.0f}%
{outdoor_context}
""".strip()
                sent = self.send_message(message, AlertType.HUMIDITY_LOW) or sent
            elif transition == "exited":
                message = f"""
✅ <b>Humidity Alert</b>

Humidity has <b>returned to normal</b>

<b>🏠 Indoor:</b> {humidity:.0f}%
<b>Threshold:</b> {low_threshold:.0f}%
{outdoor_context}
""".strip()
                sent = self.send_message(message, AlertType.HUMIDITY_LOW) or sent

        return sent

    def send_daily_summary(
        self,
        stats: Dict[str, Any],
        current_conditions: Dict[str, Any],
        weather_data: Optional[Dict[str, Any]] = None,
    ) -> bool:
        message = f"""
📊 <b>Daily Environmental Summary</b>

🏠 <b>INDOOR (24h Summary)</b>
━━━━━━━━━━━━━━━━━━━━━━━

<b>Temperature:</b>
  Min: {stats.get('temp_min', 0):.1f}°C | Max: {stats.get('temp_max', 0):.1f}°C
  Avg: {stats.get('temp_avg', 0):.1f}°C

<b>Humidity:</b>
  Min: {stats.get('humidity_min', 0):.0f}% | Max: {stats.get('humidity_max', 0):.0f}%
  Avg: {stats.get('humidity_avg', 0):.0f}%

<b>Pressure:</b>
  Min: {stats.get('pressure_min', 0):.0f} hPa | Max: {stats.get('pressure_max', 0):.0f} hPa
  Avg: {stats.get('pressure_avg', 0):.0f} hPa
"""
        if weather_data:
            location = weather_data.get('location_name', 'Outdoor')
            message += f"\n🌍 <b>OUTDOOR ({location})</b>\n━━━━━━━━━━━━━━━━━━━━━━━\n"
            if weather_data.get('temperature') is not None:
                message += f"🌡️ Temperature: {weather_data['temperature']:.1f}°C\n"
            if weather_data.get('humidity') is not None:
                message += f"💧 Humidity: {weather_data['humidity']}%\n"
            if weather_data.get('pressure') is not None:
                message += f"📊 Pressure: {weather_data['pressure']:.0f} hPa\n"
            if weather_data.get('weather_description'):
                message += f"☁️ Conditions: {weather_data['weather_description']}\n"
            if weather_data.get('aqi') is not None:
                aqi_label = weather_data.get('aqi_label', '')
                message += f"🌬️ Air Quality: {aqi_label} (AQI: {weather_data['aqi']})\n"
                if weather_data.get('pm2_5') is not None:
                    message += f"  PM2.5: {weather_data['pm2_5']:.1f} µg/m³\n"
                if weather_data.get('pm10') is not None:
                    message += f"  PM10: {weather_data['pm10']:.1f} µg/m³\n"
            if weather_data.get('temperature') is not None and stats.get('temp_avg'):
                temp_diff = stats['temp_avg'] - weather_data['temperature']
                if temp_diff > 0:
                    message += f"\n📈 Indoor is {abs(temp_diff):.1f}°C warmer than outside"
                elif temp_diff < 0:
                    message += f"\n📉 Indoor is {abs(temp_diff):.1f}°C cooler than outside"

        message += f"\n\n📅 <b>Readings:</b> {stats.get('reading_count', 0)}"
        return self.send_message(message.strip(), AlertType.DAILY_SUMMARY, force=True)

    def send_startup_message(self, version: str = "2.2.0") -> bool:
        message = f"""
🚀 <b>BME680 Monitor Started</b>

<b>Version:</b> {version}
<b>Status:</b> Running
<b>Notifications:</b> Enabled
""".strip()
        return self.send_message(message, AlertType.SYSTEM_STATUS, force=True)

    def send_shutdown_message(self, reason: str = "User requested") -> bool:
        message = f"""
⏹️ <b>BME680 Monitor Stopped</b>

<b>Reason:</b> {reason}
""".strip()
        return self.send_message(message, AlertType.SYSTEM_STATUS, force=True)

    def is_configured(self) -> bool:
        """Check if Telegram is properly configured."""
        return bool(self.token and self.chat_id)

    def is_enabled(self) -> bool:
        """Check if Telegram notifications are enabled."""
        return self.enabled
