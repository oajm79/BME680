#!/bin/bash

# ==============================================================================
# BME680 Sensor Control Script - Unified start/stop/status management
# ==============================================================================

# --- Configuration ---
VENV_DIR="venv"
PYTHON_SCRIPT="sensor.py"
LOG_DIR="logs"
PID_FILE="sensor.pid"
LOG_FILE="sensor.log"
SCRIPT_LOG="sensor_control.log"
HISTORY_LOG="sensor_history.log"
MAX_LOG_SIZE_MB=50

# --- Color Output ---
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

# --- Helper Functions ---
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1" | tee -a "$SCRIPT_LOG"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1" | tee -a "$SCRIPT_LOG"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1" | tee -a "$SCRIPT_LOG"
}

log_debug() {
    echo -e "${BLUE}[DEBUG]${NC} $1" | tee -a "$SCRIPT_LOG"
}

print_header() {
    echo -e "${CYAN}================================================================${NC}"
    echo -e "${CYAN}    BME680 Sensor Control - $1${NC}"
    echo -e "${CYAN}================================================================${NC}"
}

rotate_log_if_needed() {
    local logfile=$1
    local max_size_bytes=$((MAX_LOG_SIZE_MB * 1024 * 1024))

    if [ -f "$logfile" ]; then
        # Use stat -c%s for Linux (GNU coreutils)
        local size=$(stat -c%s "$logfile" 2>/dev/null)
        if [ -z "$size" ]; then
            # Fallback to stat -f%z for BSD/macOS
            size=$(stat -f%z "$logfile" 2>/dev/null)
        fi

        if [ -n "$size" ] && [ "$size" -gt "$max_size_bytes" ]; then
            log_info "Log file $logfile exceeds ${MAX_LOG_SIZE_MB}MB, rotating..."
            mv "$logfile" "${logfile}.old"
            log_info "Old log saved as ${logfile}.old"
        fi
    fi
}

check_if_running() {
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if ps -p "$PID" > /dev/null 2>&1; then
            return 0  # Running
        else
            log_warn "PID file exists but process $PID is not running. Cleaning up..."
            rm -f "$PID_FILE"
            return 1  # Not running
        fi
    fi
    return 1  # PID file doesn't exist
}

check_requirements() {
    log_info "Checking system requirements..."
    
    if ! command -v i2cdetect &> /dev/null; then
        log_warn "i2c-tools not found. Install with: sudo apt-get install i2c-tools"
    else
        log_debug "Checking I2C devices..."
        i2cdetect -y 1 > /dev/null 2>&1
        if [ $? -ne 0 ]; then
            log_warn "I2C may not be enabled. Enable with: sudo raspi-config"
        fi
    fi
    
    if command -v python3 &> /dev/null; then
        PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
        log_debug "Python version: $PYTHON_VERSION"
    else
        log_error "Python3 not found!"
        return 1
    fi
    
    AVAILABLE_SPACE=$(df -h "$SCRIPT_DIR" | awk 'NR==2 {print $4}')
    log_debug "Available disk space: $AVAILABLE_SPACE"
    
    return 0
}

# --- Command Functions ---

cmd_start() {
    print_header "START"
    log_info "Start command initiated at $(date)"
    
    if check_if_running; then
        PID=$(cat "$PID_FILE")
        log_error "Sensor is already running with PID $PID"
        echo ""
        echo "Use: $0 stop    to stop the sensor"
        echo "Use: $0 status  to check status"
        exit 1
    fi
    
    rotate_log_if_needed "$LOG_FILE"
    rotate_log_if_needed "$SCRIPT_LOG"
    
    check_requirements
    if [ $? -ne 0 ]; then
        log_error "System requirements check failed"
        exit 1
    fi
    
    cd "$SCRIPT_DIR" || exit
    
    # Git pull
    log_info "Checking for updates..."
    if git rev-parse --git-dir > /dev/null 2>&1; then
        GIT_OUTPUT=$(git pull 2>&1)
        GIT_EXIT_CODE=$?
        
        if [ $GIT_EXIT_CODE -eq 0 ]; then
            if echo "$GIT_OUTPUT" | grep -q "Already up to date"; then
                log_info "Repository is up to date"
            else
                log_info "Repository updated successfully"
            fi
        else
            log_warn "Git pull failed, continuing with local version"
        fi
    else
        log_warn "Not a git repository. Skipping update."
    fi
    
    # Validate virtual environment
    if [ ! -d "$VENV_PATH" ]; then
        log_error "Virtual environment '$VENV_PATH' not found."
        echo ""
        echo "Create it with:"
        echo "  python3 -m venv $VENV_DIR"
        echo "  source $VENV_DIR/bin/activate"
        echo "  pip install -r requirements.txt"
        exit 1
    fi
    
    if [ ! -f "$SENSOR_SCRIPT_PATH" ]; then
        log_error "Script '$SENSOR_SCRIPT_PATH' not found."
        exit 1
    fi
    
    # Verify packages
    log_info "Verifying virtual environment packages..."
    source "$VENV_PATH/bin/activate"
    
    python3 -c "import bme680, luma.oled" 2>/dev/null
    if [ $? -ne 0 ]; then
        log_warn "Some required packages may be missing."
        echo ""
        echo "Install dependencies with:"
        echo "  source $VENV_DIR/bin/activate"
        echo "  pip install -r requirements.txt"
        read -p "Continue anyway? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            exit 1
        fi
    fi
    
    # Start the sensor
    echo "$(date): Sensor started" >> "$HISTORY_LOG_FILE"
    
    log_info "Starting sensor script in the background..."
    nohup python3 "$SENSOR_SCRIPT_PATH" > "$LOG_FILE" 2>&1 &
    
    SENSOR_PID=$!
    echo $SENSOR_PID > "$PID_FILE"
    
    sleep 2
    if ps -p $SENSOR_PID > /dev/null 2>&1; then
        log_info "✓ Sensor started successfully!"
        echo ""
        echo -e "${CYAN}================================================================${NC}"
        echo "  Process ID: $SENSOR_PID"
        echo "  Log file: $LOG_FILE"
        echo ""
        echo "Useful commands:"
        echo "  $0 status         - Check sensor status"
        echo "  $0 stop           - Stop the sensor"
        echo "  $0 restart        - Restart the sensor"
        echo "  $0 logs           - View live logs"
        echo -e "${CYAN}================================================================${NC}"
    else
        log_error "Failed to start sensor!"
        log_error "Check $LOG_FILE for details"
        rm -f "$PID_FILE"
        exit 1
    fi
}

