> **Nota de mantenimiento:** `GEMINI.md` es un enlace simbólico a este archivo (`CLAUDE.md`).
> Si eres Gemini y necesitas actualizar `GEMINI.md`, edita **este archivo** (`CLAUDE.md`) en su lugar.

# Project: BME680 Environmental Monitor

## Propósito
Sistema de monitoreo ambiental y calidad del aire en tiempo real para Raspberry Pi Zero 2W (`oajm-rbpiz2w`), con sensor Bosch BME680, display OLED, almacenamiento SQLite y alertas vía Telegram/OpenClaw.

## Arquitectura
1. **Punto de entrada:** `sensor.py` (ejecutado en la Pi Zero 2W vía `bme680-sensor.service`).
2. **Módulos (`src/bme680_monitor/`):**
   - `sensor_manager.py`: Control de hardware I2C para BME680.
   - `air_quality.py`: Cálculo híbrido de IAQ combinando resistencia de gas y humedad relativa.
   - `comfort_index.py`: Índice de confort térmico y recomendaciones operativas.
   - `display.py`: Control de pantalla OLED 128x64 (luma.oled).
   - `database.py`: Persistencia en SQLite (`data/sensor_data.db`) con rotación y auto-vacuum.
   - `telegram_notifier.py`: Despacho de alertas a Telegram a través de OpenClaw con fallback directo a HTTP.
3. **Integración Homelab:**
   - En `oajm-rbpiz2w`, `pi-backend/runner.py` lee la base de datos de sensores y despacha `bme680.json` hacia Hostinger cada 60 segundos.
   - En `oajm-rbpi5`, `pi-backend/services/watchdog.py` monitorea la conectividad de red del nodo Pi Zero en el puerto 22.

## Comandos Críticos
- **Ejecutar tests:** `.venv/bin/pytest tests/`
- **Control del servicio en Pi Zero:** `systemctl status bme680-sensor.service`
- **Compilar sintaxis:** `python3 -m py_compile sensor.py`

## Restricciones e Invariantes
- No alterar las fórmulas de calibración de baseline de gas sin burn-in previo de 20 minutos.
- Las alertas a Telegram usan `shared-services-lib` para formato y enrutamiento.
