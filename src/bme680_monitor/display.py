"""OLED display management for BME680 sensor readings."""

import logging
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
        air_quality_index: Optional[int] = None
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
        """
        if not self.enabled or not self.device or not self.font:
            return

        try:
            with canvas(self.device) as draw:
                # Draw title in the yellow section
                title_x = 0
                title_y = max(0, (self.yellow_section_height - self.line_height) // 2)
                draw.text((title_x, title_y), self.title, font=self.font, fill="white")

                # Start drawing sensor data below the yellow section
                y_pos = self.yellow_section_height

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
                aq_display_text = f"AQ: {air_quality_label}"

                # Add gas resistance in kOhms if available
                if (gas_resistance is not None and
                    air_quality_index is not None and
                    air_quality_index > 0):
                    aq_display_text += f" ({gas_resistance / 1000:.1f}k)"

                draw.text((0, y_pos), aq_display_text, font=self.font, fill="white")

        except Exception as e:
            logger.error(f"Error updating OLED display: {e}")

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
