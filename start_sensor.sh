#!/bin/bash

# ==============================================================================
# Script to run the BME680 sensor reading inside a virtual environment
# ==============================================================================

# Description:
# This script automates the process of activating the Python virtual environment
# and then running the 'sensor.py' script. It is designed to be robust,
# ensuring it runs from the correct location and that the necessary files exist.

# --- Configuration ---
# Name of the virtual environment directory. Change this if you use a different name (e.g., ".venv").
VENV_DIR="venv"

# Name of the Python script to execute.
PYTHON_SCRIPT="sensor.py"

# --- Script Logic ---
# Gets the absolute path of the directory where the script is located.
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"

# Builds the full paths for the virtual environment and the Python script.
VENV_PATH="$SCRIPT_DIR/$VENV_DIR"
SENSOR_SCRIPT_PATH="$SCRIPT_DIR/$PYTHON_SCRIPT"

echo "Starting sensor script..."

# 1. Validate that the virtual environment exists.
if [ ! -d "$VENV_PATH" ]; then
    echo "Error: The virtual environment directory '$VENV_PATH' was not found."
    echo "Please ensure you have created the virtual environment in the project directory."
    exit 1
fi

# 2. Validate that the sensor script exists.
if [ ! -f "$SENSOR_SCRIPT_PATH" ]; then
    echo "Error: The script '$SENSOR_SCRIPT_PATH' was not found."
    exit 1
fi

# 3. Activate the virtual environment and run the Python script.
echo "Activating virtual environment and running '$PYTHON_SCRIPT'..."
source "$VENV_PATH/bin/activate"
python3 "$SENSOR_SCRIPT_PATH"

# 4. The Python script is now running. When it stops (e.g., with Ctrl+C),
# the virtual environment will be deactivated automatically as this script finishes.
echo "Sensor script has finished."