cmd_stop() {
    print_header "STOP"
    
    if [ ! -f "$PID_FILE" ]; then
        log_error "PID file not found. Sensor may not be running."
        exit 1
    fi
    
    PID=$(cat "$PID_FILE")
    
    if ! ps -p "$PID" > /dev/null 2>&1; then
        log_warn "Process $PID is not running."
        log_info "Cleaning up PID file..."
        rm -f "$PID_FILE"
        exit 1
    fi
    
    log_info "Stopping sensor process (PID: $PID)..."
    kill "$PID"
    
    COUNTER=0
    while ps -p "$PID" > /dev/null 2>&1 && [ $COUNTER -lt 10 ]; do
        sleep 1
        COUNTER=$((COUNTER + 1))
        echo -n "."
    done
    echo ""
    
    if ps -p "$PID" > /dev/null 2>&1; then
        log_warn "Process did not stop gracefully. Forcing..."
        kill -9 "$PID"
        sleep 1
    fi
    
    if ! ps -p "$PID" > /dev/null 2>&1; then
        log_info "✓ Sensor stopped successfully!"
        rm -f "$PID_FILE"
        echo "$(date): Sensor stopped" >> "$HISTORY_LOG_FILE"
    else
        log_error "Failed to stop the process!"
        exit 1
    fi
}

cmd_restart() {
    print_header "RESTART"
    log_info "Restart command initiated"
    
    if check_if_running; then
        cmd_stop
        sleep 2
    fi
    
    cmd_start
}

cmd_status() {
    print_header "STATUS"
    
    if check_if_running; then
        PID=$(cat "$PID_FILE")
        UPTIME=$(ps -p "$PID" -o etime= | tr -d ' ')
        MEM=$(ps -p "$PID" -o rss= | awk '{printf "%.1f MB", $1/1024}')
        
        echo -e "${GREEN}✓ Sensor is RUNNING${NC}"
        echo ""
        echo "  PID:        $PID"
        echo "  Uptime:     $UPTIME"
        echo "  Memory:     $MEM"
        echo "  Log file:   $LOG_FILE"
        echo ""
        
        if [ -f "$LOG_FILE" ]; then
            echo "Last 5 log entries:"
            echo -e "${BLUE}----------------------------------------${NC}"
            tail -n 5 "$LOG_FILE"
            echo -e "${BLUE}----------------------------------------${NC}"
        fi
    else
        echo -e "${RED}✗ Sensor is NOT RUNNING${NC}"
        echo ""
        echo "Start with: $0 start"
    fi
}

cmd_logs() {
    print_header "LOGS"
    
    if [ ! -f "$LOG_FILE" ]; then
        log_error "Log file not found: $LOG_FILE"
        exit 1
    fi
    
    log_info "Showing live logs (Ctrl+C to exit)..."
    echo ""
    tail -f "$LOG_FILE"
}

show_usage() {
    cat << EOF
Usage: $0 {start|stop|restart|status|logs}

Commands:
  start      Start the sensor monitoring
  stop       Stop the sensor monitoring
  restart    Restart the sensor (stop + start)
  status     Show current sensor status
  logs       View live sensor logs (tail -f)

Examples:
  $0 start
  $0 status
  $0 logs

EOF
    exit 1
}

# --- Main Script Logic ---
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"  # Parent directory of scripts/
LOG_DIR_PATH="$PROJECT_ROOT/logs"
VENV_PATH="$PROJECT_ROOT/$VENV_DIR"
SENSOR_SCRIPT_PATH="$PROJECT_ROOT/$PYTHON_SCRIPT"
PID_FILE="$LOG_DIR_PATH/sensor.pid"
LOG_FILE="$LOG_DIR_PATH/sensor.log"
SCRIPT_LOG="$LOG_DIR_PATH/sensor_control.log"
HISTORY_LOG_FILE="$LOG_DIR_PATH/$HISTORY_LOG"

# Create log directory if it doesn't exist
mkdir -p "$LOG_DIR_PATH"

# Check for command argument
if [ $# -eq 0 ]; then
    show_usage
fi

COMMAND=$1

case "$COMMAND" in
    start)
        cmd_start
        ;;
    stop)
        cmd_stop
        ;;
    restart)
        cmd_restart
        ;;
    status)
        cmd_status
        ;;
    logs)
        cmd_logs
        ;;
    *)
        echo -e "${RED}Error: Unknown command '$COMMAND'${NC}"
        echo ""
        show_usage
        ;;
esac

exit 0