#!/usr/bin/env python3
import bme680
import time
import csv
import os
import json
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
sensor.set_gas_heater_temperature(320)
sensor.set_gas_heater_duration(150)
sensor.select_gas_heater_profile(0)  # Enable the gas heater

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

# Reference values for typical clean air (50kΩ - 200kΩ)
TYPICAL_CLEAN_AIR_MIN = 50000  # 50 kΩ
TYPICAL_CLEAN_AIR_MAX = 200000 # 200 kΩ

# Baseline persistence file
BASELINE_FILE = "gas_baseline.json"

current_calibration_start_time = time.time() # Start time of the current burn-in/baseline phase
time_baseline_established = 0.0              # Timestamp when gas_baseline was last successfully computed
gas_baseline = None
baseline_gas_readings = []

def load_baseline():
    """Load baseline from file if it exists and is recent enough."""
    global gas_baseline, time_baseline_established
    
    if os.path.exists(BASELINE_FILE):
        try:
            with open(BASELINE_FILE, 'r') as f:
                data = json.load(f)
                saved_baseline = data.get('baseline')
                saved_timestamp = data.get('timestamp')
                
                if saved_baseline and saved_timestamp:
                    # Check if baseline is not too old (less than 24 hours)
                    age_hours = (time.time() - saved_timestamp) / 3600
                    if age_hours < 24:
                        gas_baseline = saved_baseline
                        time_baseline_established = saved_timestamp
                        print(f"Loaded baseline from file: {gas_baseline:.2f} Ohms")
                        print(f"Baseline age: {age_hours:.1f} hours")
                        
                        # Validate against typical clean air range
                        if gas_baseline < TYPICAL_CLEAN_AIR_MIN:
                            print(f"⚠️  WARNING: Baseline ({gas_baseline:.0f} Ω) is below typical clean air range ({TYPICAL_CLEAN_AIR_MIN/1000:.0f}kΩ)")
                            print("   Your baseline environment may have been contaminated.")
                        elif gas_baseline > TYPICAL_CLEAN_AIR_MAX:
                            print(f"✓ Baseline is in good range for clean air")
                        
                        return True
                    else:
                        print(f"Baseline file is too old ({age_hours:.1f} hours). Will recalibrate.")
                        
        except (json.JSONDecodeError, IOError) as e:
            print(f"Error loading baseline file: {e}")
    
    return False

def save_baseline():
    """Save current baseline to file."""
    if gas_baseline is not None:
        try:
            data = {
                'baseline': gas_baseline,
                'timestamp': time_baseline_established,
                'timestamp_readable': datetime.fromtimestamp(time_baseline_established).strftime('%Y-%m-%d %H:%M:%S')
            }
            with open(BASELINE_FILE, 'w') as f:
                json.dump(data, f, indent=2)
            print(f"Baseline saved to {BASELINE_FILE}")
        except IOError as e:
            print(f"Error saving baseline file: {e}")

# Try to load existing baseline
baseline_loaded = load_baseline()
if baseline_loaded:
    # Skip burn-in and baseline sampling if we loaded a valid baseline
    current_calibration_start_time = time.time() - (BURN_IN_DURATION_S + BASELINE_SAMPLING_DURATION_S)

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

CSV_FILENAME = "measures.csv"

# Check if the CSV file needs a header
write_header = not os.path.exists(CSV_FILENAME) or os.path.getsize(CSV_FILENAME) == 0

# Open CSV file in append mode
# newline='' is important to prevent extra blank rows on Windows
csv_file = open(CSV_FILENAME, 'a', newline='')
csv_writer = csv.writer(csv_file)

if write_header:
    # Headers with units included for easy dashboard integration
    header = [
        'timestamp',
        'temperature_c',
        'humidity_rh', 
        'pressure_hpa',
        'gas_resistance_ohms',
        'air_quality_index',
        'air_quality_label'
    ]
    csv_writer.writerow(header)
    csv_file.flush() # Ensure the header is written immediately
    print(f"Created new CSV file: {CSV_FILENAME} with headers")

