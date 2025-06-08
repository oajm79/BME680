#!/usr/bin/env python3
import bme680
import time
import csv
import os
from datetime import datetime

# OLED display imports
from luma.core.interface.serial import i2c
from luma.core.render import canvas
from luma.oled.device import ssd1306
from PIL import ImageFont

# Try to create an instance of the sensor.
# If your sensor has I2C address 0x76, use: sensor = bme680.BME680(0x76)
try:
    sensor = bme680.BME680(0x77)
except RuntimeError as e:
    print(f"Error initializing sensor: {e}")
    print("Ensure SDA and SCL connections are correct")
    print("and that I2C is enabled on the Raspberry Pi (sudo raspi-config -> Interfacing Options -> I2C).")
    exit()

print("BME680 sensor detected. Reading data...")

# Configure oversampling and filters if necessary (optional, default values usually work)
# sensor.set_temperature_oversample(bme680.OS_2X)
# sensor.set_humidity_oversample(bme680.OS_2X)
# sensor.set_pressure_oversample(bme680.OS_2X)
# sensor.set_filter(bme680.FILTER_SIZE_2)

# Configure the gas heater (necessary for gas reading)
# Adjust temperature and time according to sensor recommendations if you have them
sensor.set_gas_heater_temperature(320)
sensor.set_gas_heater_duration(150)
#sensor.select_gas_heater(bme680.GASSENSOR_ENABLE)

# OLED Display Setup
oled_device = None
oled_font = None
oled_line_height = 10  # Default for PIL's load_default()
OLED_YELLOW_SECTION_HEIGHT = 16 # Typical height for the yellow section on 128x64 two-color OLEDs
OLED_TITLE_TEXT = "BME680 Readings"

# Air Quality Score Configuration
BURN_IN_DURATION_S = 300      # 5 minutes for sensor burn-in
BASELINE_SAMPLING_DURATION_S = 300 # 5 minutes to sample for baseline gas resistance
GOOD_AIR_THRESHOLD_RATIO = 1.35   # Current gas > baseline * 1.35 -> Good
POOR_AIR_THRESHOLD_RATIO = 0.70   # Current gas < baseline * 0.70 -> Poor
                                # Otherwise -> Moderate
RECALIBRATION_INTERVAL_S = 4 * 3600 # Recalibrate every 4 hours (0 to disable)

current_calibration_start_time = time.time() # Start time of the current burn-in/baseline phase
time_baseline_established = 0.0              # Timestamp when gas_baseline was last successfully computed
gas_baseline = None
baseline_gas_readings = []

# OLED Ticker display state for the last line
OLED_ANIMATION_DURATION = 1.5  # seconds for text to scroll in
OLED_STATIC_DURATION = 5.0     # seconds for text to remain static

oled_ticker_info_idx = 0       # Current info to display (0: AQ, 1: Baseline, 2: Calib Time)
oled_ticker_phase = 'ANIMATING_IN'  # Current phase: 'ANIMATING_IN' or 'STATIC'
oled_ticker_phase_start_time = 0.0 # Timestamp when the current phase started
oled_ticker_current_text = ""      # The actual string being displayed/animated
oled_ticker_needs_text_update = True # Flag to update text at the start of an animation
oled_display_width_cache = 128     # Cache for OLED width, default 128 (will be updated if oled_device exists)


try:
    # Common I2C address for 0.96" OLED is 0x3C
    # Raspberry Pi I2C port is typically 1
    serial = i2c(port=1, address=0x3C)
    oled_device = ssd1306(serial) # Auto-detects 128x64 or 128x32 for ssd1306
    print("OLED display initialized.")
    try:
        oled_font = ImageFont.truetype("DejaVuSans.ttf", 10)
        oled_line_height = 12 # Approximate height for DejaVuSans 10pt
        print("Using DejaVuSans.ttf font for OLED.")
    except IOError:
        oled_font = ImageFont.load_default()
        print("DejaVuSans.ttf not found, using default PIL font for OLED.")
except Exception as e:
    print(f"Error initializing OLED display: {e}")
    print("OLED display will not be used. Check I2C connection and address (0x3C?).")
    oled_device = None # Ensure it's None if setup fails

# Initialize ticker start time and display width cache after OLED setup
if oled_device:
    oled_display_width_cache = oled_device.width
oled_ticker_phase_start_time = time.time() # Start the first animation immediately


CSV_FILENAME = "measures.csv"

# Check if the CSV file needs a header
write_header = not os.path.exists(CSV_FILENAME) or os.path.getsize(CSV_FILENAME) == 0

