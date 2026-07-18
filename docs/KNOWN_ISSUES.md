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
- El journal del sistema (kernel/NetworkManager) de ese boot específico se perdió: el
  boot en cuestión no tenía journal persistente (`/var/log/journal` recién se creó el
  2026-07-18 a las 14:42) y el propio flood de ~112k líneas de log del bug de arriba
  saturó el ring buffer volátil de `/run` (84MB de tmpfs), expulsando los mensajes de
  arranque de kernel/NetworkManager antes de que hubiera almacenamiento persistente.
  El equipo tampoco tiene RTC (`/dev/rtc*` no existe), así que sin DNS tampoco pudo
  sincronizar NTP durante esas 9 horas — coherente con una caída de red sostenida y
  no solo una asociación WiFi lenta al boot.
- Es posible que `transmission-daemon` (retirado del equipo el mismo día por otras
  razones) haya contribuido saturando la misma antena WiFi que usa este servicio.

**Fix aplicado (2026-07-18):**

1. `WeatherService` ahora registra `_last_failure_time` y espera `FAILURE_BACKOFF = 60`
   segundos antes de reintentar tras un fallo, en vez de reintentar en cada
   `sampling_interval`. Cubierto por `tests/test_weather_service.py`
   (`test_does_not_retry_immediately_after_failed_fetch`).
2. `bme680-sensor.service` (unit real en `/etc/systemd/system/` y el template en
   `scripts/`) cambiado de `After=network.target` a
   `After=network-online.target` + `Wants=network-online.target`.

**Estado:** Aplicado. Pendiente: `systemctl daemon-reload` + reinicio del servicio en
`oajm-rbpiz2w` para que tome el cambio del unit file.
