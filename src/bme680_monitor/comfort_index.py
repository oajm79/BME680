"""Comfort index and environmental interpretation module."""

import logging
from typing import Tuple, Optional
from enum import IntEnum


logger = logging.getLogger(__name__)


class HumidityLevel(IntEnum):
    """Humidity comfort levels."""
    VERY_DRY = 0
    DRY = 1
    OPTIMAL = 2
    HUMID = 3
    VERY_HUMID = 4


class PressureLevel(IntEnum):
    """Atmospheric pressure levels."""
    VERY_LOW = 0
    LOW = 1
    NORMAL = 2
    HIGH = 3
    VERY_HIGH = 4


class ComfortLevel(IntEnum):
    """Overall comfort levels."""
    VERY_UNCOMFORTABLE = 0
    UNCOMFORTABLE = 1
    ACCEPTABLE = 2
    COMFORTABLE = 3
    VERY_COMFORTABLE = 4


class ComfortIndexCalculator:
    """
    Calculate comfort indices and environmental interpretations.

    Provides human-readable interpretations of:
    - Humidity levels (with health implications)
    - Atmospheric pressure (with weather predictions)
    - Temperature-humidity comfort index
    """

    def __init__(
        self,
        # Humidity thresholds (%)
        humidity_very_dry: float = 30,
        humidity_dry: float = 40,
        humidity_optimal_min: float = 40,
        humidity_optimal_max: float = 60,
        humidity_humid: float = 70,

        # Pressure thresholds (hPa)
        pressure_very_low: float = 980,
        pressure_low: float = 1000,
        pressure_normal_min: float = 1000,
        pressure_normal_max: float = 1025,
        pressure_high: float = 1035,

        # Comfort temperature range (°C)
        comfort_temp_min: float = 18,
        comfort_temp_max: float = 24
    ):
        """
        Initialize comfort index calculator.

        Args:
            humidity_very_dry: Below this is very dry (%)
            humidity_dry: Below this is dry (%)
            humidity_optimal_min: Start of optimal range (%)
            humidity_optimal_max: End of optimal range (%)
            humidity_humid: Above this is humid (%)
            pressure_very_low: Below this is very low (hPa)
            pressure_low: Below this is low (hPa)
            pressure_normal_min: Start of normal pressure (hPa)
            pressure_normal_max: End of normal pressure (hPa)
            pressure_high: Above this is high (hPa)
            comfort_temp_min: Minimum comfortable temperature (°C)
            comfort_temp_max: Maximum comfortable temperature (°C)
        """
        self.humidity_very_dry = humidity_very_dry
        self.humidity_dry = humidity_dry
        self.humidity_optimal_min = humidity_optimal_min
        self.humidity_optimal_max = humidity_optimal_max
        self.humidity_humid = humidity_humid

        self.pressure_very_low = pressure_very_low
        self.pressure_low = pressure_low
        self.pressure_normal_min = pressure_normal_min
        self.pressure_normal_max = pressure_normal_max
        self.pressure_high = pressure_high

        self.comfort_temp_min = comfort_temp_min
        self.comfort_temp_max = comfort_temp_max

    def assess_humidity(self, humidity: float) -> Tuple[HumidityLevel, str, str]:
        """
        Assess humidity level with interpretation and recommendation.

        Args:
            humidity: Relative humidity in %

        Returns:
            Tuple of (level, label, recommendation)
        """
        if humidity < self.humidity_very_dry:
            return (
                HumidityLevel.VERY_DRY,
                f"MUY SECO {humidity:.0f}%",
                "⚠️ Aire muy seco. Usar humidificador. Riesgo: irritación respiratoria, piel seca."
            )
        elif humidity < self.humidity_dry:
            return (
                HumidityLevel.DRY,
                f"Seco {humidity:.0f}%",
                "💧 Aire seco. Considerar humidificador. Beber más agua."
            )
        elif humidity <= self.humidity_optimal_max:
            return (
                HumidityLevel.OPTIMAL,
                f"Ideal {humidity:.0f}%",
                "✓ Humedad ideal para confort y salud."
            )
        elif humidity <= self.humidity_humid:
            return (
                HumidityLevel.HUMID,
                f"Húmedo {humidity:.0f}%",
                "💨 Aire húmedo. Ventilar. Puede haber moho en espacios cerrados."
            )
        else:
            return (
                HumidityLevel.VERY_HUMID,
                f"MUY HÚMEDO {humidity:.0f}%",
                "⚠️ Aire muy húmedo. Usar deshumidificador. Riesgo: moho, ácaros."
            )

    def assess_pressure(self, pressure: float) -> Tuple[PressureLevel, str, str]:
        """
        Assess atmospheric pressure with weather prediction.

        Args:
            pressure: Atmospheric pressure in hPa

        Returns:
            Tuple of (level, label, weather_forecast)
        """
        if pressure < self.pressure_very_low:
            return (
                PressureLevel.VERY_LOW,
                f"⛈️  TORMENTA ({pressure:.0f})",
                "🌧️ Tormenta inminente. Probabilidad alta de lluvia fuerte."
            )
        elif pressure < self.pressure_low:
            return (
                PressureLevel.LOW,
                f"☁️  Lluvioso ({pressure:.0f})",
                "☁️ Tiempo inestable. Posible lluvia o nubosidad."
            )
        elif pressure <= self.pressure_normal_max:
            return (
                PressureLevel.NORMAL,
                f"⛅ Normal ({pressure:.0f})",
                "⛅ Tiempo estable. Condiciones normales."
            )
        elif pressure <= self.pressure_high:
            return (
                PressureLevel.HIGH,
                f"☀️  Despejado ({pressure:.0f})",
                "☀️ Buen tiempo. Cielo despejado probable."
            )
        else:
            return (
                PressureLevel.VERY_HIGH,
                f"🌤️  Seco ({pressure:.0f})",
                "🌤️ Anticiclón fuerte. Tiempo muy estable y seco."
            )

    def assess_temperature(self, temperature: float) -> Tuple[str, str]:
        """
        Assess temperature comfort.

        Args:
            temperature: Temperature in °C

        Returns:
            Tuple of (label, recommendation)
        """
        if temperature < 10:
            return (f"🥶 MUY FRÍO {temperature:.1f}°C", "🥶 Temperatura muy baja. Calentar ambiente.")
        elif temperature < self.comfort_temp_min:
            return (f"❄️  Frío {temperature:.1f}°C", "❄️ Temperatura baja. Aumentar calefacción.")
        elif temperature <= self.comfort_temp_max:
            return (f"✓ Perfecto {temperature:.1f}°C", "✓ Temperatura ideal.")
        elif temperature <= 28:
            return (f"🌡️  Cálido {temperature:.1f}°C", "🌡️ Temperatura elevada. Ventilar o usar ventilador.")
        else:
            return (f"🔥 MUY CALIENTE {temperature:.1f}°C", "🔥 Temperatura muy alta. Usar aire acondicionado.")

    def calculate_heat_index(self, temperature: float, humidity: float) -> Tuple[float, str]:
        """
        Calculate heat index (sensación térmica) using simplified formula.

        Heat index combines temperature and humidity to estimate how hot it feels.

        Args:
            temperature: Temperature in °C
            humidity: Relative humidity in %

        Returns:
            Tuple of (heat_index_celsius, interpretation)
        """
        # Simplified heat index formula (Steadman's formula approximation)
        # Only meaningful for T > 27°C
        if temperature < 27:
            return (temperature, "No aplica (temperatura baja)")

        # Convert to Fahrenheit for calculation
        T_f = temperature * 9/5 + 32
        RH = humidity

        # Rothfusz regression (simplified)
        HI_f = -42.379 + 2.04901523 * T_f + 10.14333127 * RH
        HI_f -= 0.22475541 * T_f * RH - 0.00683783 * T_f * T_f
        HI_f -= 0.05481717 * RH * RH + 0.00122874 * T_f * T_f * RH
        HI_f += 0.00085282 * T_f * RH * RH - 0.00000199 * T_f * T_f * RH * RH

        # Convert back to Celsius
        HI_c = (HI_f - 32) * 5/9

        # Interpretation
        if HI_c < 27:
            level = "Precaución"
        elif HI_c < 32:
            level = "Precaución Extrema"
        elif HI_c < 41:
            level = "Peligro"
        else:
            level = "Peligro Extremo"

        return (HI_c, f"{level} - Sensación: {HI_c:.1f}°C")

    def assess_overall_comfort(
        self,
        temperature: float,
        humidity: float,
        pressure: float
    ) -> Tuple[ComfortLevel, str, str]:
        """
        Assess overall environmental comfort.

        Args:
            temperature: Temperature in °C
            humidity: Relative humidity in %
            pressure: Atmospheric pressure in hPa

        Returns:
            Tuple of (comfort_level, summary, recommendation)
        """
        # Assess each component
        humid_level, _, _ = self.assess_humidity(humidity)
        press_level, _, _ = self.assess_pressure(pressure)

        # Temperature score
        if self.comfort_temp_min <= temperature <= self.comfort_temp_max:
            temp_score = 2  # Good
        elif temperature < 10 or temperature > 30:
            temp_score = 0  # Very bad
        else:
            temp_score = 1  # Acceptable

        # Humidity score
        if humid_level == HumidityLevel.OPTIMAL:
            humid_score = 2
        elif humid_level in (HumidityLevel.DRY, HumidityLevel.HUMID):
            humid_score = 1
        else:
            humid_score = 0

        # Pressure doesn't affect comfort as much, just weather
        press_score = 1 if press_level == PressureLevel.NORMAL else 0

        # Calculate overall comfort
        total_score = temp_score + humid_score + press_score

        if total_score >= 5:
            level = ComfortLevel.VERY_COMFORTABLE
            summary = "Excelente"
            recommendation = "✓ Condiciones ideales. Ambiente muy confortable."
        elif total_score >= 4:
            level = ComfortLevel.COMFORTABLE
            summary = "Bueno"
            recommendation = "✓ Condiciones buenas. Ambiente confortable."
        elif total_score >= 3:
            level = ComfortLevel.ACCEPTABLE
            summary = "Aceptable"
            recommendation = "⚠️ Condiciones aceptables. Pequeñas mejoras posibles."
        elif total_score >= 2:
            level = ComfortLevel.UNCOMFORTABLE
            summary = "Incómodo"
            recommendation = "⚠️ Ambiente incómodo. Ajustar temperatura o humedad."
        else:
            level = ComfortLevel.VERY_UNCOMFORTABLE
            summary = "Muy Incómodo"
            recommendation = "❌ Condiciones muy malas. Intervención necesaria."

        return (level, summary, recommendation)

    def get_comprehensive_report(
        self,
        temperature: float,
        humidity: float,
        pressure: float
    ) -> dict:
        """
        Get comprehensive environmental comfort report.

        Args:
            temperature: Temperature in °C
            humidity: Relative humidity in %
            pressure: Atmospheric pressure in hPa

        Returns:
            Dictionary with all assessments and recommendations
        """
        humid_level, humid_label, humid_rec = self.assess_humidity(humidity)
        press_level, press_label, press_forecast = self.assess_pressure(pressure)
        temp_label, temp_rec = self.assess_temperature(temperature)
        heat_index, heat_interp = self.calculate_heat_index(temperature, humidity)
        comfort_level, comfort_summary, comfort_rec = self.assess_overall_comfort(
            temperature, humidity, pressure
        )

        return {
            'temperature': {
                'value': temperature,
                'label': temp_label,
                'recommendation': temp_rec
            },
            'humidity': {
                'value': humidity,
                'level': humid_level,
                'label': humid_label,
                'recommendation': humid_rec
            },
            'pressure': {
                'value': pressure,
                'level': press_level,
                'label': press_label,
                'forecast': press_forecast
            },
            'heat_index': {
                'value': heat_index,
                'interpretation': heat_interp
            },
            'overall_comfort': {
                'level': comfort_level,
                'summary': comfort_summary,
                'recommendation': comfort_rec
            }
        }
