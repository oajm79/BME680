#!/usr/bin/env python3
import bme680
import time

# Intentar crear una instancia del sensor.
# Si tu sensor tiene la dirección I2C 0x76, usa: sensor = bme680.BME680(0x76)
try:
    sensor = bme680.BME680(0x77)
except RuntimeError as e:
    print(f"Error al inicializar el sensor: {e}")
    print("Asegúrate de que las conexiones SDA y SCL son correctas")
    print("y que I2C está habilitado en la Raspberry Pi (sudo raspi-config -> Interfacing Options -> I2C).")
    exit()

print("Sensor BME680 detectado. Leyendo datos...")

# Configurar oversampling y filtros si es necesario (opcional, valores por defecto suelen funcionar)
# sensor.set_temperature_oversample(bme680.OS_2X)
# sensor.set_humidity_oversample(bme680.OS_2X)
# sensor.set_pressure_oversample(bme680.OS_2X)
# sensor.set_filter(bme680.FILTER_SIZE_2)

# Configurar el calentador de gas (necesario para la lectura de gas)
# Ajusta la temperatura y el tiempo según las recomendaciones para el sensor si las tienes
sensor.set_gas_heater_temperature(320)
sensor.set_gas_heater_duration(150)
#sensor.select_gas_heater(bme680.GASSENSOR_ENABLE)


print("Leyendo datos cada segundo. Presiona Ctrl+C para salir.")

try:
    while True:
        if sensor.get_sensor_data():
            output = '{0:.2f} C, {1:.2f} %RH, {2:.2f} hPa'.format(
                sensor.data.temperature,
                sensor.data.humidity,
                sensor.data.pressure)

            if sensor.data.heat_stable:
                # La resistencia del gas tarda un tiempo en estabilizarse después de encender el calentador
                output += ', {0:.2f} Ohms de gas'.format(sensor.data.gas_resistance)
            else:
                output += ', Calentando sensor de gas...'

            print(output)

        time.sleep(1) # Espera 1 segundo antes de la próxima lectura

except KeyboardInterrupt:
    print("\nLectura de sensor detenida.")