print("\n" + "="*60)
print("CALIBRATION TIPS FOR BEST RESULTS:")
print("="*60)
print("• Position sensor in CLEAN AIR environment during burn-in")
print("• Open windows or place sensor outdoors for baseline")
print("• Avoid smoke, cooking fumes, or chemicals nearby")
print("• Clean air baseline: 50kΩ - 200kΩ is typical")
print("="*60 + "\n")

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
            print("⚠️  IMPORTANT: Ensure sensor is in CLEAN AIR for accurate baseline!")
            current_calibration_start_time = current_time # Reset for new burn-in
            gas_baseline = None
            baseline_gas_readings = []
            time_baseline_established = 0.0 # Mark that baseline needs re-establishment
            print("Starting new burn-in and baseline sampling phase...")

        if sensor.get_sensor_data():
            elapsed_time_current_phase = current_time - current_calibration_start_time

            # Prepare data for console output
            output = '{0:.2f} C, {1:.2f} %RH, {2:.2f} hPa'.format(
                sensor.data.temperature,
                sensor.data.humidity,
                sensor.data.pressure)

            gas_resistance_str_console = "Heating gas sensor..."
            gas_resistance_val_csv = None  # Will be numeric or None
            air_quality_index = None  # Numeric index for analysis
            air_quality_score_str = "Calibrating..." # Default AQ score

            if sensor.data.heat_stable:
                # Gas resistance takes time to stabilize after turning on the heater
                current_gas_resistance = sensor.data.gas_resistance
                gas_resistance_str_console = '{0:.2f} Gas Ohms ({1:.1f} kΩ)'.format(
                    current_gas_resistance, 
                    current_gas_resistance / 1000
                )
                gas_resistance_val_csv = current_gas_resistance  # Keep as numeric

                if elapsed_time_current_phase < BURN_IN_DURATION_S:
                    remaining = BURN_IN_DURATION_S - elapsed_time_current_phase
                    air_quality_score_str = f"Burn-in ({int(remaining)}s)"
                    air_quality_index = 0  # Calibrating
                elif elapsed_time_current_phase < BURN_IN_DURATION_S + BASELINE_SAMPLING_DURATION_S:
                    baseline_gas_readings.append(current_gas_resistance)
                    samples_collected = len(baseline_gas_readings)
                    air_quality_score_str = f"Baseline ({samples_collected})"
                    air_quality_index = 0  # Calibrating
                else:
                    if gas_baseline is None: # Calculate baseline if not already done in this calibration phase
                        if baseline_gas_readings:
                            gas_baseline = sum(baseline_gas_readings) / len(baseline_gas_readings)
                            time_baseline_established = current_time
                            timestamp_baseline_str = datetime.fromtimestamp(time_baseline_established).strftime('%Y-%m-%d %H:%M:%S')
                            print(f"\n{'='*60}")
                            print(f"✓ Gas baseline established: {gas_baseline:.2f} Ohms ({gas_baseline/1000:.1f} kΩ)")
                            print(f"  Timestamp: {timestamp_baseline_str}")
                            
                            # Validate baseline against typical clean air values
                            if gas_baseline < TYPICAL_CLEAN_AIR_MIN:
                                print(f"  ⚠️  WARNING: Baseline is LOW ({gas_baseline/1000:.1f} kΩ)")
                                print(f"     Typical clean air: {TYPICAL_CLEAN_AIR_MIN/1000:.0f}-{TYPICAL_CLEAN_AIR_MAX/1000:.0f} kΩ")
                                print(f"     Your environment may be contaminated!")
                                print(f"     Consider recalibrating in cleaner air.")
                            elif gas_baseline > TYPICAL_CLEAN_AIR_MAX:
                                print(f"  ✓ Excellent! Baseline indicates very clean air")
                            else:
                                print(f"  ✓ Baseline is within typical clean air range")
                            
                            print(f"{'='*60}\n")
                            
                            # Save baseline to file
                            save_baseline()
                            
                            baseline_gas_readings = [] # Clear after use
                        else:
                            # This case means no stable readings were collected during baseline period
                            air_quality_score_str = "Baseline Fail"
                            air_quality_index = 0

                    if gas_baseline is not None:
                        ratio = current_gas_resistance / gas_baseline
                        if ratio > GOOD_AIR_THRESHOLD_RATIO:
                            air_quality_score_str = "Good"
                            air_quality_index = 3  # Good = 3
                        elif ratio < POOR_AIR_THRESHOLD_RATIO:
                            air_quality_score_str = "Poor"
                            air_quality_index = 1  # Poor = 1
                        else:
                            air_quality_score_str = "Moderate"
                            air_quality_index = 2  # Moderate = 2
                    elif air_quality_score_str != "Baseline Fail": # If not already failed
                        air_quality_score_str = "Need Baseline"
                        air_quality_index = 0

            else: # Not heat_stable
                if elapsed_time_current_phase < BURN_IN_DURATION_S:
                     air_quality_score_str = "Burn-in (Gas)"
                     air_quality_index = 0
                else:
                     air_quality_score_str = "Gas Heating"
                     air_quality_index = 0

            output += f', {gas_resistance_str_console}, AQ: {air_quality_score_str}'
            print(output)
            
            # Prepare data for the CSV file - Keep numeric values as numbers
            timestamp_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            csv_row = [
                timestamp_str,
                round(sensor.data.temperature, 2),
                round(sensor.data.humidity, 2),
                round(sensor.data.pressure, 2),
                round(gas_resistance_val_csv, 2) if gas_resistance_val_csv is not None else None,
                air_quality_index,
                air_quality_score_str
            ]
            csv_writer.writerow(csv_row)
            csv_file.flush() # Save data to disk after each write

            # Update OLED display if available
            if oled_device and oled_font:
                with canvas(oled_device) as draw:
                    # Draw title in the yellow section
                    title_x = 0
                    title_y = (OLED_YELLOW_SECTION_HEIGHT - oled_line_height) // 2
                    if title_y < 0: title_y = 0
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
                    
                    # Display Air Quality Status
                    aq_display_text = f"AQ: {air_quality_score_str}"
                    # Add gas resistance in kOhms if the value is valid and we have an AQI score
                    if gas_resistance_val_csv is not None and air_quality_index is not None and air_quality_index > 0:
                        # Using 'k' as a shorthand for kOhms to save space
                        aq_display_text += f" ({gas_resistance_val_csv / 1000:.1f}k)"

                    draw.text((0, y_pos), aq_display_text, font=oled_font, fill="white")

        time.sleep(1) # Wait 1 second before the next reading
        
except KeyboardInterrupt:
    print("\nSensor reading stopped.")
finally:
    if 'csv_file' in locals() and csv_file and not csv_file.closed:
        csv_file.close()
        print(f"CSV file '{CSV_FILENAME}' closed.")