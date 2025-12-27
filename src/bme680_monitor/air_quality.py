"""Air quality calculation and baseline management."""

import json
import os
import time
import logging
from datetime import datetime
from typing import Optional, List, Tuple
from enum import IntEnum


logger = logging.getLogger(__name__)


class AirQualityLevel(IntEnum):
    """Air quality levels with numeric indices."""
    CALIBRATING = 0
    POOR = 1
    MODERATE = 2
    GOOD = 3


class AirQualityCalculator:
    """
    Manages air quality calculations based on gas resistance baseline.

    Uses a ratio-based algorithm:
    - Good: current_gas / baseline > good_threshold
    - Poor: current_gas / baseline < poor_threshold
    - Moderate: between thresholds
    """

    def __init__(
        self,
        baseline_file: str,
        burn_in_duration: int,
        baseline_sampling_duration: int,
        recalibration_interval: int,
        good_threshold: float,
        poor_threshold: float,
        clean_air_min: int,
        clean_air_max: int,
        baseline_max_age_hours: int = 24,
        excellent_threshold_abs: int = 150000,
        good_threshold_abs: int = 100000,
        moderate_threshold_abs: int = 50000
    ):
        """
        Initialize air quality calculator.

        Args:
            baseline_file: Path to baseline persistence file
            burn_in_duration: Burn-in phase duration in seconds
            baseline_sampling_duration: Baseline sampling duration in seconds
            recalibration_interval: Recalibration interval in seconds (0 = disabled)
            good_threshold: Ratio threshold for good air quality (relative)
            poor_threshold: Ratio threshold for poor air quality (relative)
            clean_air_min: Minimum typical clean air resistance (Ohms)
            clean_air_max: Maximum typical clean air resistance (Ohms)
            baseline_max_age_hours: Maximum baseline age before requiring recalibration
            excellent_threshold_abs: Excellent air threshold in Ohms (absolute)
            good_threshold_abs: Good air threshold in Ohms (absolute)
            moderate_threshold_abs: Moderate air threshold in Ohms (absolute)
        """
        self.baseline_file = baseline_file
        self.burn_in_duration = burn_in_duration
        self.baseline_sampling_duration = baseline_sampling_duration
        self.recalibration_interval = recalibration_interval
        self.good_threshold = good_threshold
        self.poor_threshold = poor_threshold
        self.clean_air_min = clean_air_min
        self.clean_air_max = clean_air_max
        self.baseline_max_age_hours = baseline_max_age_hours

        # Absolute thresholds for hybrid algorithm
        self.excellent_threshold_abs = excellent_threshold_abs
        self.good_threshold_abs = good_threshold_abs
        self.moderate_threshold_abs = moderate_threshold_abs

        self.gas_baseline: Optional[float] = None
        self.time_baseline_established: float = 0.0
        self.current_calibration_start_time: float = time.time()
        self.baseline_gas_readings: List[float] = []

        # Try to load existing baseline
        if self.load_baseline():
            # Skip calibration phases if baseline loaded
            self.current_calibration_start_time = (
                time.time() - (self.burn_in_duration + self.baseline_sampling_duration)
            )

    def load_baseline(self) -> bool:
        """
        Load baseline from file if it exists and is valid.

        Returns:
            True if baseline loaded successfully, False otherwise
        """
        if not os.path.exists(self.baseline_file):
            return False

        try:
            with open(self.baseline_file, 'r') as f:
                data = json.load(f)

            saved_baseline = data.get('baseline')
            saved_timestamp = data.get('timestamp')

            if not saved_baseline or not saved_timestamp:
                return False

            # Check baseline age
            age_hours = (time.time() - saved_timestamp) / 3600
            if age_hours >= self.baseline_max_age_hours:
                logger.warning(
                    f"Baseline file is too old ({age_hours:.1f} hours). Will recalibrate."
                )
                return False

            self.gas_baseline = saved_baseline
            self.time_baseline_established = saved_timestamp

            logger.info(f"Loaded baseline from file: {self.gas_baseline:.2f} Ω")
            logger.info(f"Baseline age: {age_hours:.1f} hours")

            # Validate against typical clean air range
            if self.gas_baseline < self.clean_air_min:
                logger.warning(
                    f"⚠️  WARNING: Baseline ({self.gas_baseline:.0f} Ω) is below "
                    f"typical clean air range ({self.clean_air_min/1000:.0f}kΩ)"
                )
                logger.warning("Your baseline environment may have been contaminated.")
            elif self.gas_baseline > self.clean_air_max:
                logger.info("✓ Baseline indicates very clean air")
            else:
                logger.info("✓ Baseline is within typical clean air range")

            return True

        except (json.JSONDecodeError, IOError) as e:
            logger.error(f"Error loading baseline file: {e}")
            return False

    def save_baseline(self) -> None:
        """Save current baseline to file."""
        if self.gas_baseline is None:
            return

        try:
            data = {
                'baseline': self.gas_baseline,
                'timestamp': self.time_baseline_established,
                'timestamp_readable': datetime.fromtimestamp(
                    self.time_baseline_established
                ).strftime('%Y-%m-%d %H:%M:%S')
            }
            with open(self.baseline_file, 'w') as f:
                json.dump(data, f, indent=2)

            logger.info(f"Baseline saved to {self.baseline_file}")

        except IOError as e:
            logger.error(f"Error saving baseline file: {e}")

    def should_recalibrate(self) -> bool:
        """
        Check if recalibration should be triggered.

        Returns:
            True if recalibration needed, False otherwise
        """
        if self.gas_baseline is None:
            return False

        if self.recalibration_interval <= 0:
            return False

        time_since_baseline = time.time() - self.time_baseline_established
        return time_since_baseline > self.recalibration_interval

    def trigger_recalibration(self) -> None:
        """Trigger a new calibration cycle."""
        logger.info(
            f"Recalibration triggered (interval: {self.recalibration_interval // 3600}h)"
        )
        logger.warning("⚠️  IMPORTANT: Ensure sensor is in CLEAN AIR for accurate baseline!")

        self.current_calibration_start_time = time.time()
        self.gas_baseline = None
        self.baseline_gas_readings = []
        self.time_baseline_established = 0.0

        logger.info("Starting new burn-in and baseline sampling phase...")

    def update(self, gas_resistance: float, heat_stable: bool) -> Tuple[int, str]:
        """
        Update air quality calculation with new gas resistance reading.

        Args:
            gas_resistance: Current gas resistance in Ohms
            heat_stable: Whether the gas sensor heater is stable

        Returns:
            Tuple of (air_quality_index, air_quality_label)
            - air_quality_index: 0=Calibrating, 1=Poor, 2=Moderate, 3=Good
            - air_quality_label: Human-readable label
        """
        current_time = time.time()

        # Check for automatic recalibration
        if self.should_recalibrate():
            self.trigger_recalibration()

        elapsed_time = current_time - self.current_calibration_start_time

        # If gas sensor is not stable, still in heating phase
        if not heat_stable:
            if elapsed_time < self.burn_in_duration:
                return (AirQualityLevel.CALIBRATING, "Burn-in (Gas)")
            else:
                return (AirQualityLevel.CALIBRATING, "Gas Heating")

        # Burn-in phase
        if elapsed_time < self.burn_in_duration:
            remaining = int(self.burn_in_duration - elapsed_time)
            return (AirQualityLevel.CALIBRATING, f"Burn-in ({remaining}s)")

        # Baseline sampling phase
        if elapsed_time < self.burn_in_duration + self.baseline_sampling_duration:
            self.baseline_gas_readings.append(gas_resistance)
            samples = len(self.baseline_gas_readings)
            return (AirQualityLevel.CALIBRATING, f"Baseline ({samples})")

        # Establish baseline if not already done
        if self.gas_baseline is None:
            if not self.baseline_gas_readings:
                return (AirQualityLevel.CALIBRATING, "Baseline Fail")

            self.gas_baseline = sum(self.baseline_gas_readings) / len(self.baseline_gas_readings)
            self.time_baseline_established = current_time
            timestamp_str = datetime.fromtimestamp(
                self.time_baseline_established
            ).strftime('%Y-%m-%d %H:%M:%S')

            logger.info("=" * 60)
            logger.info(
                f"✓ Gas baseline established: {self.gas_baseline:.2f} Ω "
                f"({self.gas_baseline/1000:.1f} kΩ)"
            )
            logger.info(f"  Timestamp: {timestamp_str}")

            # Validate baseline
            if self.gas_baseline < self.clean_air_min:
                logger.warning(f"  ⚠️  WARNING: Baseline is LOW ({self.gas_baseline/1000:.1f} kΩ)")
                logger.warning(
                    f"     Typical clean air: {self.clean_air_min/1000:.0f}-"
                    f"{self.clean_air_max/1000:.0f} kΩ"
                )
                logger.warning("     Your environment may be contaminated!")
                logger.warning("     Consider recalibrating in cleaner air.")
            elif self.gas_baseline > self.clean_air_max:
                logger.info("  ✓ Excellent! Baseline indicates very clean air")
            else:
                logger.info("  ✓ Baseline is within typical clean air range")

            logger.info("=" * 60)

            # Save baseline
            self.save_baseline()
            self.baseline_gas_readings = []

        # Calculate air quality using HYBRID algorithm (absolute + relative)
        if self.gas_baseline is not None:
            # 1. Absolute assessment (based on scientific BME680 ranges)
            absolute_level = self._assess_absolute_quality(gas_resistance)

            # 2. Relative assessment (compared to baseline)
            ratio = gas_resistance / self.gas_baseline
            relative_level = self._assess_relative_quality(ratio)

            # 3. Combine assessments (use worst case for safety)
            final_level = min(absolute_level, relative_level)

            # 4. Return result with label
            return self._level_to_tuple(final_level)

        return (AirQualityLevel.CALIBRATING, "Need Baseline")

    def _assess_absolute_quality(self, gas_resistance: float) -> AirQualityLevel:
        """
        Assess air quality based on absolute gas resistance values.

        Uses configurable thresholds based on BME680 research and empirical data.
        Higher resistance = cleaner air (fewer VOCs and pollutants)

        Args:
            gas_resistance: Current gas resistance in Ohms

        Returns:
            AirQualityLevel based on absolute value
        """
        if gas_resistance > self.excellent_threshold_abs:
            return AirQualityLevel.GOOD
        elif gas_resistance > self.good_threshold_abs:
            return AirQualityLevel.GOOD
        elif gas_resistance > self.moderate_threshold_abs:
            return AirQualityLevel.MODERATE
        else:
            return AirQualityLevel.POOR

    def _assess_relative_quality(self, ratio: float) -> AirQualityLevel:
        """
        Assess air quality based on ratio to baseline.

        Args:
            ratio: current_gas / baseline_gas

        Returns:
            AirQualityLevel based on relative change
        """
        if ratio > self.good_threshold:
            return AirQualityLevel.GOOD
        elif ratio < self.poor_threshold:
            return AirQualityLevel.POOR
        else:
            return AirQualityLevel.MODERATE

    def _level_to_tuple(self, level: AirQualityLevel) -> Tuple[int, str]:
        """
        Convert AirQualityLevel enum to (index, label) tuple.

        Args:
            level: AirQualityLevel enum

        Returns:
            Tuple of (numeric_index, human_readable_label)
        """
        labels = {
            AirQualityLevel.CALIBRATING: "Calibrating",
            AirQualityLevel.POOR: "Poor",
            AirQualityLevel.MODERATE: "Moderate",
            AirQualityLevel.GOOD: "Good"
        }
        return (level, labels[level])

    def get_baseline_info(self) -> Optional[dict]:
        """
        Get current baseline information.

        Returns:
            Dictionary with baseline info or None if no baseline
        """
        if self.gas_baseline is None:
            return None

        return {
            'baseline_ohms': self.gas_baseline,
            'baseline_kohms': self.gas_baseline / 1000,
            'timestamp': self.time_baseline_established,
            'age_hours': (time.time() - self.time_baseline_established) / 3600,
            'is_valid': not self.should_recalibrate()
        }
