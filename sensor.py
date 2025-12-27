#!/usr/bin/env python3
"""
BME680 Environmental Sensor Monitor

Professional air quality monitoring system with:
- Automatic calibration and baseline management
- OLED display support
- CSV data logging
- Configurable settings via YAML

Author: BME680 Monitor Project
Version: 2.0.0
"""

import time
import logging
import sys
import os
from pathlib import Path

# Add src directory to path for imports
sys.path.insert(0, str(Path(__file__).parent / "src"))

from bme680_monitor import (
    Config,
    SensorManager,
    AirQualityCalculator,
    OLEDDisplay,
    DataLogger
)


def setup_logging(config: Config) -> None:
    """
    Setup logging configuration.

    Args:
        config: Configuration object
    """
    # Create logs directory if needed
    log_dir = Path(config.log_filename).parent
    log_dir.mkdir(parents=True, exist_ok=True)

    # Create logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, config.log_level))

    # Create formatter
    formatter = logging.Formatter(
        config.log_format,
        datefmt=config.log_date_format
    )

    # Console handler
    if config.log_console_enabled:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)

    # File handler with rotation
    if config.log_file_enabled:
        from logging.handlers import RotatingFileHandler
        file_handler = RotatingFileHandler(
            config.log_filename,
            maxBytes=config.log_max_bytes,
            backupCount=config.log_backup_count
        )
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)


def print_calibration_tips(config: Config) -> None:
    """Print calibration tips for the user."""
    logger = logging.getLogger(__name__)

    logger.info("=" * 60)
    logger.info("CALIBRATION TIPS FOR BEST RESULTS:")
    logger.info("=" * 60)
    logger.info("• Position sensor in CLEAN AIR environment during burn-in")
    logger.info("• Open windows or place sensor outdoors for baseline")
    logger.info("• Avoid smoke, cooking fumes, or chemicals nearby")
    logger.info(f"• Clean air baseline: {config.clean_air_min/1000:.0f}kΩ - {config.clean_air_max/1000:.0f}kΩ is typical")
    logger.info("=" * 60)


def main():
    """Main execution function."""
    # Load configuration from config directory
    config_path = Path(__file__).parent / "config" / "config.yaml"

    try:
        config = Config(str(config_path))
    except FileNotFoundError as e:
        print(f"Error: {e}")
        print(f"\nPlease create a config.yaml file at: {config_path}")
        sys.exit(1)

    # Setup logging
    setup_logging(config)
    logger = logging.getLogger(__name__)

    logger.info("=" * 60)
    logger.info("BME680 Environmental Sensor Monitor v2.0.0")
    logger.info("=" * 60)

    # Initialize sensor
    try:
        sensor_manager = SensorManager(
            i2c_address=config.sensor_i2c_address,
            gas_heater_temperature=config.gas_heater_temperature,
            gas_heater_duration=config.gas_heater_duration
        )
    except RuntimeError:
        logger.error("Failed to initialize sensor. Exiting.")
        sys.exit(1)

    # Initialize air quality calculator
    air_quality = AirQualityCalculator(
        baseline_file=config.baseline_file,
        burn_in_duration=config.burn_in_duration,
        baseline_sampling_duration=config.baseline_sampling_duration,
        recalibration_interval=config.recalibration_interval,
        good_threshold=config.good_air_threshold,
        poor_threshold=config.poor_air_threshold,
        clean_air_min=config.clean_air_min,
        clean_air_max=config.clean_air_max,
        baseline_max_age_hours=config.baseline_max_age
    )

    # Initialize OLED display
    display = OLEDDisplay(
        enabled=config.oled_enabled,
        i2c_address=config.oled_i2c_address,
        width=config.oled_width,
        height=config.oled_height,
        yellow_section_height=config.oled_yellow_section_height,
        font_name=config.oled_font_name,
        font_size=config.oled_font_size,
        line_height=config.oled_line_height,
        title=config.oled_title
    )

    # Initialize data logger
    data_logger = DataLogger(
        filename=config.csv_filename,
        flush_immediately=config.flush_immediately
    )

    # Print calibration tips
    print_calibration_tips(config)

    logger.info(f"Reading data every {config.sampling_interval} second(s). Press Ctrl+C to exit.")
    logger.info(f"Data will be saved to '{config.csv_filename}'")

    # Main monitoring loop
    try:
        while True:
            # Read sensor data
            sensor_data = sensor_manager.read()

            if sensor_data is None:
                logger.warning("Failed to read sensor data")
                time.sleep(config.sampling_interval)
                continue

            # Format basic sensor output
            output = (
                f"{sensor_data.temperature:.2f} C, "
                f"{sensor_data.humidity:.2f} %RH, "
                f"{sensor_data.pressure:.2f} hPa"
            )

            # Initialize air quality variables
            gas_resistance_str = "Heating gas sensor..."
            gas_resistance_val = None
            air_quality_index = None
            air_quality_label = "Calibrating..."

            # Process gas resistance if available
            if sensor_data.heat_stable and sensor_data.gas_resistance is not None:
                gas_resistance_val = sensor_data.gas_resistance
                gas_resistance_str = (
                    f"{gas_resistance_val:.2f} Gas Ohms "
                    f"({gas_resistance_val / 1000:.1f} kΩ)"
                )

                # Update air quality calculation
                air_quality_index, air_quality_label = air_quality.update(
                    gas_resistance=gas_resistance_val,
                    heat_stable=sensor_data.heat_stable
                )
            else:
                # Gas sensor not stable yet
                air_quality_index, air_quality_label = air_quality.update(
                    gas_resistance=0,  # Dummy value
                    heat_stable=False
                )

            # Log to console
            output += f", {gas_resistance_str}, AQ: {air_quality_label}"
            logger.info(output)

            # Log to CSV
            data_logger.log_reading(
                temperature=sensor_data.temperature,
                humidity=sensor_data.humidity,
                pressure=sensor_data.pressure,
                gas_resistance=gas_resistance_val,
                air_quality_index=air_quality_index,
                air_quality_label=air_quality_label
            )

            # Update OLED display
            if display.is_available():
                display.update(
                    temperature=sensor_data.temperature,
                    humidity=sensor_data.humidity,
                    pressure=sensor_data.pressure,
                    air_quality_label=air_quality_label,
                    gas_resistance=gas_resistance_val,
                    air_quality_index=air_quality_index
                )

            # Check if CSV needs rotation (optional)
            data_logger.rotate_if_needed(max_size_mb=100)

            # Wait before next reading
            time.sleep(config.sampling_interval)

    except KeyboardInterrupt:
        logger.info("\nSensor reading stopped by user.")

    except Exception as e:
        logger.exception(f"Unexpected error: {e}")
        sys.exit(1)

    finally:
        # Cleanup
        if display.is_available():
            display.clear()
        logger.info("Shutdown complete.")


if __name__ == "__main__":
    main()
