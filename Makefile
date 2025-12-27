.PHONY: help install install-dev test coverage lint format clean run start stop status logs

# Default Python and pip commands
PYTHON := python3
PIP := pip3
VENV := venv
VENV_BIN := $(VENV)/bin

# Project paths
SRC_DIR := src
TEST_DIR := tests
CONFIG_DIR := config
SCRIPTS_DIR := scripts

help: ## Show this help message
	@echo "BME680 Monitor - Available commands:"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'

install: ## Install package and dependencies
	$(PIP) install -e .

install-dev: ## Install package with development dependencies
	$(PIP) install -e ".[dev]"

setup-venv: ## Create virtual environment
	$(PYTHON) -m venv $(VENV)
	@echo ""
	@echo "Virtual environment created. Activate with:"
	@echo "  source $(VENV_BIN)/activate"

test: ## Run tests with pytest
	$(PYTHON) -m pytest $(TEST_DIR) -v

test-cov: ## Run tests with coverage report
	$(PYTHON) -m pytest $(TEST_DIR) --cov=$(SRC_DIR) --cov-report=html --cov-report=term

coverage: test-cov ## Alias for test-cov

lint: ## Run code linting with flake8
	$(PYTHON) -m flake8 $(SRC_DIR) $(TEST_DIR) --max-line-length=100

format: ## Format code with black
	$(PYTHON) -m black $(SRC_DIR) $(TEST_DIR) --line-length=100

format-check: ## Check code formatting without making changes
	$(PYTHON) -m black $(SRC_DIR) $(TEST_DIR) --check --line-length=100

typecheck: ## Run type checking with mypy
	$(PYTHON) -m mypy $(SRC_DIR)

clean: ## Clean build artifacts and cache files
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info
	rm -rf .pytest_cache
	rm -rf .coverage
	rm -rf htmlcov/
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete

clean-data: ## Clean generated data files (CSV, baseline, logs)
	@echo "⚠️  This will delete all sensor data, logs, and calibration!"
	@read -p "Are you sure? [y/N] " -n 1 -r; \
	echo; \
	if [[ $$REPLY =~ ^[Yy]$$ ]]; then \
		rm -f *.csv gas_baseline.json; \
		rm -rf logs/; \
		echo "✓ Data cleaned"; \
	else \
		echo "Cancelled"; \
	fi

run: ## Run the sensor monitor
	$(PYTHON) sensor.py

start: ## Start sensor as background service (using control script)
	bash $(SCRIPTS_DIR)/sensor_control.sh start

stop: ## Stop sensor background service
	bash $(SCRIPTS_DIR)/sensor_control.sh stop

restart: ## Restart sensor background service
	bash $(SCRIPTS_DIR)/sensor_control.sh restart

status: ## Check sensor service status
	bash $(SCRIPTS_DIR)/sensor_control.sh status

logs: ## View live sensor logs
	bash $(SCRIPTS_DIR)/sensor_control.sh logs

check-hardware: ## Check I2C devices
	@echo "Checking I2C devices..."
	@if command -v i2cdetect >/dev/null 2>&1; then \
		sudo i2cdetect -y 1; \
	else \
		echo "⚠️  i2c-tools not installed. Install with:"; \
		echo "  sudo apt-get install i2c-tools"; \
	fi

install-system-deps: ## Install system dependencies (Raspberry Pi)
	sudo apt-get update
	sudo apt-get install -y python3-pip python3-venv i2c-tools git

enable-i2c: ## Enable I2C interface (requires reboot)
	@echo "Enabling I2C interface..."
	sudo raspi-config nonint do_i2c 0
	@echo "✓ I2C enabled. Reboot required: sudo reboot"

install-service: ## Install systemd service
	sudo cp $(SCRIPTS_DIR)/bme680-sensor.service /etc/systemd/system/
	sudo systemctl daemon-reload
	@echo "✓ Service installed. Enable with:"
	@echo "  sudo systemctl enable bme680-sensor"
	@echo "  sudo systemctl start bme680-sensor"

build: ## Build distribution packages
	$(PYTHON) setup.py sdist bdist_wheel

upload-test: build ## Upload to Test PyPI
	$(PYTHON) -m twine upload --repository testpypi dist/*

upload: build ## Upload to PyPI
	$(PYTHON) -m twine upload dist/*

verify-install: ## Verify installation by importing modules
	@echo "Verifying installation..."
	@$(PYTHON) -c "from bme680_monitor import Config, SensorManager, AirQualityCalculator; print('✓ All modules imported successfully')"

all: clean install test lint ## Run all checks (clean, install, test, lint)

dev-setup: setup-venv install-dev ## Complete development setup
	@echo ""
	@echo "✓ Development environment ready!"
	@echo ""
	@echo "Next steps:"
	@echo "  1. Activate venv: source $(VENV_BIN)/activate"
	@echo "  2. Run tests: make test"
	@echo "  3. Start sensor: make run"
