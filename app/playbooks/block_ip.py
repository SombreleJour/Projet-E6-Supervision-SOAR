import os
import urllib3
import requests

from ..utils.logger import logger

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def block_ip(target_ip: str, incident_id: int) -> bool:
    logger.info('[SOAR] block_ip: cible=%s incident=%d', target_ip, incident_id)
    try:
        resp = requests.post(
            f'{os.getenv("PFSENSE_URL", "https://172.16.1.1")}/api/v1/firewall/rule',
            json={
                'type': 'block',
                'interface': 'wan',
                'ipprotocol': 'inet',
                'protocol': 'any',
                'src': target_ip,
                'dst': 'any',
                'descr': f'SOAR auto-block — incident #{incident_id}',
                'enabled': True,
            },
            auth=(os.getenv('PFSENSE_USER', 'admin'), os.getenv('PFSENSE_PASSWORD', '')),
            verify=False, timeout=5,
        )
        success = resp.status_code in (200, 201)
        if success:
            logger.info('[SOAR] block_ip: SUCCÈS %s', target_ip)
        else:
            logger.warning('[SOAR] block_ip: ÉCHEC status=%d', resp.status_code)
        return success
    except Exception as e:
        logger.error('[SOAR] block_ip: %s', e)
        return False
