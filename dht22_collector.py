#!/usr/bin/env python3

import time
import logging
import board
import adafruit_dht
import requests
from datetime import datetime, timezone

API_URL   = "http://172.16.1.15/api/iot/readings"  # à adapter à l'IP de SRV-APP
GPIO_PIN  = board.D4   # GPIO PIN 4 (BCM)
INTERVAL  = 60         # secondes
TOKEN     = "token_secret_rpi5"                     # doit correspondre à IOT_API_TOKEN dans .env

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.FileHandler("/var/log/dht22.log"), logging.StreamHandler()],
)

capteur = adafruit_dht.DHT22(GPIO_PIN, use_pulseio=False)  # use_pulseio=False obligatoire sur RPi5

while True:
    try:
        temp = capteur.temperature
        hum  = capteur.humidity

        if temp is None or hum is None:
            raise RuntimeError("Valeurs nulles")

        logging.info("Temp=%.1f°C  Hum=%.1f%%", temp, hum)

        requests.post(API_URL,
            headers={"Authorization": f"Bearer {TOKEN}"},
            json={
                "temperature": round(temp, 1),
                "humidity":    round(hum, 1),
                "timestamp":   datetime.now(timezone.utc).isoformat(),
                "sensor_id":   "dht22-rpi5",
            }, timeout=5)

    except RuntimeError as e:
        logging.warning("Erreur lecture DHT22 : %s", e)
        time.sleep(2)
        continue

    except Exception as e:
        logging.error("Erreur critique : %s", e)
        capteur.exit()
        raise

    time.sleep(INTERVAL)


