import os
import urllib3
import requests

from app.utils.logger import logger

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def isolate_host(target_ip: str, incident_id: int, wazuh_api_url: str) -> bool:
    """
    Isole un hôte via l'Active Response Wazuh (commande firewall-drop).
    Retourne True si le Manager a accepté la commande (HTTP 200), False sinon.
    Toutes les tentatives sont journalisées, les exceptions ne se propagent pas.
    """
    logger.info(f'[SOAR] isolate_host: cible={target_ip} incident={incident_id}')

    try:
        # 1. Authentification JWT
        token = _get_token(wazuh_api_url)
        if not token:
            logger.error(f'[SOAR] isolate_host: token JWT non obtenu — abandon')
            return False

        headers = {'Authorization': f'Bearer {token}'}

        # 2. Recherche de l'agent correspondant à target_ip
        agents_resp = requests.get(
            f'{wazuh_api_url}/agents',
            headers=headers,
            params={'q': f'ip={target_ip}', 'limit': 1},
            verify=False,
            timeout=5,
        )
        agents_resp.raise_for_status()
        affected = agents_resp.json().get('data', {}).get('affected_items', [])

        if not affected:
            logger.warning(f'[SOAR] isolate_host: aucun agent trouvé pour IP {target_ip}')
            return False

        agent_id = affected[0]['id']
        logger.info(f'[SOAR] isolate_host: agent trouvé id={agent_id}')

        # 3. Envoi de l'Active Response firewall-drop
        ar_resp = requests.put(
            f'{wazuh_api_url}/active-response',
            headers=headers,
            params={'agents_list': agent_id},
            json={
                'command': 'firewall-drop',
                'arguments': [target_ip],
                'alert': {'data': {'srcip': target_ip}},
            },
            verify=False,
            timeout=5,
        )

        success = ar_resp.status_code == 200
        if success:
            logger.info(f'[SOAR] isolate_host: SUCCÈS agent={agent_id} IP={target_ip}')
        else:
            logger.warning(
                f'[SOAR] isolate_host: ÉCHEC agent={agent_id} '
                f'status={ar_resp.status_code} body={ar_resp.text[:200]}'
            )
        return success

    except Exception as e:
        logger.error(f'[SOAR] isolate_host: exception pour {target_ip}: {e}')
        return False


def _get_token(wazuh_api_url: str):
    try:
        resp = requests.post(
            f'{wazuh_api_url}/security/user/authenticate',
            auth=(
                os.getenv('WAZUH_USER', 'wazuh-wui'),
                os.getenv('WAZUH_PASSWORD', ''),
            ),
            verify=False,
            timeout=5,
        )
        resp.raise_for_status()
        return resp.json()['data']['token']
    except Exception as e:
        logger.warning(f'[SOAR] isolate_host _get_token failed: {e}')
        return None
