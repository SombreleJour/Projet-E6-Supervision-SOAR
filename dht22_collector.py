#!/usr/bin/env python3

import time
import logging
import board
import adafruit_dht
import requests
from datetime import datetime, timezone

API_BASE   = "http://172.16.1.15"            # IP de SRV-APP (à adapter)
API_URL    = f"{API_BASE}/api/iot/readings"
CONFIG_URL = f"{API_BASE}/api/iot/config"    # cadence d'envoi pilotée par l'app web
GPIO_PIN   = board.D4                         # GPIO PIN 4 (BCM)
DEFAULT_INTERVAL = 60                         # secondes — repli si l'API est injoignable
TOKEN      = "token_secret_rpi5"             # doit correspondre à IOT_API_TOKEN dans .env

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.FileHandler("/var/log/dht22.log"), logging.StreamHandler()],
)

capteur = adafruit_dht.DHT22(GPIO_PIN, use_pulseio=False)  # use_pulseio=False obligatoire sur RPi5


def get_interval(current):
    """Récupère la cadence d'envoi (en secondes) réglée dans l'app web.

    Renvoie `current` si l'API est injoignable ou la valeur invalide, pour ne
    jamais bloquer la collecte en cas de coupure réseau.
    """
    try:
        r = requests.get(CONFIG_URL,
                         headers={"Authorization": f"Bearer {TOKEN}"},
                         timeout=5)
        if r.ok:
            val = int(r.json().get("interval", current))
            if 1 <= val <= 600:
                if val != current:
                    logging.info("Nouvelle cadence d'envoi : %ss", val)
                return val
    except Exception as e:
        logging.warning("Config injoignable, cadence inchangée (%ss) : %s", current, e)
    return current


interval = DEFAULT_INTERVAL

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

    # Ajuste la cadence selon le réglage de l'app web, puis attend jusqu'au prochain envoi.
    interval = get_interval(interval)
    time.sleep(interval)
