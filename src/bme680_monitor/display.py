"""OLED display management for BME680 sensor readings."""

import logging
import time
from typing import Optional
from luma.core.interface.serial import i2c
from luma.core.render import canvas
from luma.oled.device import ssd1306
from PIL import ImageFont


logger = logging.getLogger(__name__)


class OLEDDisplay:
    """Manages OLED display output for sensor readings."""

    def __init__(
        self,
        enabled: bool = True,
        i2c_port: int = 1,
        i2c_address: int = 0x3C,
        width: int = 128,
        height: int = 64,
        yellow_section_height: int = 16,
        font_name: str = "DejaVuSans.ttf",
        font_size: int = 10,
        line_height: int = 12,
        title: str = "BME680 Readings"
    ):
        """
        Initialize OLED display.

        Args:
            enabled: Whether OLED display is enabled
            i2c_port: I2C port number (typically 1 on Raspberry Pi)
            i2c_address: I2C address of OLED display
            width: Display width in pixels
            height: Display height in pixels
            yellow_section_height: Height of yellow section (for two-color OLEDs)
            font_name: Font file name
            font_size: Font size in points
            line_height: Line height in pixels
            title: Display title text
        """
        self.enabled = enabled
        self.i2c_port = i2c_port
        self.i2c_address = i2c_address
        self.width = width
        self.height = height
        self.yellow_section_height = yellow_section_height
        self.font_size = font_size
        self.line_height = line_height
        self.title = title

        self.device: Optional[ssd1306] = None
        self.font: Optional[ImageFont.FreeTypeFont] = None

        # Display alternation state
        self._last_switch_time = time.time()
        self._show_comfort_view = False
        self._switch_interval = 3.0  # Switch every 3 seconds

        if self.enabled:
            self._initialize()

    def _initialize(self) -> None:
        """Initialize OLED device and font."""
        try:
            serial = i2c(port=self.i2c_port, address=self.i2c_address)
            self.device = ssd1306(serial)
            logger.info("OLED display initialized successfully")

            # Try to load TrueType font
            try:
                self.font = ImageFont.truetype(
                    "DejaVuSans.ttf",
                    self.font_size
                )
                logger.info("Using DejaVuSans.ttf font for OLED")
            except IOError:
                self.font = ImageFont.load_default()
                self.line_height = 10  # Adjust for default font
                logger.warning("DejaVuSans.ttf not found, using default PIL font")

        except Exception as e:
            logger.error(f"Error initializing OLED display: {e}")
            logger.info("OLED display will not be used. Check I2C connection and address.")
            self.device = None
            self.enabled = False

    def update(
        self,
        temperature: float,
        humidity: float,
        pressure: float,
        air_quality_label: str,
        gas_resistance: Optional[float] = None,
        air_quality_index: Optional[int] = None,
        comfort_report: Optional[dict] = None
    ) -> None:
        """
        Update OLED display with current sensor readings.

        Args:
            temperature: Temperature in Celsius
            humidity: Relative humidity in %
            pressure: Atmospheric pressure in hPa
            air_quality_label: Air quality label (e.g., "Good", "Poor")
            gas_resistance: Gas resistance in Ohms (optional)
            air_quality_index: Air quality index 0-3 (optional)
            comfort_report: Comfort interpretations from ComfortIndexCalculator (optional)
        """
        if not self.enabled or not self.device or not self.font:
            return

        # Check if it's time to switch views
        current_time = time.time()
        if current_time - self._last_switch_time >= self._switch_interval:
            self._show_comfort_view = not self._show_comfort_view
            self._last_switch_time = current_time

        try:
            with canvas(self.device) as draw:
                # Draw title in the yellow section
                title_x = 0
                title_y = max(0, (self.yellow_section_height - self.line_height) // 2)

                if self._show_comfort_view and comfort_report:
                    draw.text((title_x, title_y), "Confort", font=self.font, fill="white")
                else:
                    draw.text((title_x, title_y), self.title, font=self.font, fill="white")

                # Start drawing sensor data below the yellow section
                y_pos = self.yellow_section_height

                # Alternate between normal view and comfort view
                if self._show_comfort_view and comfort_report:
                    self._draw_comfort_view(draw, y_pos, comfort_report)
                elif comfort_report:
                    self._draw_normal_view(draw, y_pos, temperature, humidity, pressure,
                                          air_quality_label, gas_resistance, air_quality_index,
                                          comfort_report)
                else:
                    self._draw_fallback_view(draw, y_pos, temperature, humidity, pressure,
                                           air_quality_label, gas_resistance, air_quality_index)

        except Exception as e:
            logger.error(f"Error updating OLED display: {e}")

    def _draw_normal_view(
        self,
        draw,
        y_pos: int,
        temperature: float,
        humidity: float,
        pressure: float,
        air_quality_label: str,
        gas_resistance: Optional[float],
        air_quality_index: Optional[int],
        comfort_report: dict
    ) -> None:
        """Draw normal sensor readings view."""
        # Temperature with interpretation (with T: prefix)
        temp_label = self._get_temp_short_label(temperature, comfort_report)
        draw.text((0, y_pos), f"T: {temp_label}", font=self.font, fill="white")
        y_pos += self.line_height

        # Humidity with interpretation (with H: prefix)
        humid_label = self._get_humid_short_label(humidity, comfort_report)
        draw.text((0, y_pos), f"H: {humid_label}", font=self.font, fill="white")
        y_pos += self.line_height

        # Pressure with weather (with P: prefix)
        press_label = self._get_pressure_short_label(pressure, comfort_report)
        draw.text((0, y_pos), f"P: {press_label}", font=self.font, fill="white")
        y_pos += self.line_height

        # Air Quality
        aq_display_text = f"Aire: {air_quality_label}"
        if (gas_resistance is not None and
            air_quality_index is not None and
            air_quality_index > 0):
            aq_display_text += f" ({gas_resistance / 1000:.0f}k)"
        draw.text((0, y_pos), aq_display_text, font=self.font, fill="white")

    def _draw_comfort_view(self, draw, y_pos: int, comfort_report: dict) -> None:
        """Draw comfort assessment view."""
        # Overall comfort summary
        comfort_summary = comfort_report['overall_comfort']['summary']
        draw.text((0, y_pos), f"Estado: {comfort_summary}", font=self.font, fill="white")
        y_pos += self.line_height
        y_pos += 2  # Small spacing

        # Temperature recommendation (shortened)
        temp_rec = comfort_report['temperature']['recommendation']
        temp_short = self._shorten_recommendation(temp_rec)
        draw.text((0, y_pos), temp_short, font=self.font, fill="white")
        y_pos += self.line_height

        # Humidity recommendation (shortened)
        humid_rec = comfort_report['humidity']['recommendation']
        humid_short = self._shorten_recommendation(humid_rec)
        draw.text((0, y_pos), humid_short, font=self.font, fill="white")
        y_pos += self.line_height

        # Pressure forecast (shortened)
        press_forecast = comfort_report['pressure']['forecast']
        press_short = self._shorten_recommendation(press_forecast)
        draw.text((0, y_pos), press_short, font=self.font, fill="white")

    def _draw_fallback_view(
        self,
        draw,
        y_pos: int,
        temperature: float,
        humidity: float,
        pressure: float,
        air_quality_label: str,
        gas_resistance: Optional[float],
        air_quality_index: Optional[int]
    ) -> None:
        """Draw fallback technical view when no comfort report available."""
        # Temperature
        text_line = f"T: {temperature:.1f} C"
        draw.text((0, y_pos), text_line, font=self.font, fill="white")
        y_pos += self.line_height

        # Humidity
        text_line = f"H: {humidity:.1f} %RH"
        draw.text((0, y_pos), text_line, font=self.font, fill="white")
        y_pos += self.line_height

        # Pressure
        text_line = f"P: {pressure:.1f} hPa"
        draw.text((0, y_pos), text_line, font=self.font, fill="white")
        y_pos += self.line_height

        # Air Quality
        aq_display_text = f"Aire: {air_quality_label}"
        if (gas_resistance is not None and
            air_quality_index is not None and
            air_quality_index > 0):
            aq_display_text += f" ({gas_resistance / 1000:.0f}k)"
        draw.text((0, y_pos), aq_display_text, font=self.font, fill="white")

    def _shorten_recommendation(self, recommendation: str) -> str:
        """Shorten recommendation text to fit OLED display."""
        # Remove emoji and leading symbols
        text = recommendation
        for emoji in ['✓', '⚠️', '❌', '🥶', '❄️', '🌡️', '🔥', '💧', '💨', '☁️', '⛅', '☀️', '🌧️', '🌤️']:
            text = text.replace(emoji, '').strip()

        # Truncate if too long (max ~21 chars for 128px width)
        if len(text) > 21:
            text = text[:18] + "..."

        return text

    def _get_temp_short_label(self, temperature: float, comfort_report: dict) -> str:
        """Get short temperature label for OLED display."""
        if temperature < 10:
            return f"Muy Frio {temperature:.1f}C"
        elif temperature < 18:
            return f"Frio {temperature:.1f}C"
        elif temperature <= 24:
            return f"Perfecto {temperature:.1f}C"
        elif temperature <= 28:
            return f"Calido {temperature:.1f}C"
        else:
            return f"Muy Calor {temperature:.1f}C"

    def _get_humid_short_label(self, humidity: float, comfort_report: dict) -> str:
        """Get short humidity label for OLED display."""
        if humidity < 30:
            return f"Muy Seco {humidity:.0f}%"
        elif humidity < 40:
            return f"Seco {humidity:.0f}%"
        elif humidity <= 60:
            return f"Ideal {humidity:.0f}%"
        elif humidity <= 70:
            return f"Humedo {humidity:.0f}%"
        else:
            return f"Muy Humedo {humidity:.0f}%"

    def _get_pressure_short_label(self, pressure: float, comfort_report: dict) -> str:
        """Get short pressure label for OLED display."""
        if pressure < 980:
            return f"Tormenta {pressure:.0f}"
        elif pressure < 1000:
            return f"Lluvioso {pressure:.0f}"
        elif pressure <= 1025:
            return f"Normal {pressure:.0f}"
        elif pressure <= 1035:
            return f"Despejado {pressure:.0f}"
        else:
            return f"Muy Seco {pressure:.0f}"

    def clear(self) -> None:
        """Clear the OLED display."""
        if self.enabled and self.device:
            try:
                self.device.clear()
            except Exception as e:
                logger.error(f"Error clearing OLED display: {e}")

    def show_message(self, message: str, line: int = 0) -> None:
        """
        Show a simple message on the OLED display.

        Args:
            message: Message text to display
            line: Line number (0-based) to display message on
        """
        if not self.enabled or not self.device or not self.font:
            return

        try:
            with canvas(self.device) as draw:
                y_pos = line * self.line_height
                draw.text((0, y_pos), message, font=self.font, fill="white")
        except Exception as e:
            logger.error(f"Error showing message on OLED: {e}")

    def is_available(self) -> bool:
        """
        Check if OLED display is available and working.

        Returns:
            True if display is available, False otherwise
        """
        return self.enabled and self.device is not None

    def __del__(self):
        """Cleanup OLED display on deletion."""
        if self.device:
            try:
                self.clear()
            except:
                pass
