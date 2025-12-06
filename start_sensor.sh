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

# File to store the process ID (PID)
PID_FILE="sensor.pid"

# --- Script Logic ---
# Gets the absolute path of the directory where the script is located.
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"

# Builds the full paths for the virtual environment and the Python script.
VENV_PATH="$SCRIPT_DIR/$VENV_DIR"
SENSOR_SCRIPT_PATH="$SCRIPT_DIR/$PYTHON_SCRIPT"

echo "Starting sensor script..."

# Change to the script's directory to ensure git commands run in the correct repository.
cd "$SCRIPT_DIR" || exit

# Pull the latest changes from the git repository.
echo "Updating from Git repository..."
git pull
echo "Update complete."

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

# 3. Activate the virtual environment and run the Python script in the background.
echo "Activating virtual environment and running '$PYTHON_SCRIPT' in the background..."
source "$VENV_PATH/bin/activate"

# The 'nohup' command makes the script ignore hangup signals, so it keeps running when the terminal closes.
# The output (stdout and stderr) is redirected to 'sensor.log'.
# The '&' at the end sends the process to the background.
nohup python3 "$SENSOR_SCRIPT_PATH" > "$SCRIPT_DIR/sensor.log" 2>&1 &

# 4. Save the Process ID (PID) of the background script to a file.
# This makes it easy to stop the script later.
echo $! > "$SCRIPT_DIR/$PID_FILE"

echo "Sensor script is now running in the background."
echo "Process ID (PID): $(cat "$SCRIPT_DIR/$PID_FILE"). Output is being logged to '$SCRIPT_DIR/sensor.log'."
