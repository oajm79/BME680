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
    header = ['Timestamp', 'Temperature (C)', 'Humidity (%RH)', 'Pressure (hPa)', 'Gas Resistance (Ohms)']
    csv_writer.writerow(header)
    csv_file.flush() # Ensure the header is written immediately

print("Reading data every second. Press Ctrl+C to exit.")
print(f"Data will be saved to '{CSV_FILENAME}'")

try:
    while True:
        if sensor.get_sensor_data():
            # Preparar datos para la salida en consola
            output = '{0:.2f} C, {1:.2f} %RH, {2:.2f} hPa'.format(
                sensor.data.temperature,
                sensor.data.humidity,
                sensor.data.pressure)

            gas_resistance_str_console = "Heating gas sensor..."
            gas_resistance_str_oled = "Gas: Heating..." # For OLED display
            gas_resistance_val_csv = "N/A"

            if sensor.data.heat_stable:
                # Gas resistance takes time to stabilize after turning on the heater
                gas_resistance_str_console = '{0:.2f} Gas Ohms'.format(sensor.data.gas_resistance)
                gas_resistance_str_oled = 'Gas: {0:.0f} Ohms'.format(sensor.data.gas_resistance) # Integer for OLED
                gas_resistance_val_csv = '{0:.2f}'.format(sensor.data.gas_resistance)
            
            output += f', {gas_resistance_str_console}'
            #print(output)

            # Prepare data for the CSV file
            # This timestamp is also used for the OLED if needed, or generate a new one
            timestamp_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            csv_row = [
                timestamp_str,
                '{0:.2f}'.format(sensor.data.temperature),
                '{0:.2f}'.format(sensor.data.humidity),
                '{0:.2f}'.format(sensor.data.pressure),
                gas_resistance_val_csv
            ]
            csv_writer.writerow(csv_row)
            csv_file.flush() # Save data to disk after each write

            # Update OLED display if available
            if oled_device and oled_font:
                with canvas(oled_device) as draw:
                    # Clear screen by drawing a black filled rectangle (handled by canvas context manager)
                    # Or draw.rectangle(oled_device.bounding_box, outline="black", fill="black")
                    
                    y_pos = 0
                    
                    text_line = f"T: {sensor.data.temperature:.1f} C"
                    draw.text((0, y_pos), text_line, font=oled_font, fill="white")
                    y_pos += oled_line_height

                    text_line = f"H: {sensor.data.humidity:.1f} %RH"
                    draw.text((0, y_pos), text_line, font=oled_font, fill="white")
                    y_pos += oled_line_height

                    text_line = f"P: {sensor.data.pressure:.1f} hPa"
                    draw.text((0, y_pos), text_line, font=oled_font, fill="white")
                    y_pos += oled_line_height
                    draw.text((0, y_pos), gas_resistance_str_oled, font=oled_font, fill="white")
        time.sleep(1) # Wait 1 second before the next reading
except KeyboardInterrupt:
    print("\nSensor reading stopped.")
finally:
    if 'csv_file' in locals() and csv_file and not csv_file.closed:
        csv_file.close()
        print(f"CSV file '{CSV_FILENAME}' closed.")
