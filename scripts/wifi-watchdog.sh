#!/bin/bash
# WiFi reconnect watchdog for oajm-rbpiz2w (Raspberry Pi Zero 2W).
#
# Why this exists: on 2026-07-18 NetworkManager logged
#   device (wlan0): state change: config -> failed (reason 'no-secrets')
# after a handful of transient WPA handshake failures on SSID "707"
# (WPA2/WPA3 mixed mode). The saved password is correct — the box
# reconnects instantly with the same credentials on a manual reboot —
# but NetworkManager treats a 'no-secrets' failure as a hard stop and
# does NOT retry autoconnect afterwards. Since the bme680-sensor
# service's core read/display loop doesn't need the network, the app
# keeps running and showing data on the OLED with no visible sign that
# the Pi has silently dropped off the LAN, sometimes for hours, until
# someone notices and power-cycles it.
#
# This script forces a reconnect attempt if the gateway is unreachable.
# It's idempotent and cheap enough to run every few minutes via the
# companion wifi-watchdog.timer.

set -euo pipefail

GATEWAY="$(ip route show default 2>/dev/null | awk '/default/ {print $3; exit}')"
CONNECTION="netplan-wlan0-707"
LOG_TAG="wifi-watchdog"

if [ -z "$GATEWAY" ]; then
    logger -t "$LOG_TAG" "No default gateway configured, skipping check"
    exit 0
fi

if ping -c 2 -W 3 "$GATEWAY" >/dev/null 2>&1; then
    exit 0
fi

logger -t "$LOG_TAG" "Gateway $GATEWAY unreachable, forcing reconnect of $CONNECTION"
nmcli connection up "$CONNECTION" >/tmp/wifi-watchdog-last.log 2>&1 || \
    logger -t "$LOG_TAG" "Reconnect attempt failed, see /tmp/wifi-watchdog-last.log"
