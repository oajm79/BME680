# Known Issues

## Weather service: sin backoff en fallos de red (spam de reintentos)

**Detectado:** 2026-07-18, durante investigación de una caída del equipo `oajm-rbpiz2w`.

**Síntoma:** El boot del equipo entre las 05:45 y 14:45 del 2026-07-18 registró 56,179
errores "Temporary failure in name resolution" del `weather_service`, a un ritmo de
~1.7 por segundo durante 9 horas continuas.

**Causa raíz (bug de código):**

- `sensor.py` llama a `weather.get_current_conditions()` en cada lectura del sensor
  (`config.sampling_interval`, default 1 segundo). Ver `sensor.py` (líneas ~127 y 429).
- `WeatherService` (`src/bme680_monitor/weather_service.py`) tiene un caché de 10
  minutos (`CACHE_DURATION = 600`) pensado para evitar spam a la API, pero el caché
  **solo se activa si hubo un fetch exitoso previo**:

  ```python
  if self._cache and (current_time - self._cache_time) < self.CACHE_DURATION:
      return self._cache
  ```

  Si el primer intento falla (ej. DNS no resuelve todavía), `self._cache` queda en
  `None` para siempre y **nunca hay backoff** — cada iteración del loop principal
  vuelve a intentar el fetch (2 requests por iteración: clima + calidad de aire).
  En un fallo prolongado esto genera decenas de miles de intentos DNS/HTTP fallidos
  por hora, consumiendo CPU y red en un equipo con solo 415MB de RAM (Pi Zero 2W).

**Posible disparador del fallo de DNS original (no confirmado):**

- El servicio systemd `bme680-sensor.service` arranca con `After=network.target`,
  que no garantiza que la red/DNS ya estén listos (a diferencia de
  `network-online.target`). Esto explicaría un fallo al boot, pero no 9 horas seguidas.
- El journal del sistema (kernel/NetworkManager) de ese boot específico se perdió, así
  que no se pudo confirmar si hubo una caída de WiFi prolongada esa madrugada.
- Es posible que `transmission-daemon` (retirado del equipo el mismo día por otras
  razones) haya contribuido saturando la misma antena WiFi que usa este servicio.

**Fix propuesto (pendiente de aplicar):**

1. Agregar backoff/caché negativo en `WeatherService`: cachear también los fallos por
   un período corto (ej. 60s) en vez de reintentar en cada sampling_interval.
2. Cambiar en `bme680-sensor.service`:
   `After=network.target` → `After=network-online.target` + agregar
   `Wants=network-online.target`, para esperar a que la red esté realmente lista.

**Estado:** Sin aplicar. Documentado para revisar después.
