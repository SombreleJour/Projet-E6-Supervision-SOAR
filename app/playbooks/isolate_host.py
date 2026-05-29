import os
import urllib3
import requests

from ..utils.logger import logger

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def isolate_host(target_ip: str, incident_id: int, wazuh_api_url: str) -> bool:
    logger.info('[SOAR] isolate_host: cible=%s incident=%d', target_ip, incident_id)
    try:
        token = _get_token(wazuh_api_url)
        if not token:
            logger.error('[SOAR] isolate_host: token JWT non obtenu')
            return False

        headers = {'Authorization': f'Bearer {token}'}

        agents = requests.get(
            f'{wazuh_api_url}/agents',
            headers=headers,
            params={'q': f'ip={target_ip}', 'limit': 1},
            verify=False, timeout=5,
        )
        agents.raise_for_status()
        items = agents.json().get('data', {}).get('affected_items', [])
        if not items:
            logger.warning('[SOAR] isolate_host: aucun agent pour IP %s', target_ip)
            return False

        agent_id = items[0]['id']
        resp = requests.put(
            f'{wazuh_api_url}/active-response',
            headers=headers,
            params={'agents_list': agent_id},
            json={'command': 'firewall-drop', 'arguments': [target_ip],
                  'alert': {'data': {'srcip': target_ip}}},
            verify=False, timeout=5,
        )
        success = resp.status_code == 200
        if success:
            logger.info('[SOAR] isolate_host: SUCCÈS agent=%s IP=%s', agent_id, target_ip)
        else:
            logger.warning('[SOAR] isolate_host: ÉCHEC status=%d', resp.status_code)
        return success

    except Exception as e:
        logger.error('[SOAR] isolate_host: %s', e)
        return False


def _get_token(wazuh_api_url):
    try:
        resp = requests.post(
            f'{wazuh_api_url}/security/user/authenticate',
            auth=(os.getenv('WAZUH_USER', 'wazuh-wui'), os.getenv('WAZUH_PASSWORD', '')),
            verify=False, timeout=5,
        )
        resp.raise_for_status()
        return resp.json()['data']['token']
    except Exception as e:
        logger.warning('[SOAR] _get_token: %s', e)
        return None
