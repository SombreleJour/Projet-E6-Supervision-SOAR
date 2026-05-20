#!/usr/bin/env python3
"""
Script de collecte DHT22 - Raspberry Pi 5
Projet E6 - Supervision Hybride PRTG/Wazuh - MAZZONE Milo

Lecture température/humidité via DHT22 sur GPIO PIN 4,
validation des données, envoi à l'API REST Flask, journalisation.

Dépendances :
    pip install adafruit-circuitpython-dht requests

Usage :
    python3 dht22_collector.py
    ou en service systemd (voir documentation)
"""

import time
import logging
import os
import sys
from datetime import datetime

import board
import adafruit_dht
import requests
from requests.exceptions import RequestException

# ─────────────────────────────────────────
# Configuration (surcharger via variables d'environnement)
# ─────────────────────────────────────────

API_URL        = os.getenv("API_URL",        "http://172.16.1.15/api/iot/readings")
API_TOKEN      = os.getenv("API_TOKEN",      "")          # Bearer token si auth activée
GPIO_PIN       = board.D4                                  # GPIO PIN 4 (BCM)
INTERVAL_SEC   = int(os.getenv("INTERVAL",   "60"))        # Intervalle entre mesures
RETRY_DELAY    = 2                                         # Délai avant retry (s)
MAX_RETRIES    = 3                                         # Tentatives max par cycle
TEMP_MIN       = -10.0                                     # Seuil bas température (°C)
TEMP_MAX       = 60.0                                      # Seuil haut température (°C)
HUM_MIN        = 0.0                                       # Seuil bas humidité (%)
HUM_MAX        = 100.0                                     # Seuil haut humidité (%)
LOG_FILE       = os.getenv("LOG_FILE",       "/var/log/dht22_collector.log")
REQUEST_TIMEOUT = 5                                        # Timeout requête HTTP (s)

# ─────────────────────────────────────────
# Journalisation
# ─────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)

# ─────────────────────────────────────────
# Initialisation capteur
# ─────────────────────────────────────────

try:
    capteur = adafruit_dht.DHT22(GPIO_PIN, use_pulseio=False)
    logger.info("Capteur DHT22 initialisé sur GPIO PIN 4")
except Exception as e:
    logger.critical("Impossible d'initialiser le DHT22 : %s", e)
    sys.exit(1)

# ─────────────────────────────────────────
# Fonctions
# ─────────────────────────────────────────

def lire_dht22() -> tuple[float | None, float | None]:
    """
    Lit température et humidité depuis le DHT22.
    Retourne (None, None) si la lecture échoue.
    """
    try:
        temperature = capteur.temperature
        humidite    = capteur.humidity
        return temperature, humidite
    except RuntimeError as e:
        logger.debug("Erreur de lecture DHT22 (transitoire) : %s", e)
        return None, None
    except Exception as e:
        logger.error("Erreur inattendue lors de la lecture DHT22 : %s", e)
        return None, None


def valeurs_valides(temperature: float | None, humidite: float | None) -> bool:
    """
    Vérifie que les valeurs sont dans les plages physiquement acceptables.
    """
    if temperature is None or humidite is None:
        return False
    if not (TEMP_MIN <= temperature <= TEMP_MAX):
        logger.warning("Température hors plage : %.1f °C", temperature)
        return False
    if not (HUM_MIN <= humidite <= HUM_MAX):
        logger.warning("Humidité hors plage : %.1f %%", humidite)
        return False
    return True


def lire_avec_retry() -> tuple[float | None, float | None]:
    """
    Tente MAX_RETRIES lectures avec RETRY_DELAY secondes entre chaque.
    Retourne (None, None) si toutes les tentatives échouent.
    """
    for tentative in range(1, MAX_RETRIES + 1):
        temperature, humidite = lire_dht22()
        if valeurs_valides(temperature, humidite):
            return temperature, humidite
        if tentative < MAX_RETRIES:
            logger.debug("Tentative %d/%d échouée, retry dans %ds",
                         tentative, MAX_RETRIES, RETRY_DELAY)
            time.sleep(RETRY_DELAY)
    logger.error("Échec de lecture après %d tentatives", MAX_RETRIES)
    return None, None


def envoyer_api_rest(temperature: float, humidite: float) -> bool:
    """
    Envoie les mesures à l'API REST Flask via POST JSON.
    Retourne True si l'envoi a réussi, False sinon.
    """
    payload = {
        "temperature": round(temperature, 1),
        "humidity":    round(humidite,    1),
        "timestamp":   datetime.utcnow().isoformat() + "Z",
        "sensor_id":   "dht22-rpi5-iot",
    }
    headers = {"Content-Type": "application/json"}
    if API_TOKEN:
        headers["Authorization"] = f"Bearer {API_TOKEN}"

    try:
        response = requests.post(
            API_URL,
            json=payload,
            headers=headers,
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        logger.info(
            "Envoi OK — temp=%.1f°C  hum=%.1f%%  (HTTP %d)",
            temperature, humidite, response.status_code,
        )
        return True
    except RequestException as e:
        logger.error("Échec de l'envoi API : %s", e)
        return False

# ─────────────────────────────────────────
# Boucle principale
# ─────────────────────────────────────────

def main() -> None:
    logger.info("Démarrage du collecteur DHT22 (intervalle=%ds)", INTERVAL_SEC)

    while True:
        debut = time.monotonic()

        temperature, humidite = lire_avec_retry()

        if valeurs_valides(temperature, humidite):
            envoyer_api_rest(temperature, humidite)
        else:
            logger.warning("Mesure ignorée — données invalides ou lecture impossible")

        # Compenser le temps passé pour maintenir un intervalle régulier
        elapsed = time.monotonic() - debut
        sleep_time = max(0, INTERVAL_SEC - elapsed)
        time.sleep(sleep_time)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("Arrêt manuel du collecteur")
        capteur.exit()
        sys.exit(0)