# Open CSV file in append mode
# newline='' is important to prevent extra blank rows on Windows
csv_file = open(CSV_FILENAME, 'a', newline='')
csv_writer = csv.writer(csv_file)

if write_header:
    header = ['Timestamp', 'Temperature (C)', 'Humidity (%RH)', 'Pressure (hPa)', 'Gas Resistance (Ohms)', 'Air Quality']
    csv_writer.writerow(header)
    csv_file.flush() # Ensure the header is written immediately

print("Reading data every second. Press Ctrl+C to exit.")
print(f"Data will be saved to '{CSV_FILENAME}'")

try:
    while True:
        current_time = time.time()

        # --- Recalibration Trigger ---
        if gas_baseline is not None and \
           RECALIBRATION_INTERVAL_S > 0 and \
           (current_time - time_baseline_established > RECALIBRATION_INTERVAL_S):
            print(f"\n--- Recalibration triggered (interval: {RECALIBRATION_INTERVAL_S // 3600}h) ---")
            current_calibration_start_time = current_time # Reset for new burn-in
            gas_baseline = None
            baseline_gas_readings = []
            time_baseline_established = 0.0 # Mark that baseline needs re-establishment
            print("Starting new burn-in and baseline sampling phase...")

        if sensor.get_sensor_data():
            elapsed_time_current_phase = current_time - current_calibration_start_time

            # Preparar datos para la salida en consola
            output = '{0:.2f} C, {1:.2f} %RH, {2:.2f} hPa'.format(
                sensor.data.temperature,
                sensor.data.humidity,
                sensor.data.pressure)

            gas_resistance_str_console = "Heating gas sensor..."
            gas_resistance_val_csv = "N/A"
            air_quality_score_str = "Calibrating..." # Default AQ score

            if sensor.data.heat_stable:
                # Gas resistance takes time to stabilize after turning on the heater
                gas_resistance_str_console = '{0:.2f} Gas Ohms'.format(sensor.data.gas_resistance)
                gas_resistance_val_csv = '{0:.2f}'.format(sensor.data.gas_resistance)

                current_gas_resistance = sensor.data.gas_resistance

                if elapsed_time_current_phase < BURN_IN_DURATION_S:
                    air_quality_score_str = "Burn-in"
                elif elapsed_time_current_phase < BURN_IN_DURATION_S + BASELINE_SAMPLING_DURATION_S:
                    baseline_gas_readings.append(current_gas_resistance)
                    air_quality_score_str = "Baseline..."
                    # Update OLED to show baseline progress if desired
                    # e.g., "Baseline {len(baseline_gas_readings)}/{int(BASELINE_SAMPLING_DURATION_S / (interval_of_this_loop))}"
                else:
                    if gas_baseline is None: # Calculate baseline if not already done in this calibration phase
                        if baseline_gas_readings:
                            gas_baseline = sum(baseline_gas_readings) / len(baseline_gas_readings)
                            time_baseline_established = current_time
                            timestamp_baseline_str = datetime.fromtimestamp(time_baseline_established).strftime('%Y-%m-%d %H:%M:%S')
                            print(f"Gas baseline established: {gas_baseline:.2f} Ohms at {timestamp_baseline_str}")
                            baseline_gas_readings = [] # Clear after use
                        else:
                            # This case means no stable readings were collected during baseline period
                            air_quality_score_str = "Baseline Fail"
                            # Optionally, could try to re-baseline or use a default

                    if gas_baseline is not None:
                        ratio = current_gas_resistance / gas_baseline
                        if ratio > GOOD_AIR_THRESHOLD_RATIO:
                            air_quality_score_str = "Good"
                        elif ratio < POOR_AIR_THRESHOLD_RATIO:
                            air_quality_score_str = "Poor"
                        else:
                            air_quality_score_str = "Moderate"
                    elif air_quality_score_str != "Baseline Fail": # If not already failed
                        air_quality_score_str = "Need Baseline"

            else: # Not heat_stable
                if elapsed_time_current_phase < BURN_IN_DURATION_S:
                     air_quality_score_str = "Burn-in (Gas)"
                else:
                     air_quality_score_str = "Gas Heating"

            output += f', {gas_resistance_str_console}, AQ: {air_quality_score_str}'
            #print(output) # Un-commented to see console output
            # Prepare data for the CSV file
            # This timestamp is also used for the OLED if needed, or generate a new one
            timestamp_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            csv_row = [
                timestamp_str,
                '{0:.2f}'.format(sensor.data.temperature),
                '{0:.2f}'.format(sensor.data.humidity),
                '{0:.2f}'.format(sensor.data.pressure),
                gas_resistance_val_csv,
                air_quality_score_str
            ]
            csv_writer.writerow(csv_row)
            csv_file.flush() # Save data to disk after each write

            # Update OLED display if available
            if oled_device and oled_font:
                current_time_for_ticker = time.time()

                # Define text provider functions for the ticker
                def get_aq_text():
                    return f"AQ: {air_quality_score_str}"
                def get_baseline_text():
                    return f"Base: {gas_baseline:.0f} Ohms" if gas_baseline is not None else "Base: N/A"
                def get_calib_text():
                    if time_baseline_established > 0:
                        return f"Cal: {datetime.fromtimestamp(time_baseline_established).strftime('%H:%M')}"
                    return "Cal: N/A"
                
                def get_current_gas_resistance_text():
                    if sensor.data.heat_stable and hasattr(sensor.data, 'gas_resistance'):
                        return f"GasNow: {sensor.data.gas_resistance:.0f} Ohms"
                    return "GasNow: Heating" # Or another appropriate message like "GasNow: N/A"

                text_providers = [get_aq_text, get_baseline_text, get_calib_text, get_current_gas_resistance_text]

                with canvas(oled_device) as draw:
                    # Clear screen by drawing a black filled rectangle (handled by canvas context manager)
                    # Or draw.rectangle(oled_device.bounding_box, outline="black", fill="black")

                    # Draw title in the yellow section
                    # For simplicity, left-aligning. Centering would require font metrics.
                    title_x = 0
                    # Try to vertically center the title a bit within the yellow section
                    # This is an approximation, true centering needs font bounding box.
                    title_y = (OLED_YELLOW_SECTION_HEIGHT - oled_line_height) // 2
                    if title_y < 0: title_y = 0 # Ensure it's not negative if font is too large
                    draw.text((title_x, title_y), OLED_TITLE_TEXT, font=oled_font, fill="white")

                    # Start drawing sensor data below the yellow section
                    y_pos = OLED_YELLOW_SECTION_HEIGHT

                    text_line = f"T: {sensor.data.temperature:.1f} C"
                    draw.text((0, y_pos), text_line, font=oled_font, fill="white")
                    y_pos += oled_line_height

                    text_line = f"H: {sensor.data.humidity:.1f} %RH"
                    draw.text((0, y_pos), text_line, font=oled_font, fill="white")
                    y_pos += oled_line_height
                    text_line = f"P: {sensor.data.pressure:.1f} hPa"
                    draw.text((0, y_pos), text_line, font=oled_font, fill="white")
                    y_pos += oled_line_height
                    
                    # --- Ticker Logic for the last line ---
                    elapsed_in_current_phase = current_time_for_ticker - oled_ticker_phase_start_time

                    if oled_ticker_phase == 'STATIC':
                        if elapsed_in_current_phase >= OLED_STATIC_DURATION:
                            # Transition to ANIMATING_IN
                            oled_ticker_phase = 'ANIMATING_IN'
                            oled_ticker_phase_start_time = current_time_for_ticker
                            oled_ticker_info_idx = (oled_ticker_info_idx + 1) % len(text_providers)
                            oled_ticker_needs_text_update = True # Signal to update text

                    elif oled_ticker_phase == 'ANIMATING_IN':
                        if oled_ticker_needs_text_update:
                            oled_ticker_current_text = text_providers[oled_ticker_info_idx]()
                            oled_ticker_needs_text_update = False # Text updated for this animation cycle

                        if elapsed_in_current_phase >= OLED_ANIMATION_DURATION:
                            # Transition to STATIC
                            oled_ticker_phase = 'STATIC'
                            oled_ticker_phase_start_time = current_time_for_ticker
                            # Text remains as is for the static phase

                    # Calculate X position for ticker
                    x_pos_ticker = 0 # Default for STATIC phase or if animation duration is 0
                    if oled_ticker_phase == 'ANIMATING_IN' and OLED_ANIMATION_DURATION > 0:
                        progress = min(1.0, elapsed_in_current_phase / OLED_ANIMATION_DURATION)
                        x_pos_ticker = int(oled_display_width_cache * (1.0 - progress))
                    
                    draw.text((x_pos_ticker, y_pos), oled_ticker_current_text, font=oled_font, fill="white")

        time.sleep(1) # Wait 1 second before the next reading
except KeyboardInterrupt:
    print("\nSensor reading stopped.")
finally:
    if 'csv_file' in locals() and csv_file and not csv_file.closed:
        csv_file.close()
        print(f"CSV file '{CSV_FILENAME}' closed.")
