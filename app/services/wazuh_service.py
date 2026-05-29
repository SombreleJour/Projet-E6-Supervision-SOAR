import os
import re
import urllib3
import requests

from ..extensions import db
from ..models.asset import Asset
from ..utils.logger import logger

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def _api_url():
    return os.getenv('WAZUH_API_URL', 'https://172.16.1.10:55000')


def _indexer_url():
    return re.sub(r':\d+$', ':9200', _api_url())


def _credentials():
    return os.getenv('WAZUH_USER', 'wazuh-wui'), os.getenv('WAZUH_PASSWORD', '')


def get_token():
    try:
        user, password = _credentials()
        resp = requests.post(
            f'{_api_url()}/security/user/authenticate',
            auth=(user, password), verify=False, timeout=5,
        )
        resp.raise_for_status()
        return resp.json()['data']['token']
    except Exception as e:
        logger.warning(f'Wazuh get_token: {e}')
        return None


def get_agents():
    try:
        token = get_token()
        if not token:
            return []
        resp = requests.get(
            f'{_api_url()}/agents',
            headers={'Authorization': f'Bearer {token}'},
            params={'limit': 500, 'status': 'active'},
            verify=False, timeout=5,
        )
        resp.raise_for_status()
        return resp.json().get('data', {}).get('affected_items', [])
    except Exception as e:
        logger.warning(f'Wazuh get_agents: {e}')
        return []


def get_recent_alerts(n=20):
    try:
        user, password = _credentials()
        resp = requests.post(
            f'{_indexer_url()}/wazuh-alerts-*/_search',
            json={'size': n, 'sort': [{'timestamp': {'order': 'desc'}}], 'query': {'match_all': {}}},
            auth=(user, password), verify=False, timeout=5,
        )
        resp.raise_for_status()
        return [h.get('_source', {}) for h in resp.json().get('hits', {}).get('hits', [])]
    except Exception as e:
        logger.warning(f'Wazuh get_recent_alerts: {e}')
        return []


def sync_agents_to_assets():
    created = updated = 0
    for agent in get_agents():
        if agent.get('id') == '000':
            continue
        hostname = agent.get('name', '')
        ip = agent.get('ip', '')
        existing = Asset.query.filter_by(hostname=hostname).first()
        if existing:
            existing.ip_address = ip
            existing.source_system = 'wazuh'
            updated += 1
        else:
            db.session.add(Asset(name=hostname, asset_type='server',
                                 ip_address=ip, hostname=hostname, source_system='wazuh'))
            created += 1
    db.session.commit()
    logger.info(f'Wazuh sync: {created} créés, {updated} mis à jour')
    return {'created': created, 'updated': updated}
