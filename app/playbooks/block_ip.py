import os
import urllib3
import requests

from app.utils.logger import logger

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def block_ip(target_ip: str, incident_id: int) -> bool:
    """
    Bloque une IP via l'API pfSense (pfSense-API package).
    Ajoute une règle WAN de type block sur la source IP spécifiée.
    Retourne True si succès, False sinon. Ne propage jamais d'exception (fail-safe).
    """
    pfsense_url = os.getenv('PFSENSE_URL', 'https://172.16.1.1')
    user = os.getenv('PFSENSE_USER', 'admin')
    password = os.getenv('PFSENSE_PASSWORD', '')

    logger.info(f'[SOAR] block_ip: cible={target_ip} incident={incident_id}')

    try:
        payload = {
            'type': 'block',
            'interface': 'wan',
            'ipprotocol': 'inet',
            'protocol': 'any',
            'src': target_ip,
            'dst': 'any',
            'descr': f'SOAR auto-block — incident #{incident_id}',
            'enabled': True,
        }
        resp = requests.post(
            f'{pfsense_url}/api/v1/firewall/rule',
            json=payload,
            auth=(user, password),
            verify=False,
            timeout=5,
        )

        success = resp.status_code in (200, 201)
        if success:
            logger.info(f'[SOAR] block_ip: SUCCÈS {target_ip} bloqué via pfSense')
        else:
            logger.warning(
                f'[SOAR] block_ip: pfSense a retourné {resp.status_code} '
                f'pour {target_ip}: {resp.text[:200]}'
            )
        return success

    except Exception as e:
        logger.error(f'[SOAR] block_ip: exception pour {target_ip}: {e}')
        return False